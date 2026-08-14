"""Write redacted text back into a paragraph."""

from docx.text.paragraph import Paragraph


def set_paragraph_text(paragraph: Paragraph, new_text: str) -> None:
    """Replace the visible text while keeping the first run's style."""
    runs = paragraph.runs

    if not runs:
        # Empty paragraphs just need one run.
        paragraph.add_run(new_text)
        return

    runs[0].text = new_text
    for run in runs[1:]:
        run.text = ""