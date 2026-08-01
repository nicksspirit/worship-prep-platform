package contract

import (
	"archive/zip"
	"encoding/json"
	"io"
	"path/filepath"
	"testing"
	"time"
)

func TestBuildEncodesEmptySectionsAsArray(t *testing.T) {
	t.Parallel()
	path := filepath.Join(t.TempDir(), "catalog-import.zip")
	manifest := Manifest{CreatedAt: time.Date(2026, 8, 1, 0, 0, 0, 0, time.UTC)}
	song := SongRecord{Sections: nil}

	if _, err := Build(path, manifest, []SongRecord{song}); err != nil {
		t.Fatal(err)
	}

	archive, err := zip.OpenReader(path)
	if err != nil {
		t.Fatal(err)
	}
	defer archive.Close()
	reader, err := archive.File[1].Open()
	if err != nil {
		t.Fatal(err)
	}
	defer reader.Close()
	data, err := io.ReadAll(reader)
	if err != nil {
		t.Fatal(err)
	}
	var record map[string]any
	if err := json.Unmarshal(data, &record); err != nil {
		t.Fatal(err)
	}
	sections, ok := record["sections"].([]any)
	if !ok || len(sections) != 0 {
		t.Fatalf("sections = %#v, want []", record["sections"])
	}
}
