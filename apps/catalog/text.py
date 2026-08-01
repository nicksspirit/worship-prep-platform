import unicodedata

SEARCH_CONFIG = "wpp_simple_unaccent"


def normalize_title(value: str) -> str:
    """Return the stable accent-insensitive title ordering key."""

    decomposed = unicodedata.normalize("NFKD", value)
    unaccented = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return " ".join(unaccented.casefold().split())
