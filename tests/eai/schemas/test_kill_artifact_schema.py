import json

import jsonschema
import pytest

with open("schemas/kill_artifact.schema.json") as _fh:
    s = json.load(_fh)


def test_kill_artifact_schema() -> None:
    good = {
        "artifact_id": "KILL-000001",
        "status": "KILLED",
        "claim_id": "CLM-000001",
        "kill_reason": "r",
        "future_guardrail": "g",
        "artifact_hash": "a" * 64,
        "integration_permission": False,
    }
    jsonschema.validate(good, s)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({**good, "kill_reason": ""}, s)
