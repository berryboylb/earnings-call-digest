"""Writes the evaluation as eval.json and eval.md, and the headline for the console."""

from pathlib import Path

from constants.evaluation import ANCHOR_PREVIEW_LENGTH, HELD_BACK, MATCHING_NOTE, NOTES
from schema.evaluation import Evaluation


def headline_lines(evaluation: Evaluation) -> list[str]:
    headline = evaluation.headline
    figures, guidance, risks = headline.coverage["figure"], headline.coverage["guidance"], headline.coverage["risk"]
    lines = [
        f"Correct: {headline.correct_items}/{headline.matched_items} verified figures and guidance that match the key "
        "have every field right",
        f"Coverage: figures {figures[0]}/{figures[1]}, guidance {guidance[0]}/{guidance[1]}, "
        f"risks {risks[0]}/{risks[1]}",
        f"Guidance qualifiers captured: {headline.qualifiers_captured}/{headline.qualifiers_total}",
        f"must_not violations: {headline.violations}",
    ]
    for violation in evaluation.must_not_violations:
        lines.append(f"  - {violation.item_id} ({violation.kind}) {violation.item_value}: {violation.reason}")
    lines.append(f"Gate: false accepts = {headline.false_accepts} (verified but wrong); "
                 f"false rejects = {headline.false_rejects} (correct items held back)")
    return lines


def write_reports(evaluation: Evaluation, folder: Path) -> list[Path]:
    json_path = folder / "eval.json"
    json_path.write_text(evaluation.model_dump_json(indent=2), encoding="utf-8")
    md_path = folder / "eval.md"
    md_path.write_text(_markdown(evaluation), encoding="utf-8")
    return [json_path, md_path]


def _markdown(evaluation: Evaluation) -> str:
    lines = ["## Headline", ""]
    lines += [f"- {line}" if not line.startswith("  ") else line for line in headline_lines(evaluation)]

    lines += ["", "## Every answer-key entry", "",
              "| kind | anchor | expected | outcome | item id |",
              "| --- | --- | --- | --- | --- |"]
    for entry in evaluation.entries:
        outcome = entry.outcome
        if entry.outcome == HELD_BACK and entry.gate_reasons:
            outcome += ": " + "; ".join(entry.gate_reasons)
        if entry.qualifier_captured is not None:
            outcome += f" (qualifier {'captured' if entry.qualifier_captured else 'not captured'})"
        cells = [entry.kind, entry.anchor[:ANCHOR_PREVIEW_LENGTH], entry.expected, outcome, entry.item_id or "-"]
        lines.append("| " + " | ".join(_cell(cell) for cell in cells) + " |")

    lines += ["", "## Unlabelled extras", ""]
    if evaluation.unlabelled_extras:
        for extra in evaluation.unlabelled_extras:
            lines.append(f"- {extra.item_id} ({extra.kind}): {extra.description}")
    else:
        lines.append("None.")

    lines += ["", "## Notes", "", NOTES, "", MATCHING_NOTE, ""]
    return "\n".join(lines)


def _cell(text: str) -> str:
    return text.replace("|", "\\|")
