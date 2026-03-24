"""Testing utilities for DC measurement module.

Provides mock instruments and test helpers for DC sweep functionality.
"""


class MockB1500:
    """Mock B1500 instrument for testing without hardware.

    Simulates basic B1500 behavior:
    - Voltage setting and storage
    - Simulated I-V characteristics
    - Error checking (always returns no error)

    Used for:
    - Unit testing DC sweep functionality
    - Verification scripts without hardware
    - Development and debugging

    Example:
        >>> mock = MockB1500()
        >>> mock.dv(4, 0, -0.5, 1e-3)  # Set gate voltage
        >>> current = mock.ti(4)  # Measure gate current
        >>> print(f"IG = {current:.3e} A")
    """

    def __init__(self):
        """Initialize mock instrument state."""
        self.voltages = {}
        self.channels_connected = set()
        self.call_count = 0

    def fmt(self, mode: int):
        """Format mode setting (mock - does nothing)."""
        pass

    def av(self, count: int, mode: int):
        """Averaging setting (mock - does nothing)."""
        pass

    def fl(self, mode: int):
        """Filter setting (mock - does nothing)."""
        pass

    def cn(self, channels: list):
        """Connect channels (mock - tracks channel state)."""
        self.channels_connected = set(channels)

    def dv(self, ch: int, vrange: int, voltage: float, compliance: float):
        """Set voltage on channel (mock - stores voltage).

        Args:
            ch: Channel number
            vrange: Voltage range (ignored in mock)
            voltage: Voltage to set (V)
            compliance: Current compliance (A, ignored in mock)
        """
        self.voltages[ch] = voltage

    def ti(self, ch: int, irange: int = 0) -> float:
        """Measure current on channel (mock - returns simulated value).

        Args:
            ch: Channel number
            irange: Current range (ignored in mock)

        Returns:
            Simulated current value (A)

        Simulation model:
            - CH4 (Gate): IG = VG * 1e-8 (leakage)
            - CH5 (Drain): ID = VD^2 * 1e-5 for VD<0, else 1e-6
            - Other: 0 A
        """
        voltage = self.voltages.get(ch, 0.0)

        if ch == 4:  # Gate
            return voltage * 1e-8  # Small leakage current
        elif ch == 5:  # Drain
            # Simple nonlinear I-V: quadratic for negative voltage
            return (voltage ** 2) * 1e-5 if voltage < 0 else 1e-6
        else:  # Source or others
            return 0.0

    def errx(self) -> str:
        """Check error queue (mock - always returns no error)."""
        return "0"

    def dz(self, channels: list):
        """Zero channels (mock - sets voltages to 0)."""
        for ch in channels:
            self.voltages[ch] = 0.0

    def cl(self, channels: list):
        """Close/disable channels (mock - does nothing)."""
        pass
