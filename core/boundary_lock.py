from __future__ import annotations

from core.eai.intelligence_cycle import BoundaryCard


def within_boundary(boundary: BoundaryCard | None, context: str) -> bool:
    if boundary is None:
        return False
    return boundary.allows(context)
