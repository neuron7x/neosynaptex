import json

import jsonschema

with open("schemas/boundary_card.schema.json") as _fh:
    s = json.load(_fh)


def test_boundary_card_schema() -> None:
    jsonschema.validate(
        {
            "boundary_id": "BND-000001",
            "valid_for": ["a"],
            "invalid_for": ["b"],
            "tested_conditions": ["a"],
            "untested_conditions": ["b"],
        },
        s,
    )
