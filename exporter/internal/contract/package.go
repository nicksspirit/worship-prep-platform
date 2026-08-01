package contract

import (
	"archive/zip"
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"
)

// Build writes a deterministic Catalog Import Package and returns its manifest.
func Build(path string, manifest Manifest, songs []SongRecord) (Manifest, error) {
	if _, err := os.Stat(path); err == nil {
		return Manifest{}, fmt.Errorf("package already exists: %s", path)
	} else if !os.IsNotExist(err) {
		return Manifest{}, fmt.Errorf("inspect package path: %w", err)
	}
	var records bytes.Buffer
	encoder := json.NewEncoder(&records)
	encoder.SetEscapeHTML(false)
	for _, song := range songs {
		if err := encoder.Encode(song); err != nil {
			return Manifest{}, fmt.Errorf("encode song %q: %w", song.Source.SongUID, err)
		}
	}

	recordBytes := records.Bytes()
	recordHash := digest(recordBytes)
	manifest.ContractVersion = Version
	manifest.ParserVersion = ParserVersion
	if manifest.Warnings == nil {
		manifest.Warnings = []Warning{}
	}
	manifest.Records = RecordsManifest{
		Path:        RecordsPath,
		MediaType:   "application/x-ndjson",
		SHA256:      recordHash,
		Bytes:       len(recordBytes),
		Fingerprint: recordHash,
	}
	manifest.Counts.Songs = len(songs)
	manifest.Counts.Warnings = len(manifest.Warnings)
	sort.Slice(manifest.Source.Files, func(i, j int) bool {
		return manifest.Source.Files[i].Name < manifest.Source.Files[j].Name
	})
	manifest.Source.Fingerprint = sourceFingerprint(manifest.Source.Files)

	manifestBytes, err := json.MarshalIndent(manifest, "", "  ")
	if err != nil {
		return Manifest{}, fmt.Errorf("encode manifest: %w", err)
	}
	manifestBytes = append(manifestBytes, '\n')

	if err := os.MkdirAll(filepath.Dir(path), 0o750); err != nil {
		return Manifest{}, fmt.Errorf("create package directory: %w", err)
	}
	temporary, err := os.CreateTemp(filepath.Dir(path), ".catalog-import-*.zip")
	if err != nil {
		return Manifest{}, fmt.Errorf("create temporary package: %w", err)
	}
	temporaryPath := temporary.Name()
	committed := false
	defer func() {
		_ = temporary.Close()
		if !committed {
			_ = os.Remove(temporaryPath)
		}
	}()

	archive := zip.NewWriter(temporary)
	for _, entry := range []struct {
		name string
		data []byte
	}{{"manifest.json", manifestBytes}, {RecordsPath, recordBytes}} {
		header := &zip.FileHeader{Name: entry.name, Method: zip.Deflate}
		header.SetMode(0o640)
		header.Modified = manifest.CreatedAt.UTC().Truncate(time.Second)
		writer, createErr := archive.CreateHeader(header)
		if createErr != nil {
			return Manifest{}, fmt.Errorf("create archive entry %q: %w", entry.name, createErr)
		}
		if _, writeErr := writer.Write(entry.data); writeErr != nil {
			return Manifest{}, fmt.Errorf("write archive entry %q: %w", entry.name, writeErr)
		}
	}
	if err := archive.Close(); err != nil {
		return Manifest{}, fmt.Errorf("close package archive: %w", err)
	}
	if err := temporary.Sync(); err != nil {
		return Manifest{}, fmt.Errorf("sync package archive: %w", err)
	}
	if err := temporary.Close(); err != nil {
		return Manifest{}, fmt.Errorf("close package file: %w", err)
	}
	if err := os.Rename(temporaryPath, path); err != nil {
		return Manifest{}, fmt.Errorf("publish package: %w", err)
	}
	committed = true
	return manifest, nil
}

func sourceFingerprint(files []SourceFile) string {
	var source strings.Builder
	for _, file := range files {
		fmt.Fprintf(&source, "%s\x00%t\x00%t\x00%d\x00%s\n", file.Name, file.Required, file.Present, file.Size, file.SHA256)
	}
	return digest([]byte(source.String()))
}

func digest(data []byte) string {
	hash := sha256.Sum256(data)
	return "sha256:" + hex.EncodeToString(hash[:])
}

// SHA256 returns a prefixed checksum for a stream.
func SHA256(reader io.Reader) (string, error) {
	hash := sha256.New()
	if _, err := io.Copy(hash, reader); err != nil {
		return "", err
	}
	return "sha256:" + hex.EncodeToString(hash.Sum(nil)), nil
}
