// Package source safely acquires and reads copied EasyWorship databases.
package source

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"

	"github.com/nicksspirit/worship-prep-platform/exporter/internal/contract"
)

var ErrSourceInUse = errors.New("EasyWorship is running")

var sourceFiles = []struct {
	name     string
	required bool
}{
	{"Songs.db", true},
	{"SongWords.db", true},
	{"SongKeys.db", false},
}

// ProcessDetector reports whether EasyWorship is currently using its library.
type ProcessDetector interface {
	EasyWorshipRunning() (bool, error)
}

// Acquisition owns temporary copies of the EasyWorship source files.
type Acquisition struct {
	Directory string
	Files     []contract.SourceFile
}

// Cleanup removes every temporary source copy.
func (a *Acquisition) Cleanup() error {
	return os.RemoveAll(a.Directory)
}

// Acquire copies required databases into a unique temporary directory.
func Acquire(dataDirectory string, detector ProcessDetector) (*Acquisition, error) {
	running, err := detector.EasyWorshipRunning()
	if err != nil {
		return nil, fmt.Errorf("detect EasyWorship process: %w", err)
	}
	if running {
		return nil, ErrSourceInUse
	}

	temporary, err := os.MkdirTemp("", "wpp-catalog-source-*")
	if err != nil {
		return nil, fmt.Errorf("create temporary source directory: %w", err)
	}
	acquisition := &Acquisition{Directory: temporary}
	committed := false
	defer func() {
		if !committed {
			_ = acquisition.Cleanup()
		}
	}()

	for _, specification := range sourceFiles {
		sourcePath := filepath.Join(dataDirectory, specification.name)
		file := contract.SourceFile{Name: specification.name, Required: specification.required}
		info, statErr := os.Stat(sourcePath)
		if statErr != nil {
			if errors.Is(statErr, os.ErrNotExist) && !specification.required {
				acquisition.Files = append(acquisition.Files, file)
				continue
			}
			if errors.Is(statErr, os.ErrNotExist) {
				return nil, fmt.Errorf("required EasyWorship database is missing: %s", specification.name)
			}
			return nil, fmt.Errorf("inspect %s: %w", specification.name, statErr)
		}
		if !info.Mode().IsRegular() {
			return nil, fmt.Errorf("EasyWorship source is not a regular file: %s", specification.name)
		}

		destinationPath := filepath.Join(temporary, specification.name)
		size, checksum, copyErr := copyAndHash(sourcePath, destinationPath)
		if copyErr != nil {
			return nil, fmt.Errorf("copy %s: %w", specification.name, copyErr)
		}
		file.Present = true
		file.Size = size
		file.SHA256 = checksum
		acquisition.Files = append(acquisition.Files, file)
	}
	running, err = detector.EasyWorshipRunning()
	if err != nil {
		return nil, fmt.Errorf("recheck EasyWorship process: %w", err)
	}
	if running {
		return nil, ErrSourceInUse
	}
	committed = true
	return acquisition, nil
}

func copyAndHash(sourcePath string, destinationPath string) (int64, string, error) {
	sourceFile, err := os.Open(sourcePath)
	if err != nil {
		return 0, "", err
	}
	defer sourceFile.Close()

	destinationFile, err := os.OpenFile(destinationPath, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0o600)
	if err != nil {
		return 0, "", err
	}
	committed := false
	defer func() {
		_ = destinationFile.Close()
		if !committed {
			_ = os.Remove(destinationPath)
		}
	}()

	hash := sha256.New()
	size, err := io.Copy(io.MultiWriter(destinationFile, hash), sourceFile)
	if err != nil {
		return 0, "", err
	}
	if err := destinationFile.Sync(); err != nil {
		return 0, "", err
	}
	if err := destinationFile.Close(); err != nil {
		return 0, "", err
	}
	committed = true
	return size, "sha256:" + hex.EncodeToString(hash.Sum(nil)), nil
}
