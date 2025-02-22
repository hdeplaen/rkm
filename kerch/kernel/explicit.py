# coding=utf-8
"""
File containing the linear kernel class.

@author: HENRI DE PLAEN
@copyright: KU LEUVEN
@license: MIT
@date: March 2021
"""

import torch
from .. import utils
from .kernel import Kernel
from abc import ABCMeta, abstractmethod


@utils.extend_docstring(Kernel)
class Explicit(Kernel, metaclass=ABCMeta):

    @utils.kwargs_decorator({})
    def __init__(self, *args, **kwargs):
        super(Explicit, self).__init__(*args, **kwargs)
        self._dim_feature = None

    def __str__(self):
        return f"Explicit kernel."

    @property
    def explicit(self) -> bool:
        return True

    @property
    def dim_feature(self) -> int:
        if self._dim_feature is None:
            # if it has not been set before, we can compute it with a minimal example
            self._dim_feature = self._explicit_with_none(x=self.current_sample_projected[0:1, :]).shape[1]
        return self._dim_feature

    def _implicit(self, x, y):
        phi_x = self._explicit(x)
        phi_y = self._explicit(y)
        return phi_x @ phi_y.T

    @abstractmethod
    def _explicit(self, x):
        return x

    def _explicit_preimage(self, phi):
        raise NotImplementedError


