import json

import jsonschema

with open("schemas/claim_card.schema.json") as _fh:
    s = json.load(_fh)


def test_claim_card_schema() -> None:
    jsonschema.validate({"claim_id": "CLM-000001", "claim_text": "x", "claim_type": "factual"}, s)
