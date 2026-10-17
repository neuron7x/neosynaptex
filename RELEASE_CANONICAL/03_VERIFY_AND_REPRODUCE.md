# Reproduce the frozen canonical source ZIP

**Base snapshot commit:** `04f232e22066e594a29fa9b95e28a7ac48851122`  
**Base Git tree:** `57b4f5804a66c9efc263a97f20d307ef2aac872b`  
**Original tracked blobs:** **10,694**, partitioned into six complete, ordered manifest parts.

## One ZIP / GitHub source archive

Download the **commit-pinned GitHub source ZIP** supplied with this release. Do not use mutable `main.zip` for reproducibility.

```bash
sha256sum NEOSYNAPTEX_H5_CANONICAL.zip
unzip -t NEOSYNAPTEX_H5_CANONICAL.zip
mkdir -p /tmp/neosynaptex-h5
unzip NEOSYNAPTEX_H5_CANONICAL.zip -d /tmp/neosynaptex-h5
ROOT=$(find /tmp/neosynaptex-h5 -mindepth 1 -maxdepth 1 -type d | head -n1)
python3 "$ROOT/RELEASE_CANONICAL/verify_source_snapshot.py" "$ROOT" \
  --archive NEOSYNAPTEX_H5_CANONICAL.zip
```

The verifier reads the six Git object manifest parts and checks **every original file's byte size and Git blob SHA-1**, with fail-closed missing, altered, symlink and path-collision detection. It does not check the `RELEASE_CANONICAL/` files against the base manifest (those were added *after* the base commit). The release commit SHA identifies those additional files via Git itself.

**SHA-256 of the outer ZIP is not preclaimed.** GitHub regenerates source archives and compression bytes may vary even for identical extracted content. The `--archive` option computes the actual downloaded ZIP SHA-256; retain it with the audit log. Git SHA-1 is the Git content identity and does not substitute for a stronger signed independent attestation.

## Replay H5 code, separately

```bash
python -m pip install -e '.[dev]' -e 'agents[ml]'
python -m pytest -q tests/dopa_closure_v2/test_h5_td_lambda.py
python -m pytest -q tests/dopa_closure_v2/test_h5_dopamine_checkpoint.py
python -m experiments.dopa_signal_validity.h5_td_lambda \
  --seed 19 --output /tmp/neosynaptex-h5-seed19.json
python scripts/verify_neuroai_offline.py
```

These commands are instructions for **future reproduction**, not claimed successful CI.

## Full Git history: outside source ZIP

To preserve all accessible branch references and complete Git object history, perform a separate mirror clone on a network-enabled system:

```bash
git clone --mirror https://github.com/neuron7x/neosynaptex.git neosynaptex.git
git -C neosynaptex.git fsck --full
git -C neosynaptex.git bundle create ../neosynaptex-all-refs.bundle --all
```

GitHub-generated ZIP snapshots **do not contain `.git/`** and thus cannot represent all Git history or every branch as a live tree. No local clone was possible in the packaging session (GitHub DNS/network access absent).

## Private ChatGPT transcript

A complete **verbatim chat export** requires the user's ChatGPT account data export and should not be committed to this public repository. The included `02_RESEARCH_CHAT_SCOPE.md` is a faithful **research decision reconstruction, not transcript completeness**.

Scientific delivery status remains **R&D H5 prototype / validation pending**, not production-certified.
