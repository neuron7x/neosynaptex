import json

import jsonschema
import pytest

with open("schemas/iev_gate_decision.schema.json") as _fh:
    s = json.load(_fh)


def test_iev_gate_decision_schema() -> None:
    jsonschema.validate(
        {"decision_id": "IEV-000001", "status": "QUARANTINED", "claim_id": "CLM-000001"}, s
    )
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"decision_id": "IEV-1", "status": "OK", "claim_id": "x"}, s)
