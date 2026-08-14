"""Evaluate predictions against the gold spans."""

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

ALL_REQUIRED_TYPES = [
    "PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "ORGANIZATION", "LOCATION",
    "DATE_OF_BIRTH", "US_SSN", "CREDIT_CARD", "IP_ADDRESS",
]


@dataclass
class Counts:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    @property
    def precision(self):
        return self.tp / (self.tp + self.fp) if (self.tp + self.fp) else None

    @property
    def recall(self):
        return self.tp / (self.tp + self.fn) if (self.tp + self.fn) else None

    @property
    def f1(self):
        p, r = self.precision, self.recall
        if p is None or r is None or (p + r) == 0:
            return None
        return 2 * p * r / (p + r)

    @property
    def accuracy(self):
        denom = self.tp + self.fp + self.fn
        return self.tp / denom if denom else None


def _overlaps(a_start, a_end, b_start, b_end) -> bool:
    return max(a_start, b_start) < min(a_end, b_end)


def _match_element(gold_entities, predicted_entities):
    candidates = []
    for gi, g in enumerate(gold_entities):
        for pi, p in enumerate(predicted_entities):
            if g["entity_type"] != p["entity_type"]:
                continue
            if _overlaps(g["start"], g["end"], p["start"], p["end"]):
                overlap_len = min(g["end"], p["end"]) - max(g["start"], p["start"])
                candidates.append((overlap_len, gi, pi))

    candidates.sort(key=lambda x: x[0], reverse=True)
    used_gold, used_pred, matched = set(), set(), []
    for _, gi, pi in candidates:
        if gi in used_gold or pi in used_pred:
            continue
        used_gold.add(gi)
        used_pred.add(pi)
        matched.append((gi, pi))

    unmatched_gold = [i for i in range(len(gold_entities)) if i not in used_gold]
    unmatched_pred = [i for i in range(len(predicted_entities)) if i not in used_pred]
    return matched, unmatched_gold, unmatched_pred


def evaluate(gold_by_id: dict, predictions_by_id: dict) -> dict:
    per_type = defaultdict(Counts)
    fp_examples = defaultdict(list)
    fn_examples = defaultdict(list)
    types_present_in_gold = set()
    types_present_in_predictions = set()

    all_ids = set(gold_by_id) | set(predictions_by_id)
    for element_id in all_ids:
        gold = gold_by_id.get(element_id, [])
        pred = predictions_by_id.get(element_id, [])

        for g in gold:
            types_present_in_gold.add(g["entity_type"])
        for p in pred:
            types_present_in_predictions.add(p["entity_type"])

        matched, unmatched_gold, unmatched_pred = _match_element(gold, pred)

        for gi, pi in matched:
            per_type[gold[gi]["entity_type"]].tp += 1

        for gi in unmatched_gold:
            g = gold[gi]
            per_type[g["entity_type"]].fn += 1
            fn_examples[g["entity_type"]].append({"element_id": element_id, "text": g.get("text", "")})

        for pi in unmatched_pred:
            p = pred[pi]
            per_type[p["entity_type"]].fp += 1
            fp_examples[p["entity_type"]].append({
                "element_id": element_id, "text": p.get("text", ""), "score": p.get("score"),
            })

    overall = Counts()
    for c in per_type.values():
        overall.tp += c.tp
        overall.fp += c.fp
        overall.fn += c.fn

    per_type_report = {}
    for etype in ALL_REQUIRED_TYPES:
        has_gold = etype in types_present_in_gold
        has_pred = etype in types_present_in_predictions
        c = per_type.get(etype, Counts())

        if not has_gold and not has_pred:
            # Nothing to score for this type.
            per_type_report[etype] = {
                "tp": 0, "fp": 0, "fn": 0,
                "precision": "N/A", "recall": "N/A", "f1": "N/A", "accuracy": "N/A",
                "note": "no real instances in source document, and detector produced no predictions",
            }
        elif has_gold and c.tp == 0 and c.fn == 0:
            # Negative controls only.
            per_type_report[etype] = {
                "tp": c.tp, "fp": c.fp, "fn": c.fn,
                "precision": c.precision, "recall": "N/A", "f1": "N/A",
                "accuracy": c.accuracy,
                "note": "no real instances of this type in source document; "
                        "gold entries are negative controls only (precision/FP still valid)",
            }
        else:
            per_type_report[etype] = {
                "tp": c.tp, "fp": c.fp, "fn": c.fn,
                "precision": c.precision, "recall": c.recall, "f1": c.f1, "accuracy": c.accuracy,
            }

    return {
        "per_type": per_type_report,
        "overall": {
            "tp": overall.tp, "fp": overall.fp, "fn": overall.fn,
            "precision": overall.precision, "recall": overall.recall,
            "f1": overall.f1, "accuracy": overall.accuracy,
        },
        "fp_examples": {k: v[:10] for k, v in fp_examples.items()},
        "fn_examples": {k: v[:10] for k, v in fn_examples.items()},
    }


def _load_entity_map(path: str) -> dict:
    data = json.loads(Path(path).read_text())
    result = {}
    for item in data:
        key = "gold_entities" if "gold_entities" in item else "predicted_entities"
        result[item["element_id"]] = item[key]
    return result


def run(gold_path: str, predictions_path: str, output_path: str):
    gold_by_id = _load_entity_map(gold_path)
    predictions_by_id = _load_entity_map(predictions_path)
    report = evaluate(gold_by_id, predictions_by_id)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(json.dumps(report, indent=2, ensure_ascii=False))

    print(f"Evaluation written -> {output_path}\n")
    print(f"{'Type':<16} {'TP':>4} {'FP':>4} {'FN':>4} {'Precision':>10} {'Recall':>10} {'F1':>10} {'Accuracy':>10}")
    for etype, m in report["per_type"].items():
        def fmt(x):
            return x if isinstance(x, str) else f"{x:.2%}"
        print(f"{etype:<16} {m['tp']:>4} {m['fp']:>4} {m['fn']:>4} "
              f"{fmt(m['precision']):>10} {fmt(m['recall']):>10} {fmt(m['f1']):>10} {fmt(m['accuracy']):>10}")

    o = report["overall"]
    print(f"\n{'OVERALL':<16} {o['tp']:>4} {o['fp']:>4} {o['fn']:>4} "
          f"{o['precision']:.2%} {o['recall']:.2%} {o['f1']:.2%} {o['accuracy']:.2%}")

    return report


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", default="evaluation/evaluation_dataset.json")
    parser.add_argument("--predictions", default="evaluation/predictions.json")
    parser.add_argument("--out", default="evaluation/eval_results.json")
    args = parser.parse_args()
    run(args.gold, args.predictions, args.out)