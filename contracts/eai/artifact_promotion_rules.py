from core.eai.intelligence_cycle import EvidenceArtifact


def may_promote(artifact: EvidenceArtifact) -> bool:
    return artifact.can_be_promoted()
