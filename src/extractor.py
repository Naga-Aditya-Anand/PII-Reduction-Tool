"""Extract text elements from a docx with location info."""

from dataclasses import dataclass, field
from typing import Iterator
import docx
from docx.document import Document as DocxDocument
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table, _Cell
from docx.text.paragraph import Paragraph


@dataclass
class TextElement:
    element_id: str
    text: str
    paragraph: Paragraph
    context: str
    row_context: str = ""  # sibling cell text for table rows


def _iter_block_items(parent):
    if isinstance(parent, DocxDocument):
        parent_elm = parent.element.body
    elif isinstance(parent, _Cell):
        parent_elm = parent._tc
    else:
        raise ValueError("unsupported parent type")

    for child in parent_elm.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, parent)
        elif isinstance(child, CT_Tbl):
            yield Table(child, parent)


def _walk(parent, prefix: str, row_context: str = "") -> Iterator[TextElement]:
    p_counter = 0
    t_counter = 0
    for block in _iter_block_items(parent):
        if isinstance(block, Paragraph):
            text = block.text
            if text.strip():
                eid = f"{prefix}_p{p_counter}"
                yield TextElement(
                    element_id=eid,
                    text=text,
                    paragraph=block,
                    context=f"{prefix} / paragraph {p_counter}",
                    row_context=row_context,
                )
            p_counter += 1
        elif isinstance(block, Table):
            for r_idx, row in enumerate(block.rows):
                # Capture sibling text once per row.
                row_cell_texts = [cell.text for cell in row.cells]
                for c_idx, cell in enumerate(row.cells):
                    sibling_text = " | ".join(
                        t for i, t in enumerate(row_cell_texts) if i != c_idx and t.strip()
                    )
                    cell_prefix = f"{prefix}_tbl{t_counter}_r{r_idx}_c{c_idx}"
                    yield from _walk(cell, cell_prefix, row_context=sibling_text)
            t_counter += 1


def extract_text_elements(docx_path: str) -> list[TextElement]:
    document = docx.Document(docx_path)
    return list(_walk(document, "body"))


def load_document(docx_path: str) -> DocxDocument:
    return docx.Document(docx_path)


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "data/input/Red_Herring_Prospectus.docx"
    elements = extract_text_elements(path)
    print(f"Extracted {len(elements)} non-empty text elements")
    with_row_context = [e for e in elements if e.row_context]
    print(f"Elements with row_context populated: {len(with_row_context)}")
    for el in with_row_context[:5]:
        print(f"  [{el.element_id}] text={el.text[:40]!r}  row_context={el.row_context[:60]!r}")