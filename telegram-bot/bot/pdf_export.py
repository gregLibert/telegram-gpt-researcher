"""Render Markdown as PDF via HTML/CSS using WeasyPrint."""

from __future__ import annotations

import markdown
from weasyprint import CSS, HTML

_TABLES_LINKS_BASE_CSS = """
@page {
  size: A4;
  margin: 1.5cm;
}
body {
  font-family: "DejaVu Sans", "Liberation Sans", sans-serif;
  font-size: 11pt;
  line-height: 1.4;
  color: #1a1a1a;
}
h1, h2, h3, h4 {
  color: #111;
  page-break-after: avoid;
}
table {
  border-collapse: collapse;
  width: 100%;
  margin: 1em 0;
  font-size: 10pt;
  table-layout: fixed;
}
thead th {
  background: #e8e8e8;
  font-weight: bold;
}
th, td {
  border: 1px solid #444;
  padding: 6px 8px;
  vertical-align: top;
  word-wrap: break-word;
  overflow-wrap: anywhere;
  hyphens: auto;
}
tbody tr:nth-child(even) {
  background: #f5f5f5;
}
a, a:visited {
  color: #0645ad;
  word-break: break-all;
  overflow-wrap: anywhere;
}
code {
  font-family: "DejaVu Sans Mono", monospace;
  font-size: 9.5pt;
  background: #f0f0f0;
  padding: 1px 4px;
}
pre {
  font-family: "DejaVu Sans Mono", monospace;
  font-size: 9pt;
  white-space: pre-wrap;
  word-break: break-word;
  overflow-wrap: anywhere;
  background: #f8f8f8;
  border: 1px solid #ddd;
  padding: 8px;
}
blockquote {
  margin: 0.75em 0;
  padding-left: 12px;
  border-left: 4px solid #ccc;
  color: #333;
}
ul, ol {
  margin: 0.5em 0;
  padding-left: 1.4em;
}
"""


def _markdown_to_html_document(markdown_text: str) -> str:
    """Convert Markdown to a minimal UTF-8 HTML5 document body."""
    body = markdown_text if markdown_text.strip() else "(rapport vide)"
    fragment = markdown.markdown(
        body,
        extensions=["extra", "nl2br", "sane_lists"],
    )
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Report</title>
</head>
<body>
{fragment}
</body>
</html>
"""


def markdown_to_pdf_bytes(markdown_text: str) -> bytes:
    """
    Build a PDF from Markdown using WeasyPrint.

    Styles prioritize readable tables, wrapped long URLs, and monospace blocks.
    """
    html_string = _markdown_to_html_document(markdown_text)
    return HTML(string=html_string).write_pdf(
        stylesheets=[CSS(string=_TABLES_LINKS_BASE_CSS)],
    )


markdown_to_basic_pdf_bytes = markdown_to_pdf_bytes
