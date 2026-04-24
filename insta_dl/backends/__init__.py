from ..backend import InstagramBackend
from .aiograpi_backend import AiograpiBackend
from .hiker import HikerBackend


def make_backend(name: str, **kwargs: object) -> InstagramBackend:
    if name == "hiker":
        return HikerBackend(**kwargs)  # type: ignore[arg-type]
    if name == "aiograpi":
        return AiograpiBackend(**kwargs)  # type: ignore[arg-type]
    raise ValueError(f"unknown backend: {name!r}")


__all__ = ["AiograpiBackend", "HikerBackend", "InstagramBackend", "make_backend"]
