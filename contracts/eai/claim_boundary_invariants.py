from core.eai.intelligence_cycle import BoundaryCard


def within_boundary(boundary: BoundaryCard, context: str) -> bool:
    return boundary.allows(context)
