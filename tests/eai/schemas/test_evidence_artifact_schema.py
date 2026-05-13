import json

import jsonschema
import pytest

with open("schemas/evidence_artifact.schema.json") as _fh:
    s = json.load(_fh)


def test_evidence_artifact_schema() -> None:
    good = {
        "artifact_id": "EVD-000001",
        "status": "EVIDENCE",
        "claim_id": "CLM-000001",
        "boundary_id": "BND-000001",
        "reproducibility_manifest": {},
        "artifact_hash": "a" * 64,
        "integration_permission": True,
    }
    jsonschema.validate(good, s)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({**good, "integration_permission": False}, s)
