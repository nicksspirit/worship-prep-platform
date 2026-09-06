"""Typed, transport-neutral preparation for Catalog Import persistence."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import TypedDict

from apps.catalog.text import normalize_title


class CatalogSource(TypedDict):
    """The stable source identity needed to project a song."""

    song_uid: str


class CatalogMetadata(TypedDict):
    """The source metadata materialized in a catalog entry."""

    title: str
    author: str | None
    copyright: str | None


class CatalogSlide(TypedDict):
    """A presentation slide within one Song Section."""

    position: int
    lines: list[str]


class CatalogSection(TypedDict):
    """A source-normalized Song Section."""

    position: int
    label: str
    slides: list[CatalogSlide]


class FingerprintComponents(TypedDict):
    """Independent semantic-fingerprint components."""

    metadata: str
    lyrics: str
    structure: str
    presentation: str


class SemanticFingerprint(TypedDict):
    """The versioned fingerprint carried by a Catalog Import Package."""

    version: str
    value: str
    components: FingerprintComponents


class CatalogSongRecord(TypedDict):
    """A schema-validated song record used by import preparation."""

    source: CatalogSource
    metadata: CatalogMetadata
    cleaned_lyrics: str
    sections: list[CatalogSection]
    semantic_fingerprint: SemanticFingerprint


@dataclass(frozen=True, slots=True)
class ExistingCatalogSong:
    """Freshness information carried from the previously active snapshot."""

    semantic_fingerprint: str
    content_changed_at: datetime


@dataclass(frozen=True, slots=True)
class PreparedCatalogEntry:
    """The complete, persistence-ready projection of one imported song."""

    song_uid: str
    title: str
    normalized_title: str
    authors: tuple[str, ...]
    copyright_notice: str
    cleaned_lyrics: str
    sections: list[CatalogSection]
    slide_count: int
    rights_status: str
    fingerprint_version: str
    semantic_fingerprint: str
    metadata_fingerprint: str
    lyrics_fingerprint: str
    structure_fingerprint: str
    presentation_fingerprint: str
    content_changed_at: datetime


def prepare_catalog_entries(
    records: Sequence[CatalogSongRecord],
    *,
    previous_songs: Mapping[str, ExistingCatalogSong],
    rights_by_song_uid: Mapping[str, str],
    promoted_at: datetime,
) -> list[PreparedCatalogEntry]:
    """Project validated song records without accessing persistence or framework state."""

    entries = []
    for record in records:
        source = record["source"]
        metadata = record["metadata"]
        fingerprint = record["semantic_fingerprint"]
        components = fingerprint["components"]
        song_uid = source["song_uid"]
        prior = previous_songs.get(song_uid)
        changed_at = (
            prior.content_changed_at
            if prior and prior.semantic_fingerprint == fingerprint["value"]
            else promoted_at
        )
        entries.append(
            PreparedCatalogEntry(
                song_uid=song_uid,
                title=metadata["title"],
                normalized_title=normalize_title(metadata["title"]),
                authors=(metadata["author"],) if metadata["author"] else (),
                copyright_notice=metadata["copyright"] or "",
                cleaned_lyrics=record["cleaned_lyrics"],
                sections=record["sections"],
                slide_count=sum(
                    len(section["slides"]) for section in record["sections"]
                ),
                rights_status=rights_by_song_uid.get(song_uid, "unknown"),
                fingerprint_version=fingerprint["version"],
                semantic_fingerprint=fingerprint["value"],
                metadata_fingerprint=components["metadata"],
                lyrics_fingerprint=components["lyrics"],
                structure_fingerprint=components["structure"],
                presentation_fingerprint=components["presentation"],
                content_changed_at=changed_at,
            )
        )
    return entries
