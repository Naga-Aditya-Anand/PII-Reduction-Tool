"""CLI entry point for the PII redaction tool."""

import sys
from src.redactor import PIIRedactor

DEFAULT_INPUT = "data/input/Red_Herring_Prospectus.docx"
DEFAULT_OUTPUT = "output/redacted_prospectus.docx"
DEFAULT_LOG = "output/detections_log.json"


def main():
    input_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_INPUT
    output_path = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_OUTPUT

    print(f"Reading:  {input_path}")
    print(f"Writing:  {output_path}\n")

    redactor = PIIRedactor()
    redactor.redact_document(input_path, output_path)
    redactor.save_detections_log(DEFAULT_LOG)

    print()
    redactor.print_summary()
    print(f"\nDone. Redacted document: {output_path}")
    print(f"Detection log (contains real PII, keep local): {DEFAULT_LOG}")


if __name__ == "__main__":
    main()