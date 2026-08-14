"""Main redaction pipeline."""

from dataclasses import dataclass, asdict
import json
from pathlib import Path

from src.extractor import extract_text_elements, load_document, _walk
from src.pii_engine import build_analyzer_engine, analyze_text
from src.fake_generator import FakeValueGenerator
from src.docx_writer import set_paragraph_text

@dataclass
class Detection:
    element_id: str
    entity_type: str
    original_text: str
    fake_text: str
    score: float
    context: str


def _resolve_overlaps(results):
    """Keep the highest-scoring overlapping span."""
    by_score_desc = sorted(results, key=lambda r: r.score, reverse=True)
    selected = []
    for r in by_score_desc:
        overlaps_existing = any(
            not (r.end <= s.start or r.start >= s.end) for s in selected
        )
        if not overlaps_existing:
            selected.append(r)
    return sorted(selected, key=lambda r: r.start)


def _redact_paragraph_text(text: str, results, fake_gen: FakeValueGenerator):
    """Apply replacements right-to-left so offsets stay valid."""
    detections = []
    new_text = text
    for r in reversed(results):  # already start-ascending; reversed = descending
        original_slice = text[r.start:r.end]
        fake_value = fake_gen.get_fake(original_slice, r.entity_type)
        new_text = new_text[: r.start] + fake_value + new_text[r.end :]
        detections.append((r.entity_type, original_slice, fake_value, r.score))
    return new_text, detections


class PIIRedactor:
    def __init__(self, score_threshold: float = 0.35, seed: int = 42):
        self.analyzer = build_analyzer_engine()
        self.fake_gen = FakeValueGenerator(seed=seed)
        self.score_threshold = score_threshold
        self.detections: list[Detection] = []

    def redact_document(self, input_path: str, output_path: str) -> None:
        document = load_document(input_path)
        elements = extract_text_elements(input_path)

        # Use the loaded document object so saved edits hit the same tree.
        elements = list(_walk(document, "body"))

        for element in elements:
            # Pass nearby table text in as extra context.
            extra_context = element.row_context.lower().split() if element.row_context else None
            results = analyze_text(
                self.analyzer, element.text, self.score_threshold, context=extra_context
            )
            if not results:
                continue

            resolved = _resolve_overlaps(results)
            new_text, made = _redact_paragraph_text(element.text, resolved, self.fake_gen)

            set_paragraph_text(element.paragraph, new_text)

            for entity_type, original, fake, score in made:
                self.detections.append(
                    Detection(
                        element_id=element.element_id,
                        entity_type=entity_type,
                        original_text=original,
                        fake_text=fake,
                        score=score,
                        context=element.context,
                    )
                )

        document.save(output_path)

    def save_detections_log(self, path: str) -> None:
        """Write the redaction audit log locally."""
        payload = [asdict(d) for d in self.detections]
        Path(path).write_text(json.dumps(payload, indent=2, ensure_ascii=False))

    def print_summary(self) -> None:
        from collections import Counter
        counts = Counter(d.entity_type for d in self.detections)
        print(f"Total redactions: {len(self.detections)}")
        for entity_type, count in counts.most_common():
            print(f"  {entity_type}: {count}")


if __name__ == "__main__":
    import sys
    input_path = sys.argv[1] if len(sys.argv) > 1 else "data/input/Red_Herring_Prospectus.docx"
    output_path = sys.argv[2] if len(sys.argv) > 2 else "output/redacted_prospectus.docx"

    redactor = PIIRedactor()
    redactor.redact_document(input_path, output_path)
    redactor.save_detections_log("output/detections_log.json")
    redactor.print_summary()
    print(f"\nRedacted document saved to: {output_path}")