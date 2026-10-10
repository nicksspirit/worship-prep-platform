import re
import textwrap
from dataclasses import dataclass

from django.core.exceptions import ValidationError

LABEL = re.compile(
    r"(?:verse|chorus|bridge|pre[- ]chorus|refrain|intro|introduction|outro|ending|"
    r"interlude|tag|solo|vamp)(?:\s*\d+)?[:]?",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class PreparedSection:
    position: int
    label: str
    slides: tuple[tuple[str, ...], ...]


def prepare_lyrics(lyrics: str) -> tuple[PreparedSection, ...]:
    """Prepare one supplied song without inventing words or expanding repeats."""
    if not isinstance(lyrics, str) or not lyrics.strip():
        raise ValidationError("Paste the song lyrics.")
    if len(lyrics) > 20000:
        raise ValidationError("Lyrics cannot exceed 20,000 characters.")
    if any((ord(char) < 32 and char not in "\t\r\n") or ord(char) == 127
           for char in lyrics):
        raise ValidationError("Lyrics contain unsupported control characters.")
    if any(len(word) > 45 for word in lyrics.split()):
        raise ValidationError(
            "A lyric word exceeds 45 characters. Check for a missing space or use "
            "a shorter word before preparing the lyrics.",
        )
    wrapper = textwrap.TextWrapper(
        width=45, break_long_words=False, break_on_hyphens=False,
        replace_whitespace=False,
    )
    sections: list[PreparedSection] = []
    label = ""
    slides: list[tuple[str, ...]] = []
    lines: list[str] = []

    def finish_slide() -> None:
        if lines:
            slides.append(tuple(lines))
            lines.clear()

    def finish_section() -> None:
        finish_slide()
        if slides or label:
            sections.append(PreparedSection(len(sections) + 1, label, tuple(slides)))
        slides.clear()

    for source_line in lyrics.splitlines():
        line = source_line.strip()
        if not line:
            finish_slide()
            continue
        candidate = line
        if line.startswith("[") and line.endswith("]"):
            candidate = line[1:-1].strip()
        if LABEL.fullmatch(candidate):
            finish_section()
            label = candidate
            continue
        for wrapped in wrapper.wrap(line):
            lines.append(wrapped)
            if len(lines) == 2:
                finish_slide()
    finish_section()
    if not any(section.slides for section in sections):
        raise ValidationError("Include lyric words, not only section labels.")
    return tuple(sections)


def _store_sections(sections: tuple[PreparedSection, ...]) -> list[dict]:
    return [
        {"position": section.position, "label": section.label,
         "slides": [list(lines) for lines in section.slides]}
        for section in sections
    ]


def _read_sections(stored: list[dict]) -> tuple[PreparedSection, ...]:
    return tuple(PreparedSection(
        section["position"], section["label"],
        tuple(tuple(lines) for lines in section["slides"]),
    ) for section in stored)


def _format_sections(sections: tuple[PreparedSection, ...]) -> str:
    blocks = []
    for section in sections:
        text = "\n\n".join("\n".join(lines) for lines in section.slides)
        blocks.append(f"[{section.label}]\n{text}" if section.label else text)
    return "\n\n".join(blocks)
