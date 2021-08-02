"""
LS-SVM abstract level

@author: HENRI DE PLAEN
@copyright: KU LEUVEN
@license: MIT
@date: March 2021
"""

import torch
import random
import numpy as np
from abc import ABCMeta, abstractmethod

import rkm
from rkm.model.level import Level
from rkm.model import RepresentationError


class LSSVM(Level, metaclass=ABCMeta):
    """
    Abstract LSSVM class.
    """

    @rkm.kwargs_decorator(
        {"gamma": 1.})
    def __init__(self, **kwargs):
        """

        :param gamma: reconstruction / regularization trade-off.
        """
        add_kwargs = {"requires_bias": True}  # LS-SVM level becomes ridge regression if this is False.
        new_kwargs = {**kwargs, **add_kwargs}
        super(LSSVM, self).__init__(**new_kwargs)

        self._gamma = kwargs["gamma"]
        self._criterion = torch.nn.MSELoss(reduction="mean")
        self._generate_representation(**kwargs)

        self._last_recon = torch.tensor(0.)
        self._last_reg = torch.tensor(0.)
        self._last_loss = torch.tensor(0.)

    @property
    def gamma(self):
        return self._gamma

    @property
    def hparams(self):
        return {"Type": "LSSVM",
                "Gamma": self.gamma,
                **super(LSSVM, self).hparams}

    @property
    def last_recon(self):
        return self._last_recon.data

    @property
    def last_reg(self):
        return self.last_reg.data

    @property
    def last_loss(self):
        return self._last_loss.data

    def _generate_representation(self, **kwargs):
        # REGULARIZATION
        def primal_reg(idx_kernels):
            weight = self._model['linear'].weight
            return (1 / len(idx_kernels)) * weight.t() @ weight
            # return weight.t() @ weight

        def dual_reg(idx_kernels):
            alpha = self._model["linear"].alpha[idx_kernels]
            K = self._model["kernel"].dmatrix(idx_kernels)
            return (1 / len(idx_kernels)) * alpha.t() @ K @ alpha
            # return alpha.t() @ K @ alpha

        switcher_reg = {"primal": lambda idx_kernels: primal_reg(idx_kernels),
                        "dual": lambda idx_kernels: dual_reg(idx_kernels)}
        self._reg = switcher_reg.get(kwargs["representation"], RepresentationError)

    def recon(self, x, y, idx_kernels=None):
        if idx_kernels is None: idx_kernels = self._all_kernels
        x_tilde = self.forward(x, idx_kernels)
        return self._criterion(x_tilde, y), x_tilde

    def reg(self, idx_kernels=None):
        if idx_kernels is None: idx_kernels = self._all_kernels
        return torch.trace(self._reg(idx_kernels))

    def loss(self, x=None, y=None, idx_kernels=None):
        if idx_kernels is None: idx_kernels = self._all_kernels
        recon, x_tilde = self.recon(x, y, idx_kernels)
        reg = self.reg(idx_kernels)
        l = .5 * reg + .5 * self._gamma * recon
        self._last_recon = recon.data
        self._last_reg = reg.data
        self._last_loss = l.data
        return l, x_tilde

    def solve(self, x, y=None):
        assert y is not None, "Tensor y is unspecified. This is not allowed for a LSSVM level."
        switcher = {'primal': lambda: self.primal(x, y),
                    'dual': lambda: self.dual(x, y)}

        return switcher.get(self.representation, RepresentationError)()

    def primal(self, x, y):
        assert y.size(1) == 1, "Not implemented for multi-dimensional output (as for now)."

        C, phi = self._model['kernel'].cov(x)
        n = phi.size(1)
        I = torch.eye(n)
        P = torch.sum(phi, dim=0)
        S = torch.sum(y, dim=0)
        Y = phi.t() @ y

        A = torch.cat((torch.cat((C + (1 / self._gamma) * I, P.t()), dim=1),
                       torch.cat((P, n), dim=1)), dim=0)
        B = torch.cat((Y, S), dim=0)

        sol = torch.solve(A, B)
        weight = sol[0:-1].data
        bias = sol[-1].data

        return weight, bias

    def dual(self, x, y):
        assert y.dim() == 1, "Not implemented for multi-dimensional output (as for now)."
        n = x.size(0)

        K = self._model["kernel"].dmatrix(self._all_kernels)
        I = torch.eye(n, device=self.device)
        N = torch.ones((n, 1), device=self.device)
        A = torch.cat((torch.cat((K + (1 / self._gamma) * I, N), dim=1),
                       torch.cat((N.t(), torch.tensor([[0.]], device=self.device)), dim=1)), dim=0)
        B = torch.cat((y, torch.tensor([0.], device=self.device)), dim=0)

        sol, _ = torch.solve(B[:, None], A)
        alpha = sol[0:-1].data
        beta = sol[-1].data

        reg = (1 / len(y)) * alpha.t() @ K @ alpha
        yhat = (K @ alpha + beta.expand([n, 1])).squeeze()
        recon = (1 / len(y)) * torch.sum((yhat - y) ** 2)

        return alpha, beta

    def get_params(self, slow_names=None):
        euclidean = torch.nn.ParameterList(
            [p for n, p in self._model['kernel'].named_parameters() if p.requires_grad and n not in slow_names])
        euclidean.extend(
            [p for p in self._model['linear'].parameters() if p.requires_grad])
        slow = torch.nn.ParameterList(
            [p for n, p in self._model['kernel'].named_parameters() if p.requires_grad and n in slow_names])
        stiefel = torch.nn.ParameterList()
        return euclidean, slow, stiefel
