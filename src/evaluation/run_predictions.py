"""Run detection on the evaluation dataset."""

import argparse
import json
from pathlib import Path

from src.extractor import extract_text_elements
from src.pii_engine import build_analyzer_engine, analyze_text
from src.redactor import _resolve_overlaps


def run_predictions(docx_path: str, dataset_path: str, output_path: str, score_threshold: float = 0.35):
    dataset = json.loads(Path(dataset_path).read_text())
    target_ids = {item["element_id"] for item in dataset}

    elements = extract_text_elements(docx_path)
    elements_by_id = {el.element_id: el for el in elements}

    missing = target_ids - elements_by_id.keys()
    if missing:
        print(f"WARNING: {len(missing)} element_ids from the dataset were not found in "
              f"the current document extraction (document may have changed): "
              f"{sorted(missing)[:5]}...")

    analyzer = build_analyzer_engine()
    predictions = []

    for element_id in target_ids:
        el = elements_by_id.get(element_id)
        if el is None:
            continue

        extra_context = el.row_context.lower().split() if el.row_context else None
        raw_results = analyze_text(analyzer, el.text, score_threshold, context=extra_context)
        resolved = _resolve_overlaps(raw_results)

        predictions.append({
            "element_id": element_id,
            "text": el.text,
            "predicted_entities": [
                {
                    "entity_type": r.entity_type,
                    "text": el.text[r.start:r.end],
                    "start": r.start,
                    "end": r.end,
                    "score": r.score,
                }
                for r in resolved
            ],
        })

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(json.dumps(predictions, indent=2, ensure_ascii=False))
    print(f"Wrote predictions for {len(predictions)} elements -> {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--docx", default="data/input/Red_Herring_Prospectus.docx")
    parser.add_argument("--dataset", default="evaluation/evaluation_dataset.json")
    parser.add_argument("--out", default="evaluation/predictions.json")
    parser.add_argument("--threshold", type=float, default=0.35)
    args = parser.parse_args()
    run_predictions(args.docx, args.dataset, args.out, args.threshold)