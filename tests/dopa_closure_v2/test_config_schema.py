from pathlib import Path

from scripts.validate_dopa_closure_v2_config import validate_config


def test_config_validator_passes_real_config() -> None:
    assert not validate_config(Path("configs/dopa_closure_v2/allocator.yaml"))
