# Experiments

Reproducible experiment runners. Each subdirectory is self-contained and
ships its own README and artefact set.

## Contents

- `lemma_1_verification/` — numerical verification of Lemma 1 (Kuramoto
  on dense graphs). Single runner: `verify_kuramoto_gamma_unity.py`.
  Output anchor: `evidence/lemma_1_numerical.json`.
- `lm_substrate/` — stateless-LLM γ derivation (GPT-4o-mini). Within-
  substrate falsification record (γ ≈ 0). See sub-README.
- `probe_dialogue_null/` — archived null result for the cumulative
  lexical/entropy dialogue adapter; AT battery rejects 0/5. Kept for
  guard-rail purposes only.
- `scaffolding_trap/` — agent-based-model dskill/dt analysis;
  `scaffolding_trap_finding.md` plus raw JSON and figure.
- `causal_topology/` — graph-similarity and motif analyses with
  `run_topology_experiment.py` driving the pipeline.
- `spectral_coherence/`, `spectral_coherence_v3/` — spectral battery
  variants (Welch, multitaper, wavelet coherence). v3 supersedes v1.
- `experiment_cards.py` — registry of experiment metadata used by other
  tooling.

## Notes

- Status / verdict for any γ-row referenced from these experiments is
  recorded canonically in `evidence/replications/registry.yaml`. If a
  per-experiment README and the registry disagree, the registry wins.
- Several experiments emit large JSON artefacts not committed to the
  repo; rerun the corresponding `run_*.py` to regenerate.
