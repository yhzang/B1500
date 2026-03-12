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
    def _is_no_error(err: str) -> bool:
        """Return True when ERRX? indicates no instrument error."""
        text = err.strip()
        return text.startswith("+0") or text.startswith("0")

    @staticmethod
    def _parse_errx_code(err: str) -> int | None:
        """Parse the numeric code from an ERRX? response like +153,\"...\"."""
        text = err.strip()
        if not text:
            return None

        head = text.split(",", 1)[0].strip()
        try:
            return int(head)
        except ValueError:
            return None

    def _write(self, cmd: str, *, check_err: bool = True, wait_opc: bool = False) -> None:
        """Send a write command with optional OPC wait and ERRX check."""
        self.s.write(cmd)

        if wait_opc:
            _ = self.opc()

        if check_err:
            err = self.errx()
            if not self._is_no_error(err):
                raise B1500Error(f"Command failed: {cmd!r}, ERRX? -> {err}")

    def _query(self, cmd: str, *, check_err: bool = False) -> str:
        """Send a query command and optionally check ERRX afterwards."""
        resp = self.s.query(cmd)

        if check_err:
            err = self.errx()
            if not self._is_no_error(err):
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
        Drain ERRX? until code == 0 or max_reads is reached.

        Returns all ERRX? responses read, including the final no-error record if reached.
        """
        if max_reads <= 0:
            raise ValueError(f"max_reads must be > 0, got {max_reads}")

        records: list[str] = []
        for _ in range(max_reads):
            err = self.errx()
            records.append(err)
            if self._parse_errx_code(err) == 0:
                break
        return records

    # ---------------------------
    # format
    # ---------------------------

    def fmt(self, mode: int = 5) -> None:
        """Set output data format."""
        if not isinstance(mode, int):
            raise TypeError(f"mode must be int, got {type(mode).__name__}")
        if mode < 0:
            raise ValueError(f"mode must be >= 0, got {mode}")

        self._write(f"FMT {mode}", check_err=True, wait_opc=False)

    # ---------------------------
    # channel control
    # ---------------------------

    def cn(self, channels: Iterable[int]) -> None:
        """Connect channels."""
        self._write(f"CN {self._format_channels(channels)}", check_err=True, wait_opc=False)

    def cl(self, channels: Iterable[int]) -> None:
        """Clear channels."""
        self._write(f"CL {self._format_channels(channels)}", check_err=True, wait_opc=False)

    def dz(self, channels: Iterable[int]) -> None:
        """Force zero output on channels."""
        self._write(f"DZ {self._format_channels(channels)}", check_err=True, wait_opc=False)

    # ---------------------------
    # source / measure
    # ---------------------------

    def dv(
        self,
        ch: int,
        vrange: int,
        voltage: float,
        compliance: float | None = None,
        comp_polarity: int | None = None,
        irange: int | None = None,
    ) -> None:
        """Force DC voltage using DV chnum,vrange,voltage[,Icomp[,comp_polarity[,irange]]]."""
        ch = self._validate_channel(ch)
        if not isinstance(vrange, int):
            raise TypeError(f"vrange must be int, got {type(vrange).__name__}")
        if compliance is not None and compliance <= 0:
            raise ValueError(f"compliance must be > 0, got {compliance}")
        if comp_polarity is not None and not isinstance(comp_polarity, int):
            raise TypeError(
                f"comp_polarity must be int when provided, got {type(comp_polarity).__name__}"
            )
        if irange is not None and not isinstance(irange, int):
            raise TypeError(f"irange must be int when provided, got {type(irange).__name__}")

        fields: list[str] = [str(ch), str(vrange), f"{voltage:.12g}"]
        if compliance is not None:
            fields.append(f"{compliance:.12g}")
            if comp_polarity is not None:
                fields.append(str(comp_polarity))
                if irange is not None:
                    fields.append(str(irange))
            elif irange is not None:
                raise ValueError("irange requires comp_polarity to be provided.")
        elif comp_polarity is not None or irange is not None:
            raise ValueError("comp_polarity and irange require compliance to be provided.")

        self._write(f"DV {','.join(fields)}", check_err=True, wait_opc=False)

    def ti(self, ch: int, irange: int = 0) -> float:
        """Spot current measurement."""
        ch = self._validate_channel(ch)

        if not isinstance(irange, int):
            raise TypeError(f"irange must be int, got {type(irange).__name__}")

        resp = self._query(f"TI {ch},{irange}", check_err=False)

        status = self._extract_status(resp)
        if status == "C":
            warnings.warn(f"TI channel {ch} may have hit compliance, response={resp!r}")

        return self._parse_scalar_response(resp)
