"""Renders the digest as HTML. The PDF is printed from this same HTML."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from schema.digest import DigestView

TEMPLATES = Path(__file__).parent / "templates"

# autoescape: text from the transcript or the model is shown as text, never run as HTML.
_environment = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=True)


def render_html(view: DigestView) -> str:
    return _environment.get_template("digest.html").render(view=view)
