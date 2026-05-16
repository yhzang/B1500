"""fefetlab package entry points."""

from __future__ import annotations

from typing import TYPE_CHECKING

__all__ = ["VisaSession", "VisaConfig"]

if TYPE_CHECKING:
    from .instruments.visa_session import VisaConfig, VisaSession


def __getattr__(name: str):
    if name == "VisaSession":
        from .instruments.visa_session import VisaSession

        return VisaSession

    if name == "VisaConfig":
        from .instruments.visa_session import VisaConfig

        return VisaConfig

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
