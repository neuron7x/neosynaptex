import json

import jsonschema
import pytest

with open("schemas/artifact_ledger_entry.schema.json") as _fh:
    s = json.load(_fh)


def test_artifact_ledger_entry_schema() -> None:
    jsonschema.validate(
        {"ledger_id": "LEDGER-000001", "status": "KILLED", "artifact_hash": "a" * 64}, s
    )
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"ledger_id": "LEDGER-1", "status": "BAD", "artifact_hash": "no"}, s)
