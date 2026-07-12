"""Report rendering for local and Streamlit demos."""

from __future__ import annotations

import json
from pathlib import Path

from ielts_scorer.schemas import ScoringReport


def render_markdown_report(report: ScoringReport) -> str:
    lines = [
        f"# IELTS Speaking Demo Report: {report.attempt_id}",
        "",
        f"Overall estimated IELTS-style band score: **{report.overall_band:.1f}**",
        "",
        "## Provider Provenance",
        "",
        f"- Audio source: `{report.provenance.audio_source}`",
        f"- ASR provider: `{report.provenance.asr_provider}`",
        f"- ASR mode: `{'Mock ASR transcript' if report.provenance.asr_is_mock else 'Real ASR transcript'}`",
        f"- Scoring provider: `{report.provenance.scoring_provider}`",
        f"- Scoring mode: `{'Rule-based mock scoring' if report.provenance.scoring_is_mock else 'Real model scoring'}`",
        f"- Pipeline mode: `{report.provenance.pipeline_mode}`",
        "",
        "## Dimension Scores",
        "",
        "| Dimension | Band | Evidence | Feedback |",
        "|---|---:|---|---|",
    ]
    labels = {
        "fluency_and_coherence": "Fluency and coherence",
        "lexical_resource": "Lexical resource",
        "grammatical_range_and_accuracy": "Grammatical range and accuracy",
        "pronunciation_intelligibility": "Pronunciation / intelligibility estimate",
    }
    for key, score in report.dimensions.items():
        evidence = "<br>".join(score.evidence)
        lines.append(f"| {labels[key]} | {score.band:.1f} | {evidence} | {score.feedback} |")
    lines.extend(
        [
            "",
            "## Transcript",
            "",
            report.transcript or "_No transcript text available._",
            "",
            "## Extracted Features",
            "",
            "```json",
            json.dumps(report.features.model_dump(mode="json"), indent=2, sort_keys=True),
            "```",
            "",
            "## Caveats",
            "",
        ]
    )
    lines.extend(f"- {caveat}" for caveat in report.caveats)
    lines.append("")
    return "\n".join(lines)


def write_report_files(report: ScoringReport, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{report.attempt_id}_report.json"
    markdown_path = output_dir / f"{report.attempt_id}_report.md"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    markdown_path.write_text(render_markdown_report(report), encoding="utf-8")
    return json_path, markdown_path
