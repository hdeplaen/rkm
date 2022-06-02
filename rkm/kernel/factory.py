from .base import base
from .. import utils

def factory(type='linear', **kwargs) -> base:
    r"""
    Creates a kernel based on the specified type with the specified arguments. This is the same as
    calling `rkm.kernel.type(**kwargs)` (if `type` is not a string here). This allows for the creation of kernel where
    the type of kernel is passed as a string.

    :param type: Type of kernel chosen. For the possible choices, please refer to the (non-abstract) classes
        herebelow., defaults to `linear`
    :param \**kwargs: Arguments to be passed to the kernel constructor, such as `sample` or `sigma`. If an argument is
        passed that does not exist (e.g. `sigma` to a `linear` kernel), it will just be neglected. For the default
        values, please refer to the default values of the requested kernel.
    :type type: str, optional
    :type \**kwargs: dict, optional
    :return: An instantiation of the specified kernel.
    """
    try:
        import rkm.kernel
        kernel = getattr(rkm.kernel, type)
    except:
        self._log.error("Invalid kernel type.")
        raise
    return kernel(**kwargs)

