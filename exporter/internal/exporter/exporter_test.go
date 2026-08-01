package exporter

import (
	"archive/zip"
	"bufio"
	"context"
	"database/sql"
	"encoding/json"
	"io"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/nicksspirit/worship-prep-platform/exporter/internal/contract"
	_ "modernc.org/sqlite"
)

type detector struct{ running bool }

func (d detector) EasyWorshipRunning() (bool, error) { return d.running, nil }

func TestRunBuildsVersionedPackageFromCopiedDatabases(t *testing.T) {
	t.Parallel()
	dataDirectory := createSourceFixture(t, true)
	stateDirectory := t.TempDir()
	outputPath := filepath.Join(t.TempDir(), "catalog-import.zip")
	createdAt := time.Date(2026, 8, 1, 12, 30, 0, 0, time.UTC)

	result, err := Run(context.Background(), Config{
		DataDirectory: dataDirectory, OutputPath: outputPath, StateDirectory: stateDirectory,
		RunID:              "11111111-1111-4111-8111-111111111111",
		ExporterInstanceID: "22222222-2222-4222-8222-222222222222",
		ExporterVersion:    "test", CreatedAt: createdAt, Detector: detector{},
	})
	if err != nil {
		t.Fatalf("Run() error = %v", err)
	}
	if result.Status != "package_created" || result.Manifest.Counts.Songs != 1 {
		t.Fatalf("Run() result = %#v", result)
	}
	if !result.Manifest.Source.Diagnostics.SongKeysPresent || result.Manifest.Source.Diagnostics.SongKeysRows != 1 {
		t.Fatalf("SongKeys diagnostics = %#v", result.Manifest.Source.Diagnostics)
	}

	archive, err := zip.OpenReader(outputPath)
	if err != nil {
		t.Fatal(err)
	}
	defer archive.Close()
	if len(archive.File) != 2 || archive.File[0].Name != "manifest.json" || archive.File[1].Name != "songs.ndjson" {
		t.Fatalf("archive entries = %#v", archive.File)
	}
	manifestBytes := readZipEntry(t, archive.File[0])
	var manifest contract.Manifest
	if err := json.Unmarshal(manifestBytes, &manifest); err != nil {
		t.Fatal(err)
	}
	if manifest.ContractVersion != contract.Version || manifest.Records.SHA256 == "" || manifest.Source.Fingerprint == "" {
		t.Fatalf("manifest = %#v", manifest)
	}
	recordBytes := readZipEntry(t, archive.File[1])
	checksum, err := contract.SHA256(strings.NewReader(string(recordBytes)))
	if err != nil {
		t.Fatal(err)
	}
	if checksum != manifest.Records.SHA256 {
		t.Fatalf("records checksum = %q, manifest = %q", checksum, manifest.Records.SHA256)
	}
	var song contract.SongRecord
	if err := json.Unmarshal(recordBytes, &song); err != nil {
		t.Fatal(err)
	}
	if song.Source.SongUID != "song-uid-1" || song.RawLyrics.Content == "" {
		t.Fatalf("song source evidence = %#v", song.Source)
	}
	if got, want := song.Sections[0].Label, "verse"; got != want {
		t.Errorf("normalized section label = %q, want %q", got, want)
	}
	if song.Fingerprint.Version != contract.FingerprintVersion || song.Fingerprint.Components.Lyrics == "" {
		t.Fatalf("semantic fingerprint = %#v", song.Fingerprint)
	}

	events, err := os.Open(filepath.Join(stateDirectory, "outbox", "11111111-1111-4111-8111-111111111111.ndjson"))
	if err != nil {
		t.Fatal(err)
	}
	defer events.Close()
	var eventTypes []string
	scanner := bufio.NewScanner(events)
	for scanner.Scan() {
		var event struct {
			Type string `json:"type"`
		}
		if err := json.Unmarshal(scanner.Bytes(), &event); err != nil {
			t.Fatal(err)
		}
		eventTypes = append(eventTypes, event.Type)
	}
	if got, want := strings.Join(eventTypes, ","), "started,package_created"; got != want {
		t.Fatalf("outbox events = %q, want %q", got, want)
	}
}

func TestRunRecordsSourceInUseWithoutReadingDatabases(t *testing.T) {
	t.Parallel()
	stateDirectory := t.TempDir()
	result, err := Run(context.Background(), Config{
		DataDirectory: t.TempDir(), OutputPath: filepath.Join(t.TempDir(), "unused.zip"),
		StateDirectory: stateDirectory, RunID: "33333333-3333-4333-8333-333333333333",
		ExporterInstanceID: "44444444-4444-4444-8444-444444444444",
		ExporterVersion:    "test", CreatedAt: time.Now(), Detector: detector{running: true},
	})
	if err != nil {
		t.Fatalf("Run() error = %v", err)
	}
	if result.Status != "skipped_source_in_use" {
		t.Fatalf("Run() status = %q", result.Status)
	}
	events, err := os.ReadFile(filepath.Join(stateDirectory, "outbox", "33333333-3333-4333-8333-333333333333.ndjson"))
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(string(events), `"type":"skipped_source_in_use"`) {
		t.Fatalf("outbox does not contain skipped event: %s", events)
	}
}

func TestRunReusesIdenticalPackageAndRejectsConflictingRunIdentity(t *testing.T) {
	t.Parallel()
	dataDirectory := createSourceFixture(t, false)
	stateDirectory := t.TempDir()
	config := Config{
		DataDirectory: dataDirectory, OutputPath: filepath.Join(t.TempDir(), "catalog-import.zip"),
		StateDirectory: stateDirectory, RunID: "55555555-5555-4555-8555-555555555555",
		ExporterInstanceID: "66666666-6666-4666-8666-666666666666",
		ExporterVersion:    "test", CreatedAt: time.Now(), Detector: detector{},
	}
	first, err := Run(context.Background(), config)
	if err != nil {
		t.Fatal(err)
	}
	config.CreatedAt = config.CreatedAt.Add(time.Minute)
	second, err := Run(context.Background(), config)
	if err != nil {
		t.Fatalf("idempotent Run() error = %v", err)
	}
	if second.Status != "package_reused" || second.SHA256 != first.SHA256 {
		t.Fatalf("idempotent Run() = %#v, first = %#v", second, first)
	}

	database := openFixtureDatabase(t, filepath.Join(dataDirectory, "Songs.db"))
	execFixture(t, database, `UPDATE song SET title = 'Changed title' WHERE rowid = 42`)
	database.Close()
	config.CreatedAt = config.CreatedAt.Add(time.Minute)
	if _, err := Run(context.Background(), config); err == nil || !strings.Contains(err.Error(), "Run ID conflict") {
		t.Fatalf("conflicting Run() error = %v", err)
	}
}

func createSourceFixture(t *testing.T, includeKeys bool) string {
	t.Helper()
	directory := t.TempDir()
	songs := openFixtureDatabase(t, filepath.Join(directory, "Songs.db"))
	execFixture(t, songs, `CREATE TABLE song (
		rowid INTEGER PRIMARY KEY, song_item_uid TEXT, song_rev_uid TEXT, song_uid TEXT,
		title TEXT, author TEXT, copyright TEXT, administrator TEXT, description TEXT,
		tags TEXT, reference_number TEXT, provider_id INTEGER, vendor_id INTEGER,
		presentation_id INTEGER, layout_revision INTEGER, revision INTEGER)`)
	execFixture(t, songs, `INSERT INTO song VALUES (
		42, 'item-uid-1', 'rev-uid-1', 'song-uid-1', 'Amazing Grace', 'John Newton',
		NULL, NULL, NULL, NULL, NULL, -1, 0, 12, 100, 200)`)
	songs.Close()

	words := openFixtureDatabase(t, filepath.Join(directory, "SongWords.db"))
	execFixture(t, words, `CREATE TABLE word (
		rowid INTEGER PRIMARY KEY, song_id INTEGER, words TEXT, slide_uids TEXT,
		slide_layout_revisions BLOB, slide_revisions BLOB)`)
	execFixture(t, words, `INSERT INTO word VALUES (
		1, 42, '{\rtf1\ansi{\sdparawysiwghidden Verse 1\par}Amazing grace\line How sweet the sound}',
		'slide-uid-1', X'0102', X'0304')`)
	words.Close()

	if includeKeys {
		keys := openFixtureDatabase(t, filepath.Join(directory, "SongKeys.db"))
		execFixture(t, keys, `CREATE TABLE word_key (link_id INTEGER, word_list_id INTEGER, field_flag INTEGER)`)
		execFixture(t, keys, `INSERT INTO word_key VALUES (42, 1, 3)`)
		keys.Close()
	}
	return directory
}

func openFixtureDatabase(t *testing.T, path string) *sql.DB {
	t.Helper()
	database, err := sql.Open("sqlite", path)
	if err != nil {
		t.Fatal(err)
	}
	return database
}

func execFixture(t *testing.T, database *sql.DB, statement string) {
	t.Helper()
	if _, err := database.Exec(statement); err != nil {
		t.Fatal(err)
	}
}

func readZipEntry(t *testing.T, file *zip.File) []byte {
	t.Helper()
	reader, err := file.Open()
	if err != nil {
		t.Fatal(err)
	}
	defer reader.Close()
	data, err := io.ReadAll(reader)
	if err != nil {
		t.Fatal(err)
	}
	return data
}
