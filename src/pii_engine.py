"""Presidio detection setup and filtering."""

from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_analyzer.predefined_recognizers import SpacyRecognizer

from presidio_analyzer import RecognizerResult
from src.recognizers.regex_recognizers import (
    get_custom_recognizers,
    is_public_entity,
    is_likely_organization,
    clean_span_text,
)


SUPPORTED_ENTITIES = [
    "PERSON",
    "ORGANIZATION",
    "LOCATION",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "US_SSN",
    "CREDIT_CARD",
    "IP_ADDRESS",
    "DATE_OF_BIRTH",
]


def build_analyzer_engine(spacy_model: str = "en_core_web_lg") -> AnalyzerEngine:
    """Build and return a configured Presidio AnalyzerEngine (call once, reuse)."""
    nlp_config = {
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "en", "model_name": spacy_model}],
    }
    nlp_engine = NlpEngineProvider(nlp_configuration=nlp_config).create_engine()

    registry = RecognizerRegistry()
    registry.add_recognizer(SpacyRecognizer(supported_language="en"))

    for recognizer in get_custom_recognizers():
        registry.add_recognizer(recognizer)

    return AnalyzerEngine(
        nlp_engine=nlp_engine,
        registry=registry,
        supported_languages=["en"],
    )


def analyze_text(
    analyzer: AnalyzerEngine,
    text: str,
    score_threshold: float = 0.35,
    context: list[str] | None = None,
):
    """Run detection on one string, with optional extra context."""
    results = analyzer.analyze(
        text=text,
        language="en",
        entities=SUPPORTED_ENTITIES,
        context=context or [],
    )

    filtered = []
    for r in results:
        if r.score < score_threshold:
            continue

        span_text = text[r.start : r.end]

        if r.entity_type == "ORGANIZATION":
            if is_public_entity(span_text):
                continue  # statutory body, not PII
            if not is_likely_organization(span_text):
                continue  # defined term, acronym, or other noise

        # Trim stray boundary punctuation before redaction.
        cleaned, left_trim, right_trim = clean_span_text(span_text)
        if not cleaned:
            continue  # nothing useful left after trimming

        new_result = RecognizerResult(
            entity_type=r.entity_type,
            start=r.start + left_trim,
            end=r.end - right_trim,
            score=r.score,
        )
        filtered.append(new_result)

    return filtered


if __name__ == "__main__":
    analyzer = build_analyzer_engine()
    sample = (
        "Rashi Patil can be reached at rashi.patil@gmail.com or +91 98765 43210. "
        "She was born on 14 March 1990 and works at Bajaj Finserv Ltd, "
        "with registered office in Mumbai, Maharashtra. Listed on the BSE and NSE."
    )
    results = analyze_text(analyzer, sample)
    print(f"Sample text: {sample}\n")
    print(f"Found {len(results)} entities:")
    for r in sorted(results, key=lambda x: x.start):
        print(f"  [{r.entity_type}] {sample[r.start:r.end]!r} (score={r.score:.2f})")