# Inter-layer interface contracts (GAP-O-03)

Vertical hierarchy: **Layer 0 → GeoSync → BN-Syn → MFN⁺ → conclusion.**
No subsystem may consume another's output without the boundary passing its
contract test. Code `pf/interfaces.py`; tests
`tests/physics/test_interface_contracts.py`.

## GeoSync → BN-Syn

| field | output_type | units | shape | valid_range | sampling_dt | failure_mode |
|-------|-------------|-------|-------|-------------|-------------|--------------|
| θ | float array | radians | (N, T) | finite | 0.02 | non-finite → halt |
| R | scalar/t | dimensionless | (T,) | [0, 1] | 0.02 | out of range → halt |
| γ_PSD | float | dimensionless | scalar | finite | — | non-finite → halt |

Producer `integrate_kuramoto` + `order_parameter` + `psd_slope`; validator
`validate_geosync_output`.

## BN-Syn → MFN⁺

| field | output_type | units | valid_range | failure_mode |
|-------|-------------|-------|-------------|--------------|
| spike_rate | float | Hz | [0, 1000] | negative → halt |
| V | float array | mV | [−120, 60] | out of range → halt |
| ΔE_balance | float | dimensionless | < 0.01 | exceed → flag non-physical |

## MFN⁺ → conclusion

| field | output_type | units | valid_range | failure_mode |
|-------|-------------|-------|-------------|--------------|
| dominant_k | float | 1/length | ≈ k_c | mismatch → no Turing claim |
| pattern_field | float array | concentration | ≥ 0 | negative → halt |

**Rule:** each boundary has a contract test; a failing contract halts propagation
rather than emitting a downstream signal of unknown validity.
