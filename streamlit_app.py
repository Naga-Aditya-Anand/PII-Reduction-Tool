"""Streamlit UI for the PII redaction tool."""

import io
import json
import tempfile
from collections import Counter
from pathlib import Path

import streamlit as st

from src.redactor import PIIRedactor

st.set_page_config(page_title="PII Redaction Tool", page_icon="🔒", layout="centered")


@st.cache_resource(show_spinner="Loading detection model (first run only, ~10-20s)...")
def get_redactor(score_threshold: float, seed: int) -> PIIRedactor:
    # Load the model once per process.
    return PIIRedactor(score_threshold=score_threshold, seed=seed)


st.title("🔒 PII Redaction Tool")
st.caption(
    "Upload a .docx and get back a version with names, emails, phone numbers, "
    "organizations, addresses, and other PII replaced with realistic fake values."
)

with st.sidebar:
    st.header("Settings")
    score_threshold = st.slider(
        "Detection confidence threshold", 0.0, 1.0, 0.35, 0.05,
        help="Lower catches more (higher recall, more false positives). "
             "Higher is stricter (higher precision, may miss some PII).",
    )
    seed = st.number_input(
        "Fake-value seed", value=42, step=1,
        help="Same seed -> same fake values every time, for reproducibility.",
    )
    st.markdown("---")
    st.caption(
        "Detects: names, emails, phone numbers, organizations, addresses, "
        "SSNs, credit cards, dates of birth, IP addresses."
    )

uploaded = st.file_uploader("Upload a .docx file", type=["docx"])

if uploaded is not None:
    if st.button("Redact document", type="primary"):
        with tempfile.TemporaryDirectory() as tmp_dir:
            input_path = Path(tmp_dir) / "input.docx"
            output_path = Path(tmp_dir) / "redacted.docx"
            input_path.write_bytes(uploaded.getvalue())

            redactor = get_redactor(score_threshold, seed)
            # Reset per upload so counts don't leak between documents.
            redactor.detections = []

            with st.spinner("Scanning and redacting..."):
                redactor.redact_document(str(input_path), str(output_path))

            redacted_bytes = output_path.read_bytes()

        st.success(f"Done — {len(redactor.detections)} redactions made.")

        counts = Counter(d.entity_type for d in redactor.detections)
        if counts:
            st.subheader("Detections by type")
            cols = st.columns(len(counts))
            for col, (etype, count) in zip(cols, counts.most_common()):
                col.metric(etype, count)
        else:
            st.info("No PII detected in this document.")

        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                "⬇ Download redacted .docx",
                data=redacted_bytes,
                file_name=f"redacted_{uploaded.name}",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                type="primary",
            )
        with col2:
            detections_json = json.dumps(
                [
                    {
                        "entity_type": d.entity_type,
                        "original_text": d.original_text,
                        "fake_text": d.fake_text,
                        "score": d.score,
                        "context": d.context,
                    }
                    for d in redactor.detections
                ],
                indent=2, ensure_ascii=False,
            )
            st.download_button(
                "⬇ Download detections log (.json)",
                data=detections_json,
                file_name="detections_log.json",
                mime="application/json",
            )

        with st.expander("See what was redacted"):
            for d in redactor.detections:
                st.text(f"[{d.entity_type}]  {d.original_text!r}  →  {d.fake_text!r}  (score {d.score:.2f})")
else:
    st.info("Upload a .docx file above to get started.")