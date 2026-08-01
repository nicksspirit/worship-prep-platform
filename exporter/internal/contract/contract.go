// Package contract defines the storage-neutral Catalog Import Package contract.
package contract

import "time"

const (
	Version            = "catalog-import/v1"
	ParserVersion      = "easyworship-rtf/v1"
	FingerprintVersion = "song-semantic/v1"
	RecordsPath        = "songs.ndjson"
)

// Manifest describes one complete EasyWorship Library snapshot.
type Manifest struct {
	ContractVersion    string          `json:"contract_version"`
	RunID              string          `json:"run_id"`
	ExporterInstanceID string          `json:"exporter_instance_id"`
	ExporterVersion    string          `json:"exporter_version"`
	ParserVersion      string          `json:"parser_version"`
	CreatedAt          time.Time       `json:"created_at"`
	Source             SourceManifest  `json:"source"`
	Records            RecordsManifest `json:"records"`
	Counts             Counts          `json:"counts"`
	Warnings           []Warning       `json:"warnings"`
}

// SourceManifest records the copied source databases used by the exporter.
type SourceManifest struct {
	System      string            `json:"system"`
	Fingerprint string            `json:"fingerprint"`
	Files       []SourceFile      `json:"files"`
	Diagnostics SourceDiagnostics `json:"diagnostics"`
}

// SourceFile identifies a source artifact without exposing its local path.
type SourceFile struct {
	Name     string `json:"name"`
	Required bool   `json:"required"`
	Present  bool   `json:"present"`
	Size     int64  `json:"size,omitempty"`
	SHA256   string `json:"sha256,omitempty"`
}

// SourceDiagnostics contains non-authoritative evidence from the optional index.
type SourceDiagnostics struct {
	SongKeysPresent bool `json:"song_keys_present"`
	SongKeysRows    int  `json:"song_keys_rows,omitempty"`
}

// RecordsManifest authenticates the exact newline-delimited records payload.
type RecordsManifest struct {
	Path        string `json:"path"`
	MediaType   string `json:"media_type"`
	SHA256      string `json:"sha256"`
	Bytes       int    `json:"bytes"`
	Fingerprint string `json:"fingerprint"`
}

// Counts summarizes package output.
type Counts struct {
	Songs    int `json:"songs"`
	Warnings int `json:"warnings"`
}

// Warning is a usable structural anomaly that did not invalidate the package.
type Warning struct {
	Code    string `json:"code"`
	SongUID string `json:"song_uid,omitempty"`
	Message string `json:"message"`
}

// SongRecord preserves source evidence and storage-neutral derived song content.
type SongRecord struct {
	ContractVersion string              `json:"contract_version"`
	Source          SongSource          `json:"source"`
	Metadata        SongMetadata        `json:"metadata"`
	RawLyrics       RawLyrics           `json:"raw_lyrics"`
	CleanedLyrics   string              `json:"cleaned_lyrics"`
	Sections        []Section           `json:"sections"`
	Fingerprint     SemanticFingerprint `json:"semantic_fingerprint"`
}

// SongSource contains opaque EasyWorship identity and revision evidence.
type SongSource struct {
	System               string      `json:"system"`
	SongRowID            int64       `json:"song_rowid"`
	SongItemUID          string      `json:"song_item_uid"`
	SongUID              string      `json:"song_uid"`
	SongRevisionUID      *string     `json:"song_revision_uid"`
	Revision             SourceValue `json:"revision"`
	LayoutRevision       SourceValue `json:"layout_revision"`
	ProviderID           SourceValue `json:"provider_id"`
	VendorID             SourceValue `json:"vendor_id"`
	PresentationID       SourceValue `json:"presentation_id"`
	SlideUIDs            []string    `json:"slide_uids"`
	SlideLayoutRevisions SourceValue `json:"slide_layout_revisions"`
	SlideRevisions       SourceValue `json:"slide_revisions"`
}

// SourceValue losslessly represents SQLite null, integer, real, text, or blob values.
type SourceValue struct {
	Type  string `json:"type"`
	Value any    `json:"value,omitempty"`
}

// SongMetadata contains source metadata selected for possible product use.
type SongMetadata struct {
	Title           string  `json:"title"`
	Author          *string `json:"author"`
	Copyright       *string `json:"copyright"`
	Administrator   *string `json:"administrator"`
	Description     *string `json:"description"`
	Tags            *string `json:"tags"`
	ReferenceNumber *string `json:"reference_number"`
}

// RawLyrics preserves the authoritative EasyWorship lyric representation.
type RawLyrics struct {
	Format  string `json:"format"`
	Content string `json:"content"`
}

// Section is an ordered normalized label and its lyric slides.
type Section struct {
	Position int     `json:"position"`
	Label    string  `json:"label"`
	Slides   []Slide `json:"slides"`
}

// Slide is one ordered projection-sized lyric unit.
type Slide struct {
	Position       int      `json:"position"`
	SourceSlideUID *string  `json:"source_slide_uid"`
	Lines          []string `json:"lines"`
}

// SemanticFingerprint is a versioned componentized catalog-owned fingerprint.
type SemanticFingerprint struct {
	Version    string                `json:"version"`
	Components FingerprintComponents `json:"components"`
	Value      string                `json:"value"`
}

// FingerprintComponents make changes diagnosable without trusting source revisions.
type FingerprintComponents struct {
	Metadata     string `json:"metadata"`
	Lyrics       string `json:"lyrics"`
	Structure    string `json:"structure"`
	Presentation string `json:"presentation"`
}
