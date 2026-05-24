import pytest

from core.eai.dopa_types import ClaimSignal


def test_invalid_signal_rejected() -> None:
    with pytest.raises(ValueError):
        ClaimSignal("bad", 2.0, 0.1, 0.1, 0.1, 0.1, 0.1)
