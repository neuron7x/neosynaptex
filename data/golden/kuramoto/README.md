# Golden datasets — kuramoto

Small versioned fixtures for regression checks of indicator pipelines.

## Contents

- `indicator_macd_baseline.csv.meta.json` — metadata sidecar for the
  baseline MACD output (`dataset_id: indicator-macd-baseline-v1`,
  intended use: certification, forbidden use: live trading).

## Notes

The companion CSV file is generated on demand from the curated baseline
described in the metadata. New golden files should be added sparingly and
only with a corresponding `.meta.json` sidecar.
