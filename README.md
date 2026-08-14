# PII Redaction Tool

## The Approach

This tool uses a hybrid approach, combining machine learning with strict structural rules to maximize accuracy.

* **Unstructured Data (Presidio + spaCy):** `en_core_web_lg` handles names, organizations, and locations where context is required.
* **Structured Data (Custom Recognizers):** Formats with verifiable rules bypass the NER model completely. Emails and SSNs use regex; phone numbers validate against Google's `phonenumbers` library; credit cards require Luhn-checksum validation.
* **Organization Fallback:** A dedicated structural recognizer independently catches entities with corporate suffixes (Ltd, LLP, Trust) to catch obvious companies the NER model misses.
* **Consistent Pseudonymization:** Replacements use a seeded `Faker` generator. Canonicalization ensures "BSE Ltd" and "BSE Limited" receive the same fake name across the entire document.

## Key Judgment Calls

* **Public bodies remain visible:** Regulators and exchanges (SEBI, BSE, RBI) are not redacted. Redacting them offers zero privacy benefit and harms readability.
* **Bare locations are redacted:** Standalone cities, states, or countries are treated as PII. We trade some precision in the LOCATION category to prevent edge-case leaks.
* **Out of scope (for now):** Plot numbers, flat numbers, and PIN codes are not yet targeted as they lack a distinct NER shape. (A dedicated PIN regex would be the easiest next addition).
* **N/A Categories:** SSNs, credit cards, and IP addresses do not appear in this corporate IPO prospectus, so they were evaluated as "not applicable" rather than reporting uninformative 100% or 0% scores.

## Evaluation Metrics

Based on a hand-sampled, gold-standard evaluation set (~120 elements covering all document PII types and negative controls):

* **Precision:** 86%
* **Recall:** 79%
* **F1 Score:** 82.6%
* *Note: Email and Phone detection achieved a perfect 100/100 due to their strict validation rules.*

## Known Limitations & Failure Patterns

1. **Context-free table cells:** spaCy struggles with isolated strings. A bare name in a cell might be flagged as an organization, building fragments as people, or the literal word "Email" as a person's name.
2. **Slash-separated lists:** Formats like `Name/ Name/ Name` (common in contact lists) confuse the model, causing it to drop or merge roughly one in five names. A dedicated pattern regex is needed for this specific convention.

## How to Extend

To add a new PII type:

1. Write a `Pattern` (or subclass `EntityRecognizer` for complex logic).
2. Register it in `get_custom_recognizers()`.
3. Add the entity name to `SUPPORTED_ENTITIES`.

Detection, redaction, and evaluation will automatically inherit the new type without pipeline changes.

## Run it

Install dependencies:

```bash
uv sync
```

Run the CLI:

```bash
python main.py "data/input/Red_Herring_Prospectus.docx" "output/redacted_prospectus.docx"
```

Run the web app:

```bash
streamlit run streamlit_app.py
```

The CLI writes a redacted Word document and a detection log, and the Streamlit app lets you upload a `.docx` file and download the redacted result in the browser.