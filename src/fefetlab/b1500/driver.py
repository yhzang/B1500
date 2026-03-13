from __future__ import annotations

from typing import Iterable, List
import warnings

from fefetlab.instruments.visa_session import VisaSession


class B1500Error(RuntimeError):
    """Raised when B1500 reports an instrument error."""


class B1500:
    """
    Thin but safer B1500 driver.

    Responsibility:
    - Convert Python method calls into B1500 commands
    - Perform basic parameter validation
    - Optionally check instrument error queue
    - Provide minimal response parsing

    Non-responsibility:
    - Experiment workflow
    - Data logging / persistence
    - Complex output parsing for all FMT modes
    """

    def __init__(self, session: VisaSession):
        self.s = session

    # ---------------------------
    # internal helpers
    # ---------------------------

    @staticmethod
    def _parse_errx_code(err: str) -> int:
        """
        Parse error code from ERRX? response.

        Examples:
        '+0,"No Error."' -> 0
        '0,"No Error."' -> 0
        '+153,"No module for the specified channel."' -> 153
        """
        text = err.strip()
        code_str = text.split(",", 1)[0].strip()
        return int(code_str)

    def _write(self, cmd: str, *, check_err: bool = True, wait_opc: bool = False) -> None:
        """Send a write command with optional OPC wait and ERRX check."""
        self.s.write(cmd)

        if wait_opc:
            _ = self.opc()

        if check_err:
            err = self.errx()
            code = self._parse_errx_code(err)
            if code != 0:
                raise B1500Error(f"Command failed: {cmd!r}, ERRX? -> {err}")

    def _query(self, cmd: str, *, check_err: bool = False) -> str:
        """Send a query command and optionally check ERRX afterwards."""
        resp = self.s.query(cmd)

        if check_err:
            err = self.errx()
            code = self._parse_errx_code(err)
            if code != 0:
                raise B1500Error(f"Query failed: {cmd!r}, response={resp!r}, ERRX? -> {err}")

        return resp

    @staticmethod
    def _validate_channel(ch: int) -> int:
        """Validate a single channel index."""
        if not isinstance(ch, int):
            raise TypeError(f"channel must be int, got {type(ch).__name__}: {ch!r}")
        if ch <= 0:
            raise ValueError(f"channel must be positive, got {ch}")
        return ch

    @classmethod
    def _normalize_channels(cls, channels: Iterable[int]) -> List[int]:
        """Validate and normalize channel list."""
        ch_list = [cls._validate_channel(ch) for ch in channels]
        if not ch_list:
            raise ValueError("channels cannot be empty")
        return ch_list

    @classmethod
    def _format_channels(cls, channels: Iterable[int]) -> str:
        """Format channels as comma-separated string after validation."""
        return ",".join(str(ch) for ch in cls._normalize_channels(channels))

    @staticmethod
    def _parse_scalar_response(resp: str) -> float:
        """
        Parse a scalar measurement response conservatively.

        Strategy:
        1. Try direct float(resp)
        2. For comma-separated data, scan fields from right to left
        3. For prefixed tokens like NAI+1.23E-6, parse the numeric suffix
        """
        text = resp.strip()

        try:
            return float(text)
        except ValueError:
            pass

        if "," in text:
            parts = [part.strip() for part in text.split(",") if part.strip()]
            for part in reversed(parts):
                try:
                    return float(part)
                except ValueError:
                    continue

        for idx, ch in enumerate(text):
            if ch in "+-" or ch.isdigit() or ch == ".":
                try:
                    return float(text[idx:])
                except ValueError:
                    break

        raise ValueError(f"Cannot parse scalar from response: {resp!r}")

    @staticmethod
    def _extract_status(resp: str) -> str | None:
        """
        Extract a leading status character from common ASCII responses.
        This is a heuristic.

        Example: C1.234E-3 -> status C
        """
        text = resp.strip()
        if text and text[0].isalpha():
            return text[0]
        return None

    # ---------------------------
    # basic
    # ---------------------------

    def reset(self) -> None:
        """Reset instrument and wait until complete."""
        self._write("*RST", check_err=False, wait_opc=True)

    def opc(self) -> str:
        """Query operation complete."""
        return self._query("*OPC?", check_err=False)

    def errx(self) -> str:
        """Read error queue head."""
        return self._query("ERRX?", check_err=False)

    def clear_err_queue(self, max_reads: int = 20) -> list[str]:
        """
        Drain ERRX? queue until code == 0 or max_reads reached.
        """
        records = []
        for _ in range(max_reads):
            err = self.errx()
            records.append(err)
            code = self._parse_errx_code(err)
            if code == 0:
                break
        return records

    # ---------------------------
    # format / adc helpers
    # ---------------------------

    def fmt(self, mode: int = 5) -> None:
        """Set output data format."""
        if not isinstance(mode, int):
            raise TypeError(f"mode must be int, got {type(mode).__name__}")
        if mode < 0:
            raise ValueError(f"mode must be >= 0, got {mode}")

        self._write(f"FMT {mode}", check_err=True, wait_opc=False)

    def av(self, number: int = 10, mode: int = 1) -> None:
        """Set ADC averaging: AV <number>,<mode>."""
        if not isinstance(number, int):
            raise TypeError(f"number must be int, got {type(number).__name__}")
        if not isinstance(mode, int):
            raise TypeError(f"mode must be int, got {type(mode).__name__}")
        if number <= 0:
            raise ValueError(f"number must be > 0, got {number}")
        if mode < 0:
            raise ValueError(f"mode must be >= 0, got {mode}")

        self._write(f"AV {number},{mode}", check_err=True, wait_opc=False)

    def fl(self, mode: int = 0) -> None:
        """Set filter mode: FL <mode>."""
        if not isinstance(mode, int):
            raise TypeError(f"mode must be int, got {type(mode).__name__}")
        if mode < 0:
            raise ValueError(f"mode must be >= 0, got {mode}")

        self._write(f"FL {mode}", check_err=True, wait_opc=False)

    # ---------------------------
    # channel control
    # ---------------------------

    def cn(self, channels: Iterable[int]) -> None:
        """Connect channels."""
        self._write(f"CN {self._format_channels(channels)}", check_err=True, wait_opc=False)

    def cl(self, channels: Iterable[int] | None = None) -> None:
        """
        Clear channels.

        If channels is None:
            send bare 'CL' to clear all channels.
        """
        if channels is None:
            self._write("CL", check_err=True, wait_opc=False)
        else:
            self._write(f"CL {self._format_channels(channels)}", check_err=True, wait_opc=False)

    def dz(self, channels: Iterable[int]) -> None:
        """Force zero output on channels."""
        self._write(f"DZ {self._format_channels(channels)}", check_err=True, wait_opc=False)

    # ---------------------------
    # source / measure
    # ---------------------------

    def dv(self, ch: int, a: float | int, b: float, c: float | int = 0) -> None:
        """
        Force DC voltage with current compliance.

        Backward-compatible supported call styles:

        New / recommended:
            dv(ch, vrange, voltage, compliance)

        Legacy:
            dv(ch, voltage, compliance, vrange)

        Recommendation:
            Use keyword arguments in new code, for example:
                b.dv(4, 0, -0.2, 1e-3)
            meaning:
                ch=4, vrange=0, voltage=-0.2, compliance=1e-3
        """
        ch = self._validate_channel(ch)

        # New style: dv(ch, vrange, voltage, compliance)
        if isinstance(a, int):
            vrange = a
            voltage = float(b)
            compliance = float(c)
        else:
            # Legacy style: dv(ch, voltage, compliance, vrange)
            voltage = float(a)
            compliance = float(b)
            vrange = int(c)
            warnings.warn(
                "dv(ch, voltage, compliance, vrange) 已过时；"
                "请改用 dv(ch, vrange, voltage, compliance)",
                DeprecationWarning,
                stacklevel=2,
            )

        if not isinstance(vrange, int):
            raise TypeError(f"vrange must be int, got {type(vrange).__name__}")
        if compliance <= 0:
            raise ValueError(f"compliance must be > 0, got {compliance}")

        self._write(
            f"DV {ch},{vrange},{voltage:.12g},{compliance:.12g}",
            check_err=True,
            wait_opc=False,
        )

    def ti(self, ch: int, irange: int = 0) -> float:
        """
        Measure current and parse scalar response.

        Recommended:
            b.ti(ch, irange=0)
        """
        ch = self._validate_channel(ch)

        if not isinstance(irange, int):
            raise TypeError(f"irange must be int, got {type(irange).__name__}")

        resp = self._query(f"TI {ch},{irange}", check_err=False)

        status = self._extract_status(resp)
        if status == "C":
            warnings.warn(f"TI channel {ch} may have hit compliance, response={resp!r}")

        return self._parse_scalar_response(resp)