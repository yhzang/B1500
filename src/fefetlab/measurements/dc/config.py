"""Configuration dataclasses for DC sweep measurements."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass(init=False)
class DCChannelConfig:
    """Configuration for a single DC channel.

    Public/current naming uses ``compliance``.
    Legacy notebooks/code may still pass/use ``i_comp``.

    Attributes:
        channel: Physical channel number (e.g., 4, 5, 6)
        vrange: Voltage range index (0 for auto-ranging)
        compliance: Current compliance limit in Amperes
        role: Channel role ('G', 'D', 'S', or 'X')
    """

    channel: int
    vrange: int = 0
    compliance: float = 1e-3
    role: str = ""

    def __init__(
        self,
        channel: int,
        vrange: int = 0,
        compliance: Optional[float] = None,
        i_comp: Optional[float] = None,
        role: str = "",
    ):
        if compliance is not None and i_comp is not None and compliance != i_comp:
            raise ValueError("compliance and i_comp must match when both are provided")

        resolved_compliance = compliance if compliance is not None else i_comp
        if resolved_compliance is None:
            resolved_compliance = 1e-3

        self.channel = channel
        self.vrange = vrange
        self.compliance = float(resolved_compliance)
        self.role = role

    @property
    def i_comp(self) -> float:
        """Backward-compatible alias for ``compliance``."""
        return self.compliance

    @i_comp.setter
    def i_comp(self, value: float) -> None:
        self.compliance = float(value)


@dataclass
class DCSweepConfig:
    """Configuration for DC sweep measurements.

    Attributes:
        channels: Dictionary mapping role ('G'/'D'/'S') to DCChannelConfig
        delay_s: Delay after voltage setting before measurement (seconds)
        fmt_mode: Format mode (1=ASCII 12-digit, 5=ASCII 13-digit)
        av_mode: Averaging mode
        av_count: Number of samples to average
        fl_mode: Filter mode. Default is stability-first (`1`) based on
            the official B1500 software guidance that filter ON reduces
            spikes/overshoot at the cost of longer settling time.
        integration_time_mode: Reserved integration-time mode slot for future
            driver wiring (for example AUTO/MANUAL/PLC/TIME). Not applied yet.
        integration_time_factor: Reserved integration-time factor for future
            driver wiring. Not applied yet.
    """

    channels: dict[str, DCChannelConfig] = field(default_factory=dict)
    delay_s: float = 0.2
    fmt_mode: int = 5
    av_mode: int = 1
    av_count: int = 10
    fl_mode: int = 1
    integration_time_mode: Optional[str] = None
    integration_time_factor: Optional[float] = None

    @classmethod
    def from_notebooks_default(cls, ch_g: int, ch_d: int, ch_s: int):
        """Create default config matching notebook 08/09 settings.

        Args:
            ch_g: Gate channel number
            ch_d: Drain channel number
            ch_s: Source channel number

        Returns:
            DCSweepConfig with default settings
        """
        return cls(
            channels={
                'G': DCChannelConfig(channel=ch_g, vrange=0, compliance=1e-3, role='G'),
                'D': DCChannelConfig(channel=ch_d, vrange=0, compliance=1e-3, role='D'),
                'S': DCChannelConfig(channel=ch_s, vrange=0, compliance=1e-3, role='S'),
            },
            delay_s=0.2,
            fmt_mode=5,
            av_mode=1,
            av_count=10,
            fl_mode=1,
            integration_time_mode=None,
            integration_time_factor=None,
        )
