from pathlib import Path
from .models import Phrase, Slide, Project

def parse_phrases(phrases: list[str]) -> list[Phrase]:
    return [Phrase(text=p.strip()) for p in phrases if p.strip()]

def parse_file(path: Path) -> list[Phrase]:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        import json
        data = json.loads(text)
        return [Phrase(text=item if isinstance(item, str) else item["text"]) for item in data]
    else:
        return _parse_txt(text)

def _tag(line: str, tag: str) -> str | None:
    """Match <tag> or <tag attr> and return inner content, or None."""
    close_tag = f"</{tag}>"
    if not line.endswith(close_tag):
        return None
    if line.startswith(f"<{tag}>") or line.startswith(f"<{tag} "):
        start = line.index(">") + 1
        return line[start:-len(close_tag)].strip()
    return None

def _tag_attr(line: str, tag: str) -> str | None:
    """Return the attribute value from <tag attr> or None if no attribute."""
    if not line.startswith(f"<{tag} "):
        return None
    end = line.index(">")
    return line[len(tag) + 2:end].strip()

def _next_non_blank(lines: list[str], i: int) -> int:
    while i < len(lines) and not lines[i]:
        i += 1
    return i

def _parse_txt(text: str) -> list[Phrase]:
    phrases = []
    lines = [line.strip() for line in text.splitlines()]
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line or line.startswith("#"):
            i += 1
            continue

        title = _tag(line, "title")
        title_attr = _tag_attr(line, "title") or "top"
        body = None
        body_position = None
        image_prompt = None

        if title is not None:
            j = _next_non_blank(lines, i + 1)
            if j < len(lines) and _tag(lines[j], "body") is not None:
                # normal case: title at top + body
                body = _tag(lines[j], "body")
                i = j
            else:
                # standalone: no body, title is the only text element
                body = title
                title = None
                body_position = title_attr

        # if this line is a <body> (no preceding title)
        elif _tag(line, "body") is not None:
            body = _tag(line, "body")

        # plain text line
        else:
            body = line

        # look ahead for optional <prompt>, <image>, <duration>
        image_file = None
        duration = None
        j = _next_non_blank(lines, i + 1)
        if j < len(lines) and _tag(lines[j], "prompt") is not None:
            image_prompt = _tag(lines[j], "prompt")
            i = j
        elif j < len(lines) and _tag(lines[j], "image") is not None:
            image_file = _tag(lines[j], "image")
            i = j

        j = _next_non_blank(lines, i + 1)
        if j < len(lines) and (dur_str := _tag(lines[j], "duration")) is not None:
            duration = float(dur_str)
            i = j

        if body or image_file:
            phrases.append(Phrase(text=body or "", title=title, body_position=body_position, image_prompt=image_prompt, image_file=image_file, duration=duration))
        i += 1
    return phrases

def build_project(phrases: list[Phrase], output_path: Path) -> Project:
    slides = [Slide(phrase=p) for p in phrases]
    return Project(slides=slides, output_path=output_path)
