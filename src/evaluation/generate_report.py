"""Build the markdown evaluation report."""

import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.evaluation.evaluate import load_gold, load_predictions, compute_metrics, get_error_examples


def generate_report(gold_path: str, preds_path: str, output_path: str):
    gold = load_gold(gold_path)
    preds = load_predictions(preds_path, relevant_element_ids=set(gold.keys()))
    per_type, overall = compute_metrics(gold, preds)
    fps, fns = get_error_examples(gold, preds, max_examples=20)

    lines = []
    lines.append("# PII Redaction Tool -- Evaluation Report")
    lines.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"\nSample size: {len(gold)} document elements "
                 f"(targeted + random, see `select_sample.py`)")

    lines.append("\n## Metric Definitions")
    lines.append(
        "- **Precision** = TP / (TP + FP) -- of what we redacted, how much was really PII\n"
        "- **Recall** = TP / (TP + FN) -- of what was really PII, how much did we catch\n"
        "- **F1** = harmonic mean of precision and recall\n"
        "- **Accuracy** = TP / (TP + FP + FN) -- the standard substitute for classification "
        "accuracy in span-extraction tasks (there's no meaningful 'true negative' class here). "
        "This is the Jaccard overlap between the predicted and gold entity sets."
    )

    lines.append("\n## Results by Entity Type")
    lines.append("\n| Entity Type | TP | FP | FN | Precision | Recall | F1 | Accuracy |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for etype, m in per_type.items():
        lines.append(
            f"| {etype} | {m['tp']} | {m['fp']} | {m['fn']} | "
            f"{m['precision']:.2f} | {m['recall']:.2f} | {m['f1']:.2f} | {m['accuracy']:.2f} |"
        )
    lines.append(
        f"| **OVERALL** | {overall['tp']} | {overall['fp']} | {overall['fn']} | "
        f"**{overall['precision']:.2f}** | **{overall['recall']:.2f}** | "
        f"**{overall['f1']:.2f}** | **{overall['accuracy']:.2f}** |"
    )

    lines.append("\n## Sample False Positives")
    lines.append("(System flagged as PII; human annotator disagreed)\n")
    if fps:
        for eid, etype, text in fps:
            lines.append(f"- **[{etype}]** {text!r} — `{eid}`")
    else:
        lines.append("_None found in the annotated sample._")

    lines.append("\n## Sample False Negatives")
    lines.append("(Real PII the system missed)\n")
    if fns:
        for eid, etype, text in fns:
            lines.append(f"- **[{etype}]** {text!r} — `{eid}`")
    else:
        lines.append("_None found in the annotated sample._")

    lines.append("\n## Known Limitations (found during development, not just eval)")
    lines.append(
        "- **DATE_OF_BIRTH**: no confirmed DOBs exist in this document (expected for an "
        "Indian corporate filing), so recall for this category is validated only against "
        "synthetic test cases, not real occurrences.\n"
        "- **NER cross-category confusion**: spaCy occasionally mislabels short "
        "initials-based names (e.g. 'DM Shetty') as ORGANIZATION instead of PERSON -- "
        "a known weakness of pretrained NER on non-Western name patterns.\n"
        "- **NER span-boundary truncation**: multi-word institutional names are "
        "occasionally clipped (e.g. a truncated span of 'Securities and Exchange Board "
        "of India'), which can cause an allowlisted entity to escape the filter under "
        "its truncated form.\n"
        "- **Long-tail legal defined-terms**: RHPs capitalize many generic legal terms "
        "('the Offer', 'the Syndicate') that read as proper nouns to NER; our stoplist "
        "covers observed cases, not the category exhaustively.\n"
        "- **Cross-cell/cross-row context**: our DOB context-boosting fix handles "
        "label/value pairs in the same table row, but not other layouts (e.g. label and "
        "value in different rows)."
    )

    Path(output_path).write_text("\n".join(lines))
    print(f"Report written to: {output_path}")


if __name__ == "__main__":
    gold_path = sys.argv[1] if len(sys.argv) > 1 else "evaluation/sample_for_annotation.json"
    preds_path = sys.argv[2] if len(sys.argv) > 2 else "output/detections_log.json"
    output_path = sys.argv[3] if len(sys.argv) > 3 else "evaluation/evaluation_report.md"
    generate_report(gold_path, preds_path, output_path)