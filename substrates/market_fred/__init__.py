"""FRED macro-economic substrate — γ-measurement on public-domain series.

Substrate class: ``market_macro``. See
``docs/SUBSTRATE_MEASUREMENT_TABLE.yaml`` entry ``fred_indpro``.

This substrate is intentionally minimal: it fetches a FRED CSV via
its public URL (no API key, public domain), computes the aperiodic
slope of the log-returns power spectrum, and runs the required null
families from ``docs/NULL_MODEL_HIERARCHY.md``.

All claims produced by this substrate are bound by
``docs/CLAIM_BOUNDARY.md §3.1`` and carry ``claim_status: measured``
only after at least one null family rejects the observed γ.
"""
