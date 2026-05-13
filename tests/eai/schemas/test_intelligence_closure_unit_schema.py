import json

import jsonschema
import pytest

with open("schemas/intelligence_closure_unit.schema.json") as _fh:
    s = json.load(_fh)


def test_intelligence_closure_unit_schema() -> None:
    jsonschema.validate(
        {"icu_id": "ICU-000001", "status": "EVIDENCE", "retention_hash": "a" * 64}, s
    )
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"icu_id": "BAD", "status": "X", "retention_hash": "z"}, s)
