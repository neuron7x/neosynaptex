# geosync-accel

PyO3 Rust extension that provides accelerated kernels for the
γ-scaling pipeline. Imported from Python via `core/accel.py`; falls back
to the pure-numpy implementation when the extension is not built.

## Contents

- `src/lib.rs` — PyO3 module entry point.
- `src/gamma_kernel.rs` — Theil–Sen regression and bootstrap kernel.
- `src/hilbert.rs` — Hilbert-curve spatial reordering helper.
- `src/dlpack.rs` — DLPack tensor exchange via `PyCapsule`.
- `src/arrow_ffi.rs` — Arrow C-Data interface bindings.
- `src/prefetch.rs` — cache-line aligned helper structures.
- `src/io_uring_bridge.rs` — io_uring wrapper (Linux-only).
- `benches/gamma_kernel.rs` — criterion benchmark for the γ kernel.
- `Cargo.toml`, `pyproject.toml` — build manifests (the latter for
  `maturin`).

## Requirements

- Rust toolchain (stable).
- Python ≥ 3.10 with `maturin` for the develop install.
- io_uring features require a Linux kernel that supports them; the build
  otherwise still produces the SIMD kernels and tensor-exchange shims.

## Build

```bash
cd core/rust/geosync-accel
pip install maturin
maturin develop --release
```

Or, for library-only tests:

```bash
cargo test
cargo bench   # criterion bench under benches/
```

## Usage

The Python side is exposed by `core/accel.py`:

```python
from core.accel import compute_gamma_accel
```

The Python wrapper auto-selects the Rust backend if `geosync_accel` is
importable and falls back to the pure-numpy path otherwise.

## Notes

- Performance numbers (PGO/BOLT-optimized speed-ups) are not pinned to a
  benchmark artefact in this repo; treat them as build-time targets, not
  measured claims (unverified).
- No GPU backend is shipped here.
