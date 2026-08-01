// Package runstate prevents one Catalog Import Run ID from naming different content.
package runstate

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"

	"github.com/nicksspirit/worship-prep-platform/exporter/internal/contract"
)

// Record binds one run identity to the package content created for it.
type Record struct {
	Manifest      contract.Manifest `json:"manifest"`
	PackagePath   string            `json:"package_path"`
	PackageSHA256 string            `json:"package_sha256"`
}

// Lock serializes local attempts for one run identity.
type Lock struct{ path string }

// AcquireLock prevents concurrent processes from racing package and state writes.
func AcquireLock(stateDirectory string, runID string) (*Lock, error) {
	directory := filepath.Join(stateDirectory, "locks")
	if err := os.MkdirAll(directory, 0o700); err != nil {
		return nil, fmt.Errorf("create run lock directory: %w", err)
	}
	path := filepath.Join(directory, runID)
	if err := os.Mkdir(path, 0o700); err != nil {
		if errors.Is(err, os.ErrExist) {
			return nil, fmt.Errorf("Catalog Import Run %s is already active", runID)
		}
		return nil, fmt.Errorf("acquire run lock: %w", err)
	}
	return &Lock{path: path}, nil
}

// Release frees a local run lock.
func (lock *Lock) Release() error { return os.Remove(lock.path) }

// Load returns the existing run binding, if any.
func Load(stateDirectory string, runID string) (Record, bool, error) {
	path := filepath.Join(stateDirectory, "runs", runID+".json")
	data, err := os.ReadFile(path)
	if errors.Is(err, os.ErrNotExist) {
		return Record{}, false, nil
	}
	if err != nil {
		return Record{}, false, fmt.Errorf("read run state: %w", err)
	}
	var record Record
	if err := json.Unmarshal(data, &record); err != nil {
		return Record{}, false, fmt.Errorf("decode run state: %w", err)
	}
	return record, true, nil
}

// Save atomically creates a run binding and never overwrites an existing identity.
func Save(stateDirectory string, runID string, record Record) error {
	directory := filepath.Join(stateDirectory, "runs")
	if err := os.MkdirAll(directory, 0o700); err != nil {
		return fmt.Errorf("create run state directory: %w", err)
	}
	data, err := json.MarshalIndent(record, "", "  ")
	if err != nil {
		return fmt.Errorf("encode run state: %w", err)
	}
	data = append(data, '\n')
	path := filepath.Join(directory, runID+".json")
	file, err := os.OpenFile(path, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0o600)
	if err != nil {
		return fmt.Errorf("create run state: %w", err)
	}
	committed := false
	defer func() {
		_ = file.Close()
		if !committed {
			_ = os.Remove(path)
		}
	}()
	if _, err := file.Write(data); err != nil {
		return fmt.Errorf("write run state: %w", err)
	}
	if err := file.Sync(); err != nil {
		return fmt.Errorf("sync run state: %w", err)
	}
	if err := file.Close(); err != nil {
		return fmt.Errorf("close run state: %w", err)
	}
	committed = true
	return nil
}

// SameContent reports whether a candidate is an idempotent rerun.
func SameContent(existing Record, candidate contract.Manifest) bool {
	return existing.Manifest.ContractVersion == candidate.ContractVersion &&
		existing.Manifest.ParserVersion == candidate.ParserVersion &&
		existing.Manifest.ExporterInstanceID == candidate.ExporterInstanceID &&
		existing.Manifest.Source.Fingerprint == candidate.Source.Fingerprint &&
		existing.Manifest.Records.Fingerprint == candidate.Records.Fingerprint
}
