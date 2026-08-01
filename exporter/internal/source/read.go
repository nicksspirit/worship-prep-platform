package source

import (
	"context"
	"crypto/sha256"
	"database/sql"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net/url"
	"path/filepath"
	"strings"

	"github.com/nicksspirit/worship-prep-platform/exporter/internal/contract"
	"github.com/nicksspirit/worship-prep-platform/exporter/internal/rtf"
	"modernc.org/sqlite"
)

func init() {
	// EasyWorship's UTF8_U_CI implementation is not stored in the database.
	// Registering a deterministic placeholder lets SQLite parse the schema; all
	// content queries explicitly use NOT INDEXED and never depend on its ordering.
	sqlite.MustRegisterCollationUtf8("UTF8_U_CI", strings.Compare)
}

// ReadResult is the complete, validated output from copied source databases.
type ReadResult struct {
	Songs       []contract.SongRecord
	Warnings    []contract.Warning
	Diagnostics contract.SourceDiagnostics
}

type rawWord struct {
	words                string
	slideUIDs            []string
	slideLayoutRevisions any
	slideRevisions       any
}

// Read validates the canonical source join and derives package records.
func Read(ctx context.Context, acquisition *Acquisition) (ReadResult, error) {
	songsDatabase, err := openReadOnly(filepath.Join(acquisition.Directory, "Songs.db"))
	if err != nil {
		return ReadResult{}, fmt.Errorf("open Songs.db: %w", err)
	}
	defer songsDatabase.Close()
	wordsDatabase, err := openReadOnly(filepath.Join(acquisition.Directory, "SongWords.db"))
	if err != nil {
		return ReadResult{}, fmt.Errorf("open SongWords.db: %w", err)
	}
	defer wordsDatabase.Close()

	if err := verifyDatabase(ctx, songsDatabase, "Songs.db", false); err != nil {
		return ReadResult{}, err
	}
	if err := verifyDatabase(ctx, wordsDatabase, "SongWords.db", true); err != nil {
		return ReadResult{}, err
	}
	words, err := readWords(ctx, wordsDatabase)
	if err != nil {
		return ReadResult{}, err
	}
	result, err := readSongs(ctx, songsDatabase, words)
	if err != nil {
		return ReadResult{}, err
	}
	if len(words) != len(result.Songs) {
		return ReadResult{}, fmt.Errorf(
			"source join is incomplete: %d song rows and %d word rows",
			len(result.Songs), len(words),
		)
	}

	for _, file := range acquisition.Files {
		if file.Name == "SongKeys.db" && file.Present {
			result.Diagnostics.SongKeysPresent = true
			keysDatabase, openErr := openReadOnly(filepath.Join(acquisition.Directory, file.Name))
			if openErr != nil {
				return ReadResult{}, fmt.Errorf("open SongKeys.db diagnostic: %w", openErr)
			}
			if verifyErr := verifyDatabase(ctx, keysDatabase, "SongKeys.db", true); verifyErr != nil {
				keysDatabase.Close()
				return ReadResult{}, verifyErr
			}
			if countErr := keysDatabase.QueryRowContext(ctx, "SELECT COUNT(*) FROM word_key").Scan(&result.Diagnostics.SongKeysRows); countErr != nil {
				keysDatabase.Close()
				return ReadResult{}, fmt.Errorf("read SongKeys.db diagnostic: %w", countErr)
			}
			keysDatabase.Close()
		}
	}
	return result, nil
}

func openReadOnly(path string) (*sql.DB, error) {
	location := &url.URL{Scheme: "file", Path: filepath.ToSlash(path)}
	database, err := sql.Open("sqlite", location.String()+"?mode=ro&immutable=1")
	if err != nil {
		return nil, err
	}
	database.SetMaxOpenConns(1)
	return database, nil
}

func verifyDatabase(ctx context.Context, database *sql.DB, name string, checkIndexes bool) error {
	if !checkIndexes {
		var schemaVersion int
		if err := database.QueryRowContext(ctx, "PRAGMA schema_version").Scan(&schemaVersion); err != nil {
			return fmt.Errorf("read %s schema: %w", name, err)
		}
		return nil
	}
	var result string
	if err := database.QueryRowContext(ctx, "PRAGMA quick_check").Scan(&result); err != nil {
		return fmt.Errorf("check %s: %w", name, err)
	}
	if result != "ok" {
		return fmt.Errorf("%s failed SQLite quick_check: %s", name, result)
	}
	return nil
}

func readWords(ctx context.Context, database *sql.DB) (map[int64]rawWord, error) {
	rows, err := database.QueryContext(ctx, `
		SELECT song_id, words, slide_uids, slide_layout_revisions, slide_revisions
		FROM word NOT INDEXED
		ORDER BY song_id
	`)
	if err != nil {
		return nil, fmt.Errorf("query SongWords.db: %w", err)
	}
	defer rows.Close()
	words := make(map[int64]rawWord)
	for rows.Next() {
		var songID int64
		var rawWords, rawSlideUIDs, layoutRevisions, revisions any
		if err := rows.Scan(&songID, &rawWords, &rawSlideUIDs, &layoutRevisions, &revisions); err != nil {
			return nil, fmt.Errorf("scan SongWords.db: %w", err)
		}
		if _, duplicate := words[songID]; duplicate {
			return nil, fmt.Errorf("duplicate SongWords.db song_id: %d", songID)
		}
		lyrics, ok := textValue(rawWords)
		if !ok || strings.TrimSpace(lyrics) == "" {
			return nil, fmt.Errorf("song_id %d has missing RTF lyrics", songID)
		}
		slideUIDText, _ := textValue(rawSlideUIDs)
		words[songID] = rawWord{
			words:                lyrics,
			slideUIDs:            splitSlideUIDs(slideUIDText),
			slideLayoutRevisions: layoutRevisions,
			slideRevisions:       revisions,
		}
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("iterate SongWords.db: %w", err)
	}
	return words, nil
}

func readSongs(ctx context.Context, database *sql.DB, words map[int64]rawWord) (ReadResult, error) {
	rows, err := database.QueryContext(ctx, `
		SELECT rowid, song_item_uid, song_rev_uid, song_uid, title, author,
		       copyright, administrator, description, tags, reference_number,
		       provider_id, vendor_id, presentation_id, layout_revision, revision
		FROM song NOT INDEXED
		ORDER BY rowid
	`)
	if err != nil {
		return ReadResult{}, fmt.Errorf("query Songs.db: %w", err)
	}
	defer rows.Close()

	result := ReadResult{}
	seenUIDs := make(map[string]bool)
	seenItemUIDs := make(map[string]bool)
	for rows.Next() {
		var rowID int64
		var itemUIDValue, revisionUIDValue, uidValue, titleValue any
		var author, copyright, administrator, description, tags, referenceNumber any
		var providerID, vendorID, presentationID, layoutRevision, revision any
		if err := rows.Scan(
			&rowID, &itemUIDValue, &revisionUIDValue, &uidValue, &titleValue,
			&author, &copyright, &administrator, &description, &tags, &referenceNumber,
			&providerID, &vendorID, &presentationID, &layoutRevision, &revision,
		); err != nil {
			return ReadResult{}, fmt.Errorf("scan Songs.db: %w", err)
		}
		itemUID, itemOK := requiredText(itemUIDValue)
		uid, uidOK := requiredText(uidValue)
		title, titleOK := requiredText(titleValue)
		if !itemOK || !uidOK || !titleOK {
			return ReadResult{}, fmt.Errorf("song rowid %d is missing required identity or title", rowID)
		}
		if seenUIDs[uid] {
			return ReadResult{}, fmt.Errorf("duplicate song_uid: %s", uid)
		}
		if seenItemUIDs[itemUID] {
			return ReadResult{}, fmt.Errorf("duplicate song_item_uid: %s", itemUID)
		}
		seenUIDs[uid] = true
		seenItemUIDs[itemUID] = true
		word, found := words[rowID]
		if !found {
			return ReadResult{}, fmt.Errorf("song rowid %d has no matching word.song_id", rowID)
		}
		parsed, parseErr := rtf.Parse(word.words, word.slideUIDs)
		if parseErr != nil {
			return ReadResult{}, fmt.Errorf("parse song_uid %s: %w", uid, parseErr)
		}
		for _, warning := range parsed.Warnings {
			result.Warnings = append(result.Warnings, contract.Warning{
				Code: "structural_anomaly", SongUID: uid, Message: warning,
			})
		}
		record := contract.SongRecord{
			ContractVersion: contract.Version,
			Source: contract.SongSource{
				System: "easyworship", SongRowID: rowID, SongItemUID: itemUID,
				SongUID: uid, SongRevisionUID: optionalString(revisionUIDValue),
				Revision: sourceValue(revision), LayoutRevision: sourceValue(layoutRevision),
				ProviderID: sourceValue(providerID), VendorID: sourceValue(vendorID),
				PresentationID: sourceValue(presentationID), SlideUIDs: word.slideUIDs,
				SlideLayoutRevisions: sourceValue(word.slideLayoutRevisions),
				SlideRevisions:       sourceValue(word.slideRevisions),
			},
			Metadata: contract.SongMetadata{
				Title: title, Author: optionalString(author), Copyright: optionalString(copyright),
				Administrator: optionalString(administrator), Description: optionalString(description),
				Tags: optionalString(tags), ReferenceNumber: optionalString(referenceNumber),
			},
			RawLyrics:     contract.RawLyrics{Format: "rtf", Content: word.words},
			CleanedLyrics: parsed.CleanedLyrics,
			Sections:      parsed.Sections,
		}
		record.Fingerprint = fingerprint(record)
		result.Songs = append(result.Songs, record)
	}
	if err := rows.Err(); err != nil {
		return ReadResult{}, fmt.Errorf("iterate Songs.db: %w", err)
	}
	return result, nil
}

func fingerprint(song contract.SongRecord) contract.SemanticFingerprint {
	components := contract.FingerprintComponents{
		Metadata:  digestJSON(song.Metadata),
		Lyrics:    digestJSON(song.CleanedLyrics),
		Structure: digestJSON(song.Sections),
		Presentation: digestJSON(struct {
			Format string `json:"format"`
			RTF    string `json:"rtf"`
		}{song.RawLyrics.Format, song.RawLyrics.Content}),
	}
	return contract.SemanticFingerprint{
		Version:    contract.FingerprintVersion,
		Components: components,
		Value: digestJSON(struct {
			Version    string                         `json:"version"`
			Components contract.FingerprintComponents `json:"components"`
		}{contract.FingerprintVersion, components}),
	}
}

func digestJSON(value any) string {
	encoded, err := json.Marshal(value)
	if err != nil {
		panic(fmt.Sprintf("marshal fingerprint input: %v", err))
	}
	hash := sha256.Sum256(encoded)
	return "sha256:" + hex.EncodeToString(hash[:])
}

func textValue(value any) (string, bool) {
	switch typed := value.(type) {
	case string:
		return typed, true
	case []byte:
		return string(typed), true
	default:
		return "", false
	}
}

func requiredText(value any) (string, bool) {
	text, ok := textValue(value)
	text = strings.TrimSpace(text)
	return text, ok && text != ""
}

func splitSlideUIDs(value string) []string {
	if strings.TrimSpace(value) == "" {
		return []string{}
	}
	parts := strings.Split(value, ",")
	result := make([]string, 0, len(parts))
	for _, part := range parts {
		if trimmed := strings.TrimSpace(part); trimmed != "" {
			result = append(result, trimmed)
		}
	}
	return result
}
