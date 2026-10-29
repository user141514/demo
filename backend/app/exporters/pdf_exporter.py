"""Offline HTML-to-PDF rendering with embedded Unicode fonts and pagination."""
from io import BytesIO
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from threading import Lock

import fitz as pymupdf

PDF_CACHE_VERSION = "unicode-v4"
_RENDER_LOCK = Lock()
_PRINT_CSS = """
body { font-family: sans-serif; font-size: 10pt; line-height: 1.55; }
.print-shell { max-width: none !important; margin: 0 !important; padding: 0 !important; }
body, div, section, article, footer, h1, h2, h3, p, li, span, th, td {
    color: #2D2218 !important;
}
body, section, article, footer { background: white !important; box-shadow: none !important; }
section { padding: 12px !important; margin-bottom: 16px !important; }
h1 { font-size: 20pt !important; }
h2 { font-size: 15pt !important; }
h3 { font-size: 12pt !important; }
table { width: 100%; border-collapse: collapse; }
th, td { font-size: 9pt !important; padding: 6px !important; }
"""


class _PrintHtml(HTMLParser):
    """Adapt web colors and layout to the renderer's paginated block flow."""
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.parts = []

    def handle_starttag(self, tag, attrs):
        result = []
        for name, value in attrs:
            if name == "style" and value:
                declarations = []
                for declaration in value.split(";"):
                    key, separator, original = declaration.partition(":")
                    if not separator:
                        continue
                    key = key.strip().lower()
                    if key == "color":
                        original = "#2D2218"
                    elif key == "background" and "gradient(" in original:
                        original = "white"
                    elif key == "font-family":
                        original = "sans-serif"
                    elif key in {
                        "box-shadow", "text-shadow", "transition", "display",
                        "flex", "flex-direction", "flex-grow", "flex-shrink", "flex-basis", "flex-wrap",
                        "grid-template-columns", "grid-template-rows", "gap", "align-items", "justify-content",
                        "width", "height", "max-width", "min-width", "max-height", "min-height", "overflow-x",
                    }:
                        # Web flex/grid layouts can silently skip content across pages.
                        continue
                    declarations.append(f"{key}:{original}")
                value = ";".join(declarations)
            result.append(name if value is None else f'{name}="{escape(value, quote=True)}"')
        self.parts.append(f'<{tag}{(" " + " ".join(result)) if result else ""}>')

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        self.parts.append(f"</{tag}>")

    def handle_data(self, data):
        self.parts.append(data)

    def handle_entityref(self, name):
        self.parts.append(f"&{name};")

    def handle_charref(self, name):
        self.parts.append(f"&#{name};")

    def handle_decl(self, declaration):
        self.parts.append(f"<!{declaration}>")


def render_html_pdf(html: str, title: str = "") -> bytes:
    # Serialize native rendering; do not share MuPDF story/document objects.
    with _RENDER_LOCK:
        buffer = BytesIO()
        printable = _PrintHtml()
        printable.feed(html)
        printable.close()
        story = pymupdf.Story(html="".join(printable.parts), user_css=_PRINT_CSS)
        page_box = pymupdf.paper_rect("a4")
        content_box = page_box + (36, 36, -36, -48)

        def page_rect(page_number, filled):
            if page_number >= 500:
                raise ValueError("PDF layout exceeded the page limit.")
            return page_box, content_box, None

        writer = pymupdf.DocumentWriter(buffer)
        try:
            story.write(writer, page_rect)
        finally:
            writer.close()
        with pymupdf.open(stream=buffer.getvalue(), filetype="pdf") as document:
            document.set_metadata({"title": title, "producer": f"Meitai PDF Export {PDF_CACHE_VERSION}"})
            for index, page in enumerate(document):
                label = f"{index + 1} / {len(document)}"
                width = pymupdf.get_text_length(label, fontname="helv", fontsize=9)
                page.insert_text(((page.rect.width - width) / 2, page.rect.height - 22),
                                 label, fontname="helv", fontsize=9, color=(0.45, 0.45, 0.45))
            document.subset_fonts()
            return document.tobytes(garbage=4, deflate=True)


def is_valid_pdf(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size < 128:
        return False
    try:
        with pymupdf.open(path) as document:
            return len(document) > 0 and document.is_pdf
    except Exception:
        return False
