// Package exporter coordinates safe source acquisition and package creation.
package exporter

import (
	"context"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"time"

	"github.com/nicksspirit/worship-prep-platform/exporter/internal/contract"
	"github.com/nicksspirit/worship-prep-platform/exporter/internal/outbox"
	"github.com/nicksspirit/worship-prep-platform/exporter/internal/runstate"
	"github.com/nicksspirit/worship-prep-platform/exporter/internal/source"
)

var uuidPattern = regexp.MustCompile(`^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$`)

// Config identifies one Catalog Import Run and its local output.
type Config struct {
	DataDirectory      string
	OutputPath         string
	StateDirectory     string
	RunID              string
	ExporterInstanceID string
	ExporterVersion    string
	CreatedAt          time.Time
	Detector           source.ProcessDetector
}

// Result describes an operator-visible exporter outcome.
type Result struct {
	Status   string
	Manifest contract.Manifest
	SHA256   string
}

// Run builds a package exclusively from temporary source copies.
func Run(ctx context.Context, config Config) (Result, error) {
	if err := validate(config); err != nil {
		return Result{}, err
	}
	var err error
	config.DataDirectory, err = filepath.Abs(config.DataDirectory)
	if err != nil {
		return Result{}, fmt.Errorf("resolve data directory: %w", err)
	}
	config.OutputPath, err = filepath.Abs(config.OutputPath)
	if err != nil {
		return Result{}, fmt.Errorf("resolve output path: %w", err)
	}
	config.StateDirectory, err = filepath.Abs(config.StateDirectory)
	if err != nil {
		return Result{}, fmt.Errorf("resolve state directory: %w", err)
	}
	lock, err := runstate.AcquireLock(config.StateDirectory, config.RunID)
	if err != nil {
		return Result{}, err
	}
	defer lock.Release()
	started := outbox.Event{RunID: config.RunID, Type: "started", OccurredAt: config.CreatedAt}
	if err := outbox.Append(config.StateDirectory, started); err != nil {
		return Result{}, err
	}

	acquisition, err := source.Acquire(config.DataDirectory, config.Detector)
	if errors.Is(err, source.ErrSourceInUse) {
		event := outbox.Event{
			RunID: config.RunID, Type: "skipped_source_in_use", OccurredAt: time.Now().UTC(),
		}
		if appendErr := outbox.Append(config.StateDirectory, event); appendErr != nil {
			return Result{}, appendErr
		}
		return Result{Status: "skipped_source_in_use"}, nil
	}
	if err != nil {
		_ = appendFailure(config, err)
		return Result{}, err
	}
	defer acquisition.Cleanup()

	readResult, err := source.Read(ctx, acquisition)
	if err != nil {
		_ = appendFailure(config, err)
		return Result{}, err
	}
	manifest := contract.Manifest{
		RunID: config.RunID, ExporterInstanceID: config.ExporterInstanceID,
		ExporterVersion: config.ExporterVersion, CreatedAt: config.CreatedAt.UTC(),
		Source: contract.SourceManifest{
			System: "easyworship", Files: acquisition.Files, Diagnostics: readResult.Diagnostics,
		},
		Warnings: readResult.Warnings,
	}
	existing, found, err := runstate.Load(config.StateDirectory, config.RunID)
	if err != nil {
		return Result{}, err
	}
	packagePath := config.OutputPath
	if found {
		candidateDirectory := filepath.Join(config.StateDirectory, "candidates")
		if err := os.MkdirAll(candidateDirectory, 0o700); err != nil {
			return Result{}, fmt.Errorf("create candidate directory: %w", err)
		}
		candidate, err := os.CreateTemp(candidateDirectory, config.RunID+"-*.zip")
		if err != nil {
			return Result{}, fmt.Errorf("reserve candidate package: %w", err)
		}
		packagePath = candidate.Name()
		candidate.Close()
		if err := os.Remove(packagePath); err != nil {
			return Result{}, fmt.Errorf("prepare candidate package: %w", err)
		}
		defer os.Remove(packagePath)
	}
	manifest, err = contract.Build(packagePath, manifest, readResult.Songs)
	if err != nil {
		_ = appendFailure(config, err)
		return Result{}, err
	}
	if found {
		if !runstate.SameContent(existing, manifest) {
			conflict := fmt.Errorf("Catalog Import Run ID conflict: %s is already bound to different content", config.RunID)
			_ = outbox.Append(config.StateDirectory, outbox.Event{
				RunID: config.RunID, Type: "run_identity_conflict", OccurredAt: time.Now().UTC(),
			})
			return Result{}, conflict
		}
		packagePath = existing.PackagePath
		manifest = existing.Manifest
	}
	packageFile, err := os.Open(packagePath)
	if err != nil {
		return Result{}, fmt.Errorf("open completed package: %w", err)
	}
	checksum, err := contract.SHA256(packageFile)
	packageFile.Close()
	if err != nil {
		return Result{}, fmt.Errorf("checksum completed package: %w", err)
	}
	if found && checksum != existing.PackageSHA256 {
		return Result{}, fmt.Errorf("stored package checksum no longer matches run state")
	}
	if found {
		event := outbox.Event{
			RunID: config.RunID, Type: "package_reused", OccurredAt: time.Now().UTC(),
			Details: map[string]any{"package_sha256": checksum},
		}
		if err := outbox.Append(config.StateDirectory, event); err != nil {
			return Result{}, err
		}
		return Result{Status: "package_reused", Manifest: manifest, SHA256: checksum}, nil
	}
	if err := runstate.Save(config.StateDirectory, config.RunID, runstate.Record{
		Manifest: manifest, PackagePath: config.OutputPath, PackageSHA256: checksum,
	}); err != nil {
		return Result{}, err
	}
	event := outbox.Event{
		RunID: config.RunID, Type: "package_created", OccurredAt: time.Now().UTC(),
		Details: map[string]any{
			"package_sha256": checksum,
			"songs":          manifest.Counts.Songs,
			"warnings":       manifest.Counts.Warnings,
		},
	}
	if err := outbox.Append(config.StateDirectory, event); err != nil {
		return Result{}, err
	}
	return Result{Status: "package_created", Manifest: manifest, SHA256: checksum}, nil
}

func validate(config Config) error {
	required := map[string]string{
		"data directory": config.DataDirectory, "output path": config.OutputPath,
		"state directory": config.StateDirectory, "run ID": config.RunID,
		"exporter instance ID": config.ExporterInstanceID, "exporter version": config.ExporterVersion,
	}
	for name, value := range required {
		if value == "" {
			return fmt.Errorf("%s is required", name)
		}
	}
	if config.CreatedAt.IsZero() {
		return fmt.Errorf("created time is required")
	}
	if config.Detector == nil {
		return fmt.Errorf("process detector is required")
	}
	if !uuidPattern.MatchString(config.RunID) {
		return fmt.Errorf("run ID must be a UUID")
	}
	if !uuidPattern.MatchString(config.ExporterInstanceID) {
		return fmt.Errorf("exporter instance ID must be a UUID")
	}
	return nil
}

func appendFailure(config Config, failure error) error {
	return outbox.Append(config.StateDirectory, outbox.Event{
		RunID: config.RunID, Type: "failed", OccurredAt: time.Now().UTC(),
		Details: map[string]any{"error": failure.Error()},
	})
}
