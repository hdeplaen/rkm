# coding=utf-8
"""
File containing the abstract kernel classes.

@author: HENRI DE PLAEN
@copyright: KU LEUVEN
@license: MIT
@date: March 2021
"""
from __future__ import annotations
import torch
from torch import Tensor
from abc import ABCMeta, abstractmethod
from math import inf

from .. import utils
from ..feature.sample import Sample


@utils.extend_docstring(Sample)
class _BaseKernel(Sample, metaclass=ABCMeta):
    def __init__(self, *args, **kwargs):
        super(_BaseKernel, self).__init__(*args, **kwargs)

    @abstractmethod
    def __str__(self):
        pass

    # PROPERTIES
    @property
    @abstractmethod
    def explicit(self) -> bool:
        r"""
        True if the method has an explicit formulation, False otherwise.
        """
        pass

    @property
    def hparams_fixed(self):
        r"""
        Dictionnary containing the hyper-parameters and their values. This can be relevant for monitoring.
        """
        return {**super(_BaseKernel, self).hparams_fixed}

    @property
    def hparams_variable(self) -> dict:
        r"""
        Dictionnary containing the parameters and their values. This can be relevant for monitoring.
        """
        return {**super(_BaseKernel, self).hparams_variable}

    @property
    @abstractmethod
    def dim_feature(self) -> int | inf:
        r"""
        Returns the dimension of the explicit feature map if it exists.
        """
        pass

    # def merge_idxs(self, *args, **kwargs):
    #     raise NotImplementedError
    #     # self.dmatrix()
    #     # return torch.nonzero(torch.triu(self.dmatrix()) > (1 - kwargs["mtol"]), as_tuple=False)
    #
    # def merge(self, idxs):
    #     raise NotImplementedError
    #     # # suppress added up kernel
    #     # self._Sample = (self._Sample.gather(dim=0, index=idxs[:, 1]) +
    #     #                 self._Sample.gather(dim=0, index=idxs[:, 0])) / 2
    #
    #     self.dmatrix()
    #     # suppress added up kernel entries in the kernel matrix
    #     self._Cache["K"].gather(dim=0, index=idxs[:, 1], out=self._Cache["K"])
    #     self._Cache["K"].gather(dim=1, index=idxs[:, 1], out=self._Cache["K"])
    #
    # def reduce(self, idxs):
    #     raise NotImplementedError
    #     self._Sample.gather(dim=0, index=idxs, out=self._Sample)

    ###################################################################################################
    ################################### MATHS ARE HERE ################################################
    ###################################################################################################

    @abstractmethod
    def _implicit(self, x, y) -> Tensor:
        pass

    def _implicit_with_none(self, x=None, y=None) -> Tensor:
        # implicit raw
        if x is None:
            x = self.current_sample_projected
        if y is None:
            y = self.current_sample_projected
        return self._implicit(x, y)

    def _implicit_self(self, x=None):
        K = self._implicit_with_none(x, x)
        return torch.diag(K)

    @abstractmethod
    def _explicit(self, x) -> Tensor:
        pass

    def _explicit_with_none(self, x=None):
        # explicit raw
        if x is None:
            x = self.current_sample_projected
        return self._explicit(x)

    def _phi(self):
        r"""
        Returns the explicit feature map with default centering and normalization. If already computed, it is
        recovered from the cache.

        :param overwrite: By default, the feature map is recovered from cache if already computed. Force overwrites
            this if True., defaults to False.
        """
        if self.empty_sample:
            raise utils.NotInitializedError('The sample has not been initialized yet.')
        return self._get("phi", level_key="sample_phi", fun=self.explicit)

    def _C(self) -> Tensor:
        r"""
        Returns the covariance matrix with default centering and normalization. If already computed, it is recovered
        from the cache.

        :param overwrite: By default, the covariance matrix is recovered from cache if already computed. Force overwrites
            this if True., defaults to False
                """
        def fun():
            self._check_sample()
            scale = 1 / self.num_idx
            phi = self._phi()
            return scale * phi.T @ phi
        return self._get("C", level_key="sample_C", fun=fun)

    def _K(self, explicit=None, force : bool=False) -> Tensor:
        r"""
        Returns the kernel matrix with default centering and normalization. If already computed, it is recovered from
        the cache.

        :param explicit: Specifies whether the explicit or implicit formulation has to be used. Always uses the
            the explicit if available.
        :param force: By default, the kernel matrix is recovered from cache if already computed. Force overwrites
            this if True., defaults to False
        """
        def fun(explicit):
            self._check_sample()
            if explicit is None: explicit = self.explicit
            if explicit:
                phi = self._phi()
                return phi @ phi.T
            else:
                return self._explicit_with_none()
        return self._get("K", level_key="sample_K", fun=lambda: fun(explicit))

    # ACCESSIBLE METHODS
    def phi(self, x=None) -> Tensor:
        r"""
        Returns the explicit feature map :math:`\phi(\cdot)` of the specified points.

        :param x: The datapoints serving as input of the explicit feature map. If `None`, the sample will be used.,
            defaults to `None`
        :type x: Tensor(,dim_input), optional
        :raises: ExplicitError
        """
        if x is None:
            return self._phi()

        x = utils.castf(x)
        x = self.transform_input(x)
        return self._explicit_with_none(x)

    def k(self, x=None, y=None, explicit=None) -> Tensor:
        r"""
        Returns a kernel matrix, either of the sample, either out-of-sample, either fully out-of-sample.

        .. math::
            K = [k(x_i,y_j)]_{i,j=1}^{N,M},

        with :math:`\{x_i\}_{i=1}^N` the out-of-sample points (`x`) and :math:`\{y_i\}_{j=1}^N` the sample points
        (`y`).

        .. note::
            In the case of centered kernels, this computation is more expensive as it requires to _center according to
            the sample data, which implies computing a statistic on the out-of-sample kernel matrix and thus
            also computing it.

        :param x: Out-of-sample points (first dimension). If `None`, the default sample will be used., defaults to `None`
        :param y: Out-of-sample points (second dimension). If `None`, the default sample will be used., defaults to `None`

        :type x: Tensor(N,dim_input), optional
        :type y: Tensor(M,dim_input), optional

        :return: Kernel matrix
        :rtype: Tensor(N,M)

        :raises: ExplicitError
        """
        if x is None and y is None:
            return self._K(explicit=self.explicit)

        # in order to get the values in the correct format (e.g. coming from numpy)
        x = utils.castf(x)
        y = utils.castf(y)
        x = self.transform_input(x)
        y = self.transform_input(y)
        return self._implicit_with_none(x, y)

    def c(self, x=None) -> Tensor:
        r"""
        Out-of-sample explicit matrix.

        .. math::
            C = \frac1M\sum_{i}^{M} \phi(x_i)\phi(x_i)^\top.

        :param x: Out-of-sample points (first dimension). If `None`, the default sample will be used., defaults to `None`
        :type x: Tensor(N,dim_input), optional

        :return: Covariance matrix
        :rtype: Tensor(dim_feature,dim_feature)
        """

        phi = self.phi(x)
        scale = 1 / x.shape[0]
        return scale * phi.T @ phi

    def forward(self, x, representation="implicit") -> Tensor:
        """
        Passes datapoints through the kernel.

        :param x: Datapoints to be passed through the kernel.
        :param representation: Chosen representation. If `dual`, an out-of-sample kernel matrix is returned. If
            `primal` is specified, it returns the explicit feature map., defaults to `dual`

        :type x: Tensor(,dim_input)
        :type representation: str, optional

        :return: Out-of-sample kernel matrix or explicit feature map depending on `representation`.

        :raises: RepresentationError
        """

        def explicit(x):
            return self.phi(x)

        def implicit(x):
            return self.k(x)

        switcher = {"explicit": explicit,
                    "implicit": implicit}

        fun = switcher.get(representation, utils.RepresentationError(cls=self))
        return fun(x)

    @property
    def K(self) -> Tensor:
        r"""
        Returns the kernel matrix on the sample data. Same result as calling :py:func:`k()`, but faster.
        It is loaded from memory if already computed and unchanged since then, to avoid re-computation when recurrently
        called.

        .. math::
            K_{ij} = k(x_i,x_j).
        """
        return self._K()

    @property
    def C(self) -> Tensor:
        r"""
        Returns the explicit matrix on the sample datapoints.

        .. math::
            C = \frac{1}{\texttt{num_idx}}\sum_i^\texttt{num_idx} \phi(x_i)\phi(x_i)^\top.
        """
        return self._C()

    @property
    def Phi(self) -> Tensor:
        r"""
        Returns the explicit feature map :math:`\phi(\cdot)` of the sample datapoints. Same as calling
        :py:func:`phi()`, but slightly faster.
        It is loaded from memory if already computed and unchanged since then, to avoid re-computation when recurrently
        called.
        """
        return self._phi()

    ## DIRECT ATTRIBUTES

    @property
    def Cov(self) -> torch.Tensor:
        r"""
        Returns the covariance matrix of the sample. Same as calling self.cov().
        """
        return self.cov()

    @property
    def Corr(self) -> torch.Tensor:
        r"""
        Returns the correlation matrix of the sample. Same as calling self.corr().
        """
        return self.corr()

    def implicit_preimage(self, k_image: Tensor | None = None, method: str = 'knn', **kwargs):
        r"""
        Computes a pre-image of coefficients in the RKHS of the kernel, given by ``k_image``.
        Different methods are available:

        * ``'knn'``: Nearest neighbors. We refer to :py:func:`kerch.method.knn` for more details.
        * ``'smoother'``: Kernel smoothing. We refer to :py:func:`kerch.method.smoother` for more details
        * ``'iterative'``: Iterative optimization. We refer to :py:func:`kerch.method.iterative_preimage_k` for more details

        :param k_image: RKHS coefficients to be inverted. If not specified (``None``), the kernel matrix on the sample is used.
        :type k_image: torch.Tensor [num_points, num_idx], optional
        :param method: Pre-image method to be used. Defaults to ``'knn'``.
        :type method: str, optional
        :param \**kwargs: Additional parameters of the pre-image method used. Please refer to its documentation for
            further details.
        :type \**kwargs: dict, optional
        :return: Pre-image
        :rtype: torch.Tensor [num_points, dim_input]
        """

        # DEFENSIVE
        k_image = utils.castf(k_image)
        if k_image is None:
            k_image = self.K

        if torch.all(k_image < 0):
            self._logger.warning(f"The argument k_coefficient contains negative values, which should never be the case by "
                              f"definition of a RKHS.")

        # PRE-IMAGE
        method = method.lower()
        if method == 'knn':
            from ..method import knn
            return knn(dists=-k_image, observations=self.current_sample, **kwargs)
        elif method == 'smoother':
            from ..method import smoother
            return smoother(coefficients=k_image, observations=self.current_sample, **kwargs)
        elif method == 'iterative':
            from ..method import iterative_preimage_k
            return iterative_preimage_k(k_image=k_image, kernel=self, **kwargs)
        else:
            raise AttributeError('Unknown or non-implemented preimage method.')

