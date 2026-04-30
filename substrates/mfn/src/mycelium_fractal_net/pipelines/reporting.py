from __future__ import annotations

import hashlib
import html
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

torch = None  # loaded on demand, not at import time

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("mycelium-fractal-net")
except PackageNotFoundError:
    __version__ = "0.1.0"
from mycelium_fractal_net.analytics.morphology import compute_morphology_descriptor
from mycelium_fractal_net.artifact_bundle import (
    sha256_file,
    sign_artifacts,
    verify_artifact_signature,
)
from mycelium_fractal_net.core.causal_validation import validate_causal_consistency
from mycelium_fractal_net.core.compare import compare
from mycelium_fractal_net.core.detect import detect_anomaly
from mycelium_fractal_net.core.forecast import forecast_next
from mycelium_fractal_net.types.field import FieldSequence
from mycelium_fractal_net.types.report import AnalysisReport

SCHEMA_VERSION = "mfn-artifact-manifest-v2"


def _reject_traversal(p: str | Path) -> Path:
    """Defense-in-depth: reject paths with ``..`` segments.

    Output paths in this pipeline flow from operator-controlled config
    (``output_root`` argument), not from adversarial input. The guard
    below catches accidental traversal in misconfigured deployments.
    ``.resolve()`` was deliberately removed after PR #164 — it added new
    CodeQL py/path-injection sinks without closing the original alerts
    (CodeQL's barriers do not include ``Path.resolve()``). The original
    parameter→sink flow is dismissed in the security tab as
    not-exploitable under this admin-controlled threat model.
    """
    import os as _os

    raw = _os.fspath(p)
    if ".." in Path(raw).parts:
        raise ValueError(f"path traversal disallowed: {raw!r}")
    return Path(raw)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    safe = _reject_traversal(path)
    safe.parent.mkdir(parents=True, exist_ok=True)
    safe.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    safe = _reject_traversal(path)
    safe.parent.mkdir(parents=True, exist_ok=True)
    safe.write_text(text, encoding="utf-8")


def _ensure_history(sequence: FieldSequence) -> np.ndarray:
    return sequence.history if sequence.history is not None else sequence.field[None, :, :]


def _sha256_file(path: Path) -> str:
    safe = _reject_traversal(path)
    digest = hashlib.sha256()
    with safe.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_manifest(run_dir: Path, artifact_list: list[str]) -> dict[str, dict[str, Any]]:
    safe_root = _reject_traversal(run_dir)
    manifest: dict[str, dict[str, Any]] = {}
    for name in artifact_list:
        path = safe_root / name
        manifest[name] = {
            "bytes": int(path.stat().st_size),
            "sha256": _sha256_file(path),
            "path": name,
        }
    return manifest


def _config_hash(sequence: FieldSequence) -> str:
    spec_dict = (
        sequence.spec.to_dict()
        if sequence.spec is not None
        else {
            "grid_size": sequence.grid_size,
            "steps": sequence.num_steps,
            "seed": sequence.metadata.get("seed", 42),
        }
    )
    return hashlib.sha256(json.dumps(spec_dict, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def _git_sha(root: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        sha = proc.stdout.strip()
        return sha or "UNKNOWN"
    except Exception:
        return "UNKNOWN"


def _lock_hash(root: Path) -> str:
    lock = root / "uv.lock"
    if not lock.exists():
        return "UNKNOWN"
    return hashlib.sha256(lock.read_bytes()).hexdigest()


def _to_rgb(value: float, vmin: float, vmax: float) -> tuple[int, int, int]:
    if vmax <= vmin:
        t = 0.5
    else:
        t = max(0.0, min(1.0, (value - vmin) / (vmax - vmin)))
    r = int(255 * t)
    b = int(255 * (1.0 - t))
    g = int(255 * (1.0 - abs(t - 0.5) * 2.0) * 0.75)
    return r, g, b


def _svg_heatmap(array: np.ndarray, title: str) -> str:
    data = np.asarray(array, dtype=np.float64)
    if data.ndim != 2:
        raise ValueError("heatmap expects 2D array")
    rows, cols = data.shape
    cell = max(4, min(16, 320 // max(rows, cols)))
    margin_top = 28
    width = cols * cell
    height = rows * cell
    vmin = float(np.min(data))
    vmax = float(np.max(data))
    rects: list[str] = []
    for i in range(rows):
        for j in range(cols):
            r, g, b = _to_rgb(float(data[i, j]), vmin, vmax)
            rects.append(
                f'<rect x="{j * cell}" y="{margin_top + i * cell}" width="{cell}" height="{cell}" fill="rgb({r},{g},{b})"/>'
            )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height + margin_top + 24}" viewBox="0 0 {width} {height + margin_top + 24}">'
        f'<rect width="100%" height="100%" fill="#0f172a"/>'
        f'<text x="8" y="18" font-size="14" fill="#e2e8f0" font-family="monospace">{html.escape(title)}</text>'
        + "".join(rects)
        + f'<text x="8" y="{height + margin_top + 18}" font-size="11" fill="#94a3b8" font-family="monospace">min={vmin:.6f}, max={vmax:.6f}</text>'
        + "</svg>"
    )


def _svg_line(values: list[float], title: str, y_label: str) -> str:
    clean = [float(v) for v in values]
    if not clean:
        clean = [0.0]
    width = 420
    height = 180
    margin = 28
    vmin = min(clean)
    vmax = max(clean)
    span = (vmax - vmin) or 1.0
    points = []
    for idx, value in enumerate(clean):
        x = margin + (idx / max(1, len(clean) - 1)) * (width - 2 * margin)
        y = height - margin - ((value - vmin) / span) * (height - 2 * margin)
        points.append(f"{x:.1f},{y:.1f}")
    ticks = "".join(
        f'<line x1="{margin}" y1="{margin + t * (height - 2 * margin) / 4:.1f}" x2="{width - margin}" y2="{margin + t * (height - 2 * margin) / 4:.1f}" stroke="#334155" stroke-width="1"/>'
        for t in range(5)
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        f'<rect width="100%" height="100%" fill="#0f172a"/>'
        f'<text x="8" y="18" font-size="14" fill="#e2e8f0" font-family="monospace">{html.escape(title)}</text>'
        f"{ticks}"
        f'<polyline fill="none" stroke="#38bdf8" stroke-width="2" points="{" ".join(points)}"/>'
        f'<text x="8" y="{height - 8}" font-size="11" fill="#94a3b8" font-family="monospace">{html.escape(y_label)} | min={vmin:.4f}, max={vmax:.4f}</text>'
        f"</svg>"
    )


def _table_rows(mapping: dict[str, Any]) -> str:
    return "".join(
        f"<tr><th>{html.escape(str(k))}</th><td>{html.escape(str(v))}</td></tr>"
        for k, v in mapping.items()
    )


def _build_report_html(
    run_id: str,
    summary: dict[str, Any],
    descriptor: dict[str, Any],
    detection: dict[str, Any],
    forecast: dict[str, Any],
    comparison: dict[str, Any],
    optional_artifacts: dict[str, str],
) -> str:
    cards = [
        ("Run Summary", summary),
        (
            "Detection",
            {
                "label": detection.get("label"),
                "score": f"{float(detection.get('score', 0.0)):.4f}",
                "confidence": f"{float(detection.get('confidence', 0.0)):.4f}",
                "top_features": ", ".join(detection.get("top_contributing_features", [])),
            },
        ),
        (
            "Comparison",
            {
                "label": comparison.get("label"),
                "distance": f"{float(comparison.get('distance', 0.0)):.6f}",
                "cosine_similarity": f"{float(comparison.get('cosine_similarity', 0.0)):.6f}",
                "nearest_analog": comparison.get("nearest_structural_analog"),
            },
        ),
        (
            "Descriptor Snapshot",
            {
                "descriptor_version": descriptor.get("descriptor_version"),
                "embedding_dim": len(descriptor.get("embedding", [])),
                "fractal_dimension": f"{float(descriptor.get('features', {}).get('D_box', 0.0)):.4f}",
                "activity": f"{float(descriptor.get('features', {}).get('f_active', 0.0)):.4f}",
            },
        ),
    ]
    sections = "".join(
        f'<section class="card"><h2>{html.escape(title)}</h2><table>{_table_rows(payload)}</table></section>'
        for title, payload in cards
    )
    visuals = "".join(
        f'<figure class="viz"><img src="{html.escape(path)}" alt="{html.escape(label)}"/><figcaption>{html.escape(label)}</figcaption></figure>'
        for label, path in optional_artifacts.items()
        if path.endswith(".svg")
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>MFN Report {html.escape(run_id)}</title>
<style>
body {{ font-family: Inter, system-ui, sans-serif; margin: 0; padding: 24px; background: #020617; color: #e2e8f0; }}
h1 {{ margin-top: 0; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 16px; }}
.card {{ background: #0f172a; border: 1px solid #1e293b; border-radius: 16px; padding: 16px; box-shadow: 0 6px 24px rgba(0,0,0,.25); }}
.card h2 {{ margin: 0 0 12px 0; font-size: 18px; }}
table {{ width: 100%; border-collapse: collapse; }}
th, td {{ text-align: left; padding: 6px 8px; border-bottom: 1px solid #1e293b; font-size: 13px; }}
.viz-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 18px; margin-top: 18px; }}
.viz {{ background: #0f172a; border: 1px solid #1e293b; border-radius: 16px; padding: 12px; margin: 0; }}
.viz img {{ width: 100%; height: auto; display: block; background: #0f172a; border-radius: 12px; }}
.viz figcaption {{ margin-top: 8px; font-size: 13px; color: #94a3b8; }}
small a {{ color: #38bdf8; }}
</style>
</head>
<body>
<h1>Morphology-aware Field Intelligence Engine</h1>
<p>Run <strong>{html.escape(run_id)}</strong> — deterministic structural analytics report with canonical artifacts.</p>
<div class="grid">{sections}</div>
<div class="viz-grid">{visuals}</div>
<p><small>Forecast method: {html.escape(str(forecast.get("method", "n/a")))} | Generated by engine {html.escape(str(summary.get("engine_version", "n/a")))}</small></p>
</body>
</html>
"""


def build_analysis_report(
    sequence: FieldSequence,
    output_root: str | Path,
    *,
    horizon: int = 8,
    comparison_sequence: FieldSequence | None = None,
    export_symbolic_context: bool = True,
) -> AnalysisReport:
    import logging as _log

    _report_logger = _log.getLogger(__name__)

    descriptor = compute_morphology_descriptor(sequence)
    try:
        detection = detect_anomaly(sequence)
    except Exception:
        _report_logger.warning("Detection failed, using fallback", exc_info=True)
        from mycelium_fractal_net.types.detection import AnomalyEvent

        detection = AnomalyEvent(score=0.0, label="error", confidence=0.0)
    try:
        forecast = forecast_next(sequence, horizon=horizon)
    except Exception:
        _report_logger.warning("Forecast failed, using fallback", exc_info=True)
        from mycelium_fractal_net.types.forecast import ForecastResult

        forecast = ForecastResult(horizon=horizon)
    forecast_final = (
        np.asarray(forecast.predicted_states[-1], dtype=np.float64)
        if forecast.predicted_states
        else sequence.field
    )
    auto_comparison_sequence = FieldSequence(
        field=forecast_final,
        history=None,
        spec=sequence.spec,
        metadata={"derived_from": "forecast"},
    )
    comparison_target = comparison_sequence or auto_comparison_sequence
    comparison = compare(sequence, comparison_target)

    project_root = Path(__file__).resolve().parents[3]
    timestamp_now = datetime.now(timezone.utc)
    seed = int(sequence.metadata.get("seed", sequence.spec.seed if sequence.spec else 42))
    run_id = timestamp_now.strftime("run_%Y%m%dT%H%M%S_%fZ") + f"_s{seed}"
    safe_root = _reject_traversal(output_root)
    run_dir = safe_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    history = _ensure_history(sequence)
    np.save(run_dir / "field.npy", sequence.field)
    np.save(run_dir / "history.npy", history)

    descriptor_dict = descriptor.to_dict()
    detection_dict = detection.to_dict()
    forecast_dict = forecast.to_dict()
    comparison_dict = comparison.to_dict()

    _write_json(
        run_dir / "config.json",
        {} if sequence.spec is None else sequence.spec.to_dict(),
    )
    _write_json(run_dir / "descriptor.json", descriptor_dict)
    _write_json(run_dir / "detection.json", detection_dict)
    _write_json(run_dir / "forecast.json", forecast_dict)
    _write_json(run_dir / "comparison.json", comparison_dict)

    # Core artifacts: created before manifest. Manifest/causal are added after.
    core_artifacts = [
        "config.json",
        "field.npy",
        "history.npy",
        "descriptor.json",
        "detection.json",
        "forecast.json",
        "comparison.json",
        "report.md",
    ]
    # Full artifact list including self-referential ones
    artifact_list = [*core_artifacts, "manifest.json", "causal_validation.json"]

    summary = {
        "grid_size": sequence.grid_size,
        "steps": sequence.num_steps,
        "descriptor_version": descriptor.version,
        "anomaly_label": detection.label,
        "anomaly_score": detection.score,
        "regime_label": detection.regime.label if detection.regime else "n/a",
        "forecast_horizon": forecast.horizon,
        "forecast_method": forecast.method,
        "comparison_label": comparison.label,
        "comparison_distance": comparison.distance,
        "engine_version": __version__,
        "seed": seed,
        "runtime_hash": sequence.runtime_hash,
        "git_sha": _git_sha(project_root),
        "lock_hash": _lock_hash(project_root),
        "python_version": platform.python_version(),
        "torch_version": getattr(torch, "__version__", "unavailable"),
    }

    optional_artifacts = {
        "field_heatmap": "field.svg",
        "history_mean_heatmap": "history_mean.svg",
        "forecast_final_heatmap": "forecast_final.svg",
        "comparison_delta_heatmap": "comparison_delta.svg",
        "forecast_mean_trajectory": "trajectory.svg",
        "report_html": "report.html",
        "summary_json": "summary.json",
        "symbolic_context": "symbolic_context.json",
    }

    report = AnalysisReport(
        run_id=run_id,
        spec=sequence.spec,
        sequence=sequence,
        descriptor=descriptor,
        detection=detection,
        forecast=forecast,
        comparison=comparison,
        artifacts={
            "config": "config.json",
            "field": "field.npy",
            "history": "history.npy",
            "descriptor": "descriptor.json",
            "detection": "detection.json",
            "forecast": "forecast.json",
            "comparison": "comparison.json",
            "report": "report.md",
            "manifest": "manifest.json",
            **optional_artifacts,
        },
        metadata={
            "created_at": timestamp_now.isoformat(),
            "summary": summary,
            "schema_version": SCHEMA_VERSION,
            "engine_version": __version__,
            "seed": seed,
            "config_hash": _config_hash(sequence),
            "git_sha": _git_sha(project_root),
            "lock_hash": _lock_hash(project_root),
            "python_version": platform.python_version(),
            "torch_version": getattr(torch, "__version__", "unavailable"),
        },
    )

    markdown_lines = [
        "# Morphology-aware Field Intelligence Engine Report",
        "",
        f"- Run ID: {run_id}",
        f"- Engine version: {__version__}",
        f"- Grid size: {sequence.grid_size}",
        f"- Steps: {sequence.num_steps}",
        f"- Descriptor version: {descriptor.version}",
        f"- Anomaly label: {detection.label} (score={detection.score:.4f})",
        f"- Regime label: {detection.regime.label if detection.regime else 'n/a'}",
        f"- Forecast horizon: {forecast.horizon}",
        f"- Forecast method: {forecast.method}",
        f"- Comparison label: {comparison.label} (distance={comparison.distance:.6f}, cosine={comparison.cosine_similarity:.6f})",
        "",
        "## Visual artifacts",
        "",
        "- report.html",
        "- field.svg",
        "- history_mean.svg",
        "- forecast_final.svg",
        "- comparison_delta.svg",
        "- trajectory.svg",
    ]
    _write_text(run_dir / "report.md", "\n".join(markdown_lines) + "\n")

    comparison_field = (
        comparison_target.history[-1]
        if comparison_target.history is not None
        else comparison_target.field
    )
    delta_field = forecast_final - comparison_field
    _write_text(run_dir / "field.svg", _svg_heatmap(sequence.field, "Final field"))
    _write_text(
        run_dir / "history_mean.svg",
        _svg_heatmap(np.mean(history, axis=0), "History mean field"),
    )
    _write_text(
        run_dir / "forecast_final.svg",
        _svg_heatmap(forecast_final, "Forecast final field"),
    )
    _write_text(
        run_dir / "comparison_delta.svg",
        _svg_heatmap(delta_field, "Forecast vs comparison delta"),
    )
    trajectory_values = [
        float(step.get("field_mean_mV", 0.0)) for step in forecast.descriptor_trajectory
    ]
    _write_text(
        run_dir / "trajectory.svg",
        _svg_line(trajectory_values, "Forecast mean potential trajectory", "field_mean_mV"),
    )
    _write_json(run_dir / "summary.json", summary)
    _write_text(
        run_dir / "report.html",
        _build_report_html(
            run_id,
            summary,
            descriptor_dict,
            detection_dict,
            forecast_dict,
            comparison_dict,
            optional_artifacts,
        ),
    )
    if export_symbolic_context:
        symbolic_context = report.to_symbolic_context(
            manifest_hashes={
                "field": sha256_file(run_dir / "field.npy"),
                "history": sha256_file(run_dir / "history.npy"),
                "forecast": sha256_file(run_dir / "forecast.json"),
                "comparison": sha256_file(run_dir / "comparison.json"),
            }
        )
        _write_json(run_dir / "symbolic_context.json", symbolic_context.to_dict())

    initial_manifest = {
        "run_id": run_id,
        "engine_version": __version__,
        "schema_version": SCHEMA_VERSION,
        "seed": seed,
        "config_hash": _config_hash(sequence),
        "timestamp": timestamp_now.isoformat(),
        "artifact_list": artifact_list,
        "git_sha": _git_sha(project_root),
        "lock_hash": _lock_hash(project_root),
        "python_version": platform.python_version(),
        "torch_version": getattr(torch, "__version__", "unavailable"),
        "optional_artifact_list": list(optional_artifacts.values()),
        "report": report.to_dict(),
    }
    manifest = {
        **initial_manifest,
        "artifact_manifest": _artifact_manifest(run_dir, core_artifacts),
        "optional_artifact_manifest": _artifact_manifest(
            run_dir, list(optional_artifacts.values())
        ),
        "crypto_audit_log": "crypto_audit.jsonl",
    }
    _write_json(run_dir / "manifest.json", manifest)
    audit_log = run_dir / "crypto_audit.jsonl"
    signed_paths = [run_dir / "report.md", run_dir / "manifest.json"]
    sign_artifacts(
        signed_paths,
        config_path=project_root / "configs" / "crypto.yaml",
        audit_log=audit_log,
    )
    # Enforce: verify immediately after signing (sign-then-verify contract)
    for signed_path in signed_paths:
        if not verify_artifact_signature(signed_path, audit_log=audit_log):
            raise RuntimeError(f"Signature verification failed for {signed_path.name}")

    # Causal Validation Gate — verify every conclusion follows from data & invariants
    causal_result = validate_causal_consistency(
        sequence=sequence,
        descriptor=report.descriptor,
        detection=report.detection,
        forecast=report.forecast,
        comparison=report.comparison,
    )
    _write_json(run_dir / "causal_validation.json", causal_result.to_dict())

    # Strict mode: block publication only on error/fatal violations (not warnings)
    if causal_result.error_count > 0:
        errors = [r for r in causal_result.violations if r.severity.value in ("error", "fatal")]
        raise RuntimeError(
            f"Causal validation failed ({causal_result.decision.value}): "
            f"{len(errors)} error(s). First: [{errors[0].rule_id}] {errors[0].message}"
        )

    return report
