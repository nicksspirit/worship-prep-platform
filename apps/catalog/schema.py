from datetime import datetime

from django_bolt.serializers import Serializer


class APIErrorDetail(Serializer):
    code: str
    message: str
    restart: str | None = None


class APIErrorResponse(Serializer):
    error: APIErrorDetail


class CatalogImportResponse(Serializer):
    run_id: str
    status: str


class CatalogSearchSong(Serializer):
    song_uid: str
    title: str
    authors: list[str]
    slide_count: int
    content_changed_at: datetime
    rights_status: str
    lyrics_access: str


class CatalogSearchResponse(Serializer):
    results: list[CatalogSearchSong]
    next: str | None
    has_more: bool


class SongMetadataResponse(Serializer):
    song_uid: str
    title: str
    authors: list[str]
    copyright_notice: str
    slide_count: int
    content_changed_at: datetime
    rights_status: str
    lyrics_access: str


class SongLyricsSection(Serializer):
    position: int
    label: str
    text: str


class SongLyricsResponse(Serializer):
    song_uid: str
    title: str
    content_changed_at: datetime
    rights_status: str
    sections: list[SongLyricsSection]
