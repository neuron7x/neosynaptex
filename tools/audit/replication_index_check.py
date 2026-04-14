"""Ratchet: the replications registry must never silently regress or rot.

Signal contract
---------------

``evidence/replications/registry.yaml`` is the canonical index of
every independent replication attempt filed against a γ-claim per
``docs/REPLICATION_PROTOCOL.md``. This tool enforces three
invariants:

1. **Shape** — the registry parses into ``{schema_version, protocol,
   replications: [...]}`` and every entry has the required keys
   (``id``, ``date``, ``substrate_class``, ``lab``, ``prereg_path``,
   ``verdict``, ``commit_sha``, ``claim_tested``,
   ``interpretation_boundary``).
2. **Integrity** — every ``prereg_path`` points at a file that
   exists. ``substrate_class`` is in
   ``{in_vivo_cns, neuronal_culture, simulated_agent}`` and
   ``verdict`` is in ``{support, falsification, theory_revision,
   pending}``.
3. **Ratchet** — the number of entries in the registry is
   ``>= min_replications_count`` from
   ``tools/audit/replication_baseline.json``. Scaffold-time baseline
   is 0; bumps happen in the same PR that appends entries.

Scope is deliberately structural. The tool does NOT re-run any
replication, does NOT compare γ values against the ledger, does NOT
validate that the prereg YAML itself conforms to §7. Semantic
correctness stays the reviewer's job.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

__all__ = [
    "ALLOWED_SUBSTRATE_CLASSES",
    "ALLOWED_VERDICTS",
    "REQUIRED_ENTRY_KEYS",
    "IntegrityError",
    "load_baseline",
    "load_registry",
    "main",
    "run_check",
]

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_REGISTRY = _REPO_ROOT / "evidence" / "replications" / "registry.yaml"
_BASELINE_PATH = _REPO_ROOT / "tools" / "audit" / "replication_baseline.json"

REQUIRED_ENTRY_KEYS: frozenset[str] = frozenset(
    {
        "id",
        "date",
        "substrate_class",
        "lab",
        "prereg_path",
        "verdict",
        "commit_sha",
        "claim_tested",
        "interpretation_boundary",
    }
)

ALLOWED_SUBSTRATE_CLASSES: frozenset[str] = frozenset(
    {
        # Neural classes (original REPLICATION_PROTOCOL.md scope).
        "in_vivo_cns",
        "neuronal_culture",
        "simulated_agent",
        # γ-program extensions per docs/CLAIM_BOUNDARY.md §3.2 —
        # cross-substrate convergence framing spans neural + market +
        # morphogenetic substrates. Adding a class here requires a
        # matching row in docs/SUBSTRATE_MEASUREMENT_TABLE.yaml.
        "market_macro",
        "market_microstructure",
        "developmental_transcriptome",
        "physiological_cardiac",
        "reaction_diffusion",
        "synchronisation",
    }
)
ALLOWED_VERDICTS: frozenset[str] = frozenset(
    {"support", "falsification", "theory_revision", "pending"}
)


class IntegrityError(ValueError):
    """Raised when the registry cannot be parsed into the expected shape."""


def _load_yaml(text: str) -> dict:
    try:
        import yaml  # type: ignore[import-untyped]

        data = yaml.safe_load(text)
        if data is None:
            return {}
        if not isinstance(data, dict):
            raise IntegrityError("registry.yaml: top level must be a mapping")
        return data
    except ImportError:  # pragma: no cover - fallback path
        return _parse_registry_fallback(text)


# Narrow fallback parser. Recognises exactly the shape registry.yaml
# uses (top-level scalars + a list of dict entries under
# ``replications:``). Any other structure is rejected.
_SCALAR_LINE = re.compile(r"^(?P<key>[a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*(?P<val>.*?)\s*$")


def _parse_registry_fallback(text: str) -> dict:
    top: dict[str, object] = {}
    replications: list[dict[str, object]] = []
    in_list = False
    current: dict[str, object] | None = None

    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw.startswith("replications:"):
            in_list = True
            rest = raw.partition(":")[2].strip()
            if rest == "[]":
                top["replications"] = []
                in_list = False
            continue
        if not in_list:
            m = _SCALAR_LINE.match(raw)
            if m:
                val = m.group("val").strip()
                if val.startswith('"') and val.endswith('"'):
                    val = val[1:-1]
                if val.isdigit():
                    top[m.group("key")] = int(val)
                else:
                    top[m.group("key")] = val
            continue

        stripped = raw.rstrip()
        indent = len(stripped) - len(stripped.lstrip(" "))
        line = stripped.strip()

        if line.startswith("- ") and indent == 2:
            current = {}
            replications.append(current)
            remainder = line[2:].strip()
            if remainder:
                key, _, val = remainder.partition(":")
                current[key.strip()] = val.strip()
            continue

        if current is None:
            continue

        if indent == 4 and ":" in line:
            key, _, val = line.partition(":")
            val = val.strip()
            if val.startswith('"') and val.endswith('"'):
                val = val[1:-1]
            current[key.strip()] = val

    # If the ``replications:`` line was seen, record the parsed list.
    # If it was NOT seen, leave ``top`` without the key so that
    # ``load_registry`` raises IntegrityError for missing key — per
    # the contract. Silently defaulting to ``[]`` would mask the
    # missing-key case and let the gate pass when it should fail
    # (CI-reproducible bug on #83).
    if in_list or replications:
        top["replications"] = replications
    return top


def load_registry(path: pathlib.Path = _REGISTRY) -> dict:
    if not path.is_file():
        raise IntegrityError(f"registry.yaml not found at {path}")
    text = path.read_text(encoding="utf-8")
    data = _load_yaml(text)

    replications = data.get("replications")
    if replications is None:
        raise IntegrityError("registry.yaml: missing 'replications' key")
    if not isinstance(replications, list):
        raise IntegrityError("registry.yaml: 'replications' must be a list")

    return data


def load_baseline(path: pathlib.Path = _BASELINE_PATH) -> int:
    if not path.is_file():
        raise IntegrityError(f"baseline file not found at {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    value = data.get("min_replications_count")
    if not isinstance(value, int) or value < 0:
        raise IntegrityError(
            "replication_baseline.json: min_replications_count must be a non-negative int"
        )
    return value


def _validate_entry(entry: dict, index: int, repo_root: pathlib.Path) -> list[str]:
    errors: list[str] = []
    if not isinstance(entry, dict):
        return [f"entry[{index}]: must be a mapping"]

    missing = REQUIRED_ENTRY_KEYS - entry.keys()
    if missing:
        errors.append(
            f"entry[{index}] id={entry.get('id', '<no id>')!r}: missing keys {sorted(missing)}"
        )

    sclass = entry.get("substrate_class")
    if isinstance(sclass, str) and sclass not in ALLOWED_SUBSTRATE_CLASSES:
        errors.append(
            f"entry[{index}] id={entry.get('id')!r}: substrate_class "
            f"{sclass!r} not in {sorted(ALLOWED_SUBSTRATE_CLASSES)}"
        )

    verdict = entry.get("verdict")
    if isinstance(verdict, str) and verdict not in ALLOWED_VERDICTS:
        errors.append(
            f"entry[{index}] id={entry.get('id')!r}: verdict "
            f"{verdict!r} not in {sorted(ALLOWED_VERDICTS)}"
        )

    prereg = entry.get("prereg_path")
    if (
        isinstance(prereg, str)
        and prereg.strip()
        and not (repo_root / prereg.strip()).exists()
    ):
        errors.append(
            f"entry[{index}] id={entry.get('id')!r}: "
            f"prereg_path points at missing file {prereg!r}"
        )

    return errors


def run_check(
    registry_path: pathlib.Path = _REGISTRY,
    baseline_path: pathlib.Path = _BASELINE_PATH,
    repo_root: pathlib.Path = _REPO_ROOT,
) -> tuple[int, str]:
    try:
        data = load_registry(registry_path)
        baseline = load_baseline(baseline_path)
    except (IntegrityError, json.JSONDecodeError, FileNotFoundError) as exc:
        return 2, f"DRIFT: {exc}"

    replications = data.get("replications") or []
    errors: list[str] = []
    for i, entry in enumerate(replications):
        errors.extend(_validate_entry(entry, i, repo_root))

    if errors:
        return 2, "DRIFT: " + "; ".join(errors)

    current = len(replications)
    if current < baseline:
        return (
            2,
            f"DRIFT: replications count regressed — baseline={baseline}, "
            f"current={current}. Reducing the count requires an explicit "
            "diff to replication_baseline.json with a written rationale.",
        )

    return (
        0,
        f"OK: {current} replication(s) in registry (baseline={baseline}). "
        "All prereg_paths exist, all substrate_classes and verdicts valid.",
    )


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - CLI
    _ = argv
    code, message = run_check()
    stream = sys.stdout if code == 0 else sys.stderr
    print(message, file=stream)
    return code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
