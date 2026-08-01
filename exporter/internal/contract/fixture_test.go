package contract

import (
	"bufio"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestSharedValidFixtureMatchesContract(t *testing.T) {
	t.Parallel()
	directory := filepath.Join("..", "..", "..", "contracts", "catalog-import", "v1")
	for _, name := range []string{"manifest.schema.json", "song.schema.json"} {
		data, err := os.ReadFile(filepath.Join(directory, name))
		if err != nil {
			t.Fatal(err)
		}
		var schema map[string]any
		if err := json.Unmarshal(data, &schema); err != nil {
			t.Fatalf("%s is not JSON: %v", name, err)
		}
	}

	fixtureDirectory := filepath.Join(directory, "fixtures", "valid")
	manifestBytes, err := os.ReadFile(filepath.Join(fixtureDirectory, "manifest.json"))
	if err != nil {
		t.Fatal(err)
	}
	var manifest Manifest
	if err := json.Unmarshal(manifestBytes, &manifest); err != nil {
		t.Fatal(err)
	}
	if manifest.ContractVersion != Version || manifest.ParserVersion != ParserVersion {
		t.Fatalf("fixture manifest versions = %q, %q", manifest.ContractVersion, manifest.ParserVersion)
	}

	recordFile, err := os.Open(filepath.Join(fixtureDirectory, RecordsPath))
	if err != nil {
		t.Fatal(err)
	}
	defer recordFile.Close()
	checksum, err := SHA256(recordFile)
	if err != nil {
		t.Fatal(err)
	}
	if checksum != manifest.Records.SHA256 {
		t.Fatalf("fixture checksum = %q, manifest = %q", checksum, manifest.Records.SHA256)
	}
	if _, err := recordFile.Seek(0, 0); err != nil {
		t.Fatal(err)
	}
	scanner := bufio.NewScanner(recordFile)
	count := 0
	for scanner.Scan() {
		if strings.TrimSpace(scanner.Text()) == "" {
			t.Fatal("fixture contains a blank NDJSON line")
		}
		var song SongRecord
		if err := json.Unmarshal(scanner.Bytes(), &song); err != nil {
			t.Fatal(err)
		}
		if song.ContractVersion != Version || song.Fingerprint.Version != FingerprintVersion {
			t.Fatalf("fixture song versions = %q, %q", song.ContractVersion, song.Fingerprint.Version)
		}
		count++
	}
	if err := scanner.Err(); err != nil {
		t.Fatal(err)
	}
	if count != manifest.Counts.Songs {
		t.Fatalf("fixture records = %d, manifest = %d", count, manifest.Counts.Songs)
	}
}
