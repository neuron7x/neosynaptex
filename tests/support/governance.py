from __future__ import annotations

import pytest


def traces_equation(eq_id: str) -> pytest.MarkDecorator:
    return pytest.mark.trace_eq(eq_id)
