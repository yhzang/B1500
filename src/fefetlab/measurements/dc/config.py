"""Configuration dataclasses for DC sweep measurements."""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class DCChannelConfig:
    """Configuration for a single DC channel.

    Attributes:
        channel: Physical channel number (e.g., 4, 5, 6)
        vrange: Voltage range index (0 for auto-ranging)
        i_comp: Current compliance limit in Amperes
        role: Channel role ('G', 'D', 'S', or 'X')
    """
    channel: int
    vrange: int = 0
    i_comp: float = 1e-3
    role: str = ""


@dataclass
class DCSweepConfig:
    """Configuration for DC sweep measurements.

    Attributes:
        channels: Dictionary mapping role ('G'/'D'/'S') to DCChannelConfig
        delay_s: Delay after voltage setting before measurement (seconds)
        fmt_mode: Format mode (1=ASCII 12-digit, 5=ASCII 13-digit)
        av_mode: Averaging mode
        av_count: Number of samples to average
        fl_mode: Filter mode (0=off)
    """
    channels: dict[str, DCChannelConfig] = field(default_factory=dict)
    delay_s: float = 0.2
    fmt_mode: int = 5
    av_mode: int = 1
    av_count: int = 10
    fl_mode: int = 0

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
                'G': DCChannelConfig(channel=ch_g, vrange=0, i_comp=1e-3, role='G'),
                'D': DCChannelConfig(channel=ch_d, vrange=0, i_comp=1e-3, role='D'),
                'S': DCChannelConfig(channel=ch_s, vrange=0, i_comp=1e-3, role='S'),
            },
            delay_s=0.2,
            fmt_mode=5,
            av_mode=1,
            av_count=10,
            fl_mode=0,
        )
