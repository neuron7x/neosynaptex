"""Physical-fidelity verification protocol (NFI-GAP-001 corrective sequence).

This package converts the audited *Physical Fidelity Plan v1.0* from a research
proposal template into an *executable* VVUQ protocol (ASME V&V 10-2019).

Every public function here is either:

* an **analytic reference** (a closed-form physical fact with a literature
  citation), or
* a **falsifiable verifier** that compares a measured quantity against such a
  reference and returns a typed verdict.

No function in this package emits a science claim. Outputs are *admissibility /
infrastructure* measurements only (see ``scoring.ScoreCard``): they say whether
the apparatus reproduces known physics, not whether any hypothesis about the
world is true.

Gap → module map (NFI-GAP-001 Section 9 minimum corrective sequence):

==========  =================================  ==========================
Gap         Corrective artifact                Module
==========  =================================  ==========================
GAP-O-01    scoring oracle S, baseline S0      ``scoring``, ``baseline``
GAP-O-02    Kuramoto / discrete-Ricci object   ``dynamics``
GAP-O-03    inter-subsystem interface spec     ``specs/interfaces.md``
GAP-M-01    AdEx Q10 (no Boltzmann)            ``adex_q10``
GAP-M-03    Turing Jacobian + critical ratio   ``turing``
GAP-M-04    parabolic vs hyperbolic stability  ``stability``
GAP-M-05    regime-conditioned MLE             ``stability``
GAP-E-01    parameter-prior Monte-Carlo UQ     ``uq``
GAP-E-02    H0/H1 hypothesis register          ``hypotheses``
GAP-P-03    open-system energy balance         ``energy``
GAP-C-01    gamma_PSD = 2H + 1 contract        ``spectral``
==========  =================================  ==========================
"""

from __future__ import annotations

__all__ = [
    "dynamics",
    "spectral",
    "stability",
    "turing",
    "adex_q10",
    "energy",
    "uq",
    "hypotheses",
    "scoring",
    "baseline",
]

__version__ = "1.0.0"
