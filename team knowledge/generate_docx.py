"""Regenerate Team Knowledge.docx from the Markdown source in this folder.

Run with: python 'team knowledge/generate_docx.py'
Requires: pip install python-docx
"""

from datetime import datetime
from pathlib import Path
import zipfile

from docx import Document
from docx.shared import Pt

FOLDER = Path(__file__).resolve().parent  # Directory containing this script
SOURCE = FOLDER / "README.md"  # Markdown source of truth
OUTPUT = FOLDER / "Team Knowledge.docx"  # Generated Word document


def clean(text):
    """Remove simple Markdown emphasis markers from one line of text."""
    return text.replace("`", "").replace("**", "").strip()  # Plain text for Word


def add_code_block(document, lines):
    """Add a fenced code block as monospaced paragraphs."""
    paragraph = document.add_paragraph()  # One paragraph holds the whole block
    paragraph.style = document.styles["Normal"]  # Start from the normal style
    for index, line in enumerate(lines):  # index tracks line breaks
        run = paragraph.add_run(line)  # line is one raw line from the code fence
        run.font.name = "Courier New"  # Monospace font keeps the diagram aligned
        run.font.size = Pt(9)  # Small enough for long wiring diagrams
        if index < len(lines) - 1:  # Not the final line
            run.add_break()  # Move to the next line inside the paragraph


def is_separator_row(line):
    """Return True for a Markdown table separator such as |---|---|."""
    cells = [cell.strip() for cell in line.strip().strip("|").split("|")]  # Split cells
    return bool(cells) and all(cell and set(cell) <= set("-:") for cell in cells)  # Only dashes/colons


def add_table(document, rows):
    """Turn Markdown table rows into a real Word table."""
    parsed = [[clean(cell) for cell in row.strip().strip("|").split("|")] for row in rows]  # Cell text
    if not parsed:  # Defensive: nothing to add
        return  # Skip empty tables
    columns = len(parsed[0])  # Number of columns from the header row
    table = document.add_table(rows=1, cols=columns)  # Header row plus data rows
    table.style = "Table Grid"  # Visible borders
    header = table.rows[0].cells  # Header cell objects
    for index, text in enumerate(parsed[0]):  # index is the column number
        header[index].text = text  # Fill the header cell
        for paragraph in header[index].paragraphs:  # Bold every header paragraph
            for run in paragraph.runs:  # run holds the cell text
                run.bold = True  # Emphasize the column title
    for row in parsed[1:]:  # Remaining rows are data
        cells = table.add_row().cells  # New row's cell objects
        for index, text in enumerate(row[:columns]):  # Never exceed the column count
            cells[index].text = text  # Fill the data cell


def build_document(source_text):
    """Build and return a Word document from the Markdown source text."""
    document = Document()  # Empty Word document from python-docx's template
    document.core_properties.title = "Team Knowledge - SolarLab Mini"  # Document title metadata
    document.core_properties.subject = "SolarLab Mini onboarding guide"  # Subject metadata
    document.core_properties.created = datetime(2026, 1, 1)  # Fixed timestamp for repeatable output
    document.core_properties.modified = datetime(2026, 1, 1)  # Fixed timestamp for repeatable output

    lines = source_text.splitlines()  # Source split into individual lines
    index = 0  # Current line number
    while index < len(lines):  # Process every line in order
        line = lines[index]  # Current raw line
        stripped = line.strip()  # Line without surrounding whitespace
        if stripped.startswith("```"):  # Start of a fenced code block
            index += 1  # Move past the fence
            code_lines = []  # Collect code lines until the closing fence
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code_lines.append(lines[index])  # Keep the raw line for alignment
                index += 1  # Advance
            add_code_block(document, code_lines)  # Write the block as monospaced text
        elif stripped.startswith("|") and stripped.endswith("|"):  # Markdown table
            table_rows = []  # Collect table rows
            while index < len(lines) and lines[index].strip().startswith("|"):
                candidate = lines[index].strip()  # Current table line
                if not is_separator_row(candidate):  # Skip |---|---| separators
                    table_rows.append(candidate)  # Keep header/data rows
                index += 1  # Advance
            add_table(document, table_rows)  # Write a real Word table
        elif stripped.startswith("# "):  # Top-level heading
            document.add_heading(clean(stripped[2:]), level=0)  # Document title
        elif stripped.startswith("## "):  # Section heading
            document.add_heading(clean(stripped[3:]), level=1)  # Heading 1
        elif stripped.startswith("### "):  # Subsection heading
            document.add_heading(clean(stripped[4:]), level=2)  # Heading 2
        elif stripped.startswith("- "):  # Bullet list item
            document.add_paragraph(clean(stripped[2:]), style="List Bullet")  # Bullet paragraph
        elif stripped[:2] in ("1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9."):
            document.add_paragraph(clean(stripped.split(".", 1)[1]), style="List Number")  # Numbered step
        elif stripped:  # Ordinary paragraph
            document.add_paragraph(clean(stripped))  # Plain text paragraph
        index += 1  # Move to the next line
    return document  # Finished document


def normalize_zip(path):
    """Rewrite the .docx zip with fixed timestamps and order for stable output."""
    with zipfile.ZipFile(path, "r") as source_zip:
        entries = [(info, source_zip.read(info.filename)) for info in source_zip.infolist()]
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as target_zip:
        for info, data in sorted(entries, key=lambda item: item[0].filename):
            fixed = zipfile.ZipInfo(info.filename, date_time=(2026, 1, 1, 0, 0, 0))
            fixed.compress_type = zipfile.ZIP_DEFLATED
            fixed.external_attr = info.external_attr
            target_zip.writestr(fixed, data)


def main():
    """Read the Markdown source, write the Word file, and print a summary."""
    source_text = SOURCE.read_text(encoding="utf-8")  # Full Markdown source
    document = build_document(source_text)  # Convert to Word content
    document.save(OUTPUT)  # Write the Word document
    normalize_zip(OUTPUT)  # Make the binary file byte-for-byte reproducible
    print("Wrote {} ({} paragraphs, {} tables)".format(  # Confirmation for the user
        OUTPUT.name, len(document.paragraphs), len(document.tables)
    ))


if __name__ == "__main__":  # Only run when invoked as a script
    main()  # Generate the Word document
