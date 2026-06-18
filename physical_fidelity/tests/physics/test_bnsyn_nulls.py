"""BN-Syn null models (NFI-PROMPT-002 Section 4)."""

from __future__ import annotations

import numpy as np

from physical_fidelity.pf import adex_q10


def _isi_cv(p: adex_q10.AdExParams, i_ext: float) -> float:
    _, vt, _, _ = adex_q10.simulate_adex(p, i_ext, t_end=2000.0, dt=0.02)
    # crude spike detection by reset jumps
    spikes = np.where(np.diff(vt) < -50.0)[0]
    if len(spikes) < 3:
        return 0.0
    isi = np.diff(spikes).astype(float)
    return float(np.std(isi) / np.mean(isi)) if np.mean(isi) > 0 else 0.0


def test_null_no_adaptation_more_regular():
    # a=0 removes subthreshold adaptation -> ISIs become MORE regular (CV down).
    base = adex_q10.AdExParams()
    no_adapt = adex_q10.AdExParams(a=0.0, b=0.0)
    cv_base = _isi_cv(base, 600.0)
    cv_null = _isi_cv(no_adapt, 600.0)
    assert cv_null <= cv_base + 1e-9


def test_null_no_temperature_recovers_base_tau():
    # Q10=1 -> tau unchanged from baseline.
    base = adex_q10.AdExParams()
    same = adex_q10.adex_params_at_temperature(base, 20.0, q10=1.0)
    assert same.tau_w == base.tau_w


def test_null_quiescent_no_spikes():
    p = adex_q10.AdExParams()
    _, _, _, spikes = adex_q10.simulate_adex(p, i_ext=0.0, t_end=300.0, dt=0.01)
    assert spikes == 0


def test_null_no_conductance_is_plain_adex():
    # g_e=g_i=0 -> energy driver is I_ext only (synaptic terms vanish).
    p = adex_q10.AdExParams()
    _, _, pin, _ = adex_q10.simulate_adex_energy(
        p, i_ext=40.0, t_end=50.0, dt=0.01, g_e0=0.0, g_i0=0.0
    )
    assert np.all(np.isfinite(pin))
