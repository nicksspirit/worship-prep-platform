package main

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/nicksspirit/worship-prep-platform/exporter/internal/credential"
	"github.com/nicksspirit/worship-prep-platform/exporter/internal/delivery"
	"github.com/nicksspirit/worship-prep-platform/exporter/internal/exporter"
	"github.com/nicksspirit/worship-prep-platform/exporter/internal/outbox"
	"github.com/nicksspirit/worship-prep-platform/exporter/internal/runstate"
	"github.com/nicksspirit/worship-prep-platform/exporter/internal/source"
)

var version = "dev"

func main() {
	os.Exit(run())
}

func run() int {
	var dataDirectory, outputPath, stateDirectory, runID, instanceID string
	var endpoint, apiKeyFile string
	var scheduled bool
	flag.StringVar(&dataDirectory, "data-dir", environmentDefault("", "WPP_CATALOG_EXPORTER_DATA_DIR", "EASYWORSHIP_DATA_DIR"), "EasyWorship Data directory")
	flag.StringVar(&outputPath, "output", "", "Catalog Import Package output path")
	flag.StringVar(&stateDirectory, "state-dir", environmentDefault(".catalog-exporter", "WPP_CATALOG_EXPORTER_STATE_DIR"), "durable local state directory")
	flag.StringVar(&runID, "run-id", "", "Catalog Import Run UUID (generated when omitted)")
	flag.StringVar(&instanceID, "instance-id", environmentDefault("", "WPP_CATALOG_EXPORTER_INSTANCE_ID"), "stable Catalog Exporter instance UUID")
	flag.StringVar(&endpoint, "endpoint", environmentDefault("", "WPP_CATALOG_EXPORTER_ENDPOINT"), "Worship Prep Platform HTTPS base URL")
	flag.StringVar(&apiKeyFile, "api-key-file", environmentDefault("", "WPP_CATALOG_EXPORTER_API_KEY_FILE"), "user-scoped Windows DPAPI credential file")
	flag.BoolVar(&scheduled, "scheduled", false, "identify this as the weekly scheduled Catalog Import")
	flag.Parse()

	stateDirectory, err := filepath.Abs(stateDirectory)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error: resolve state directory: %v\n", err)
		return 1
	}
	apiKey := ""
	if endpoint != "" {
		if apiKeyFile == "" {
			fmt.Fprintln(os.Stderr, "Error: --api-key-file is required with --endpoint")
			return 1
		}
		apiKey, err = credential.Load(apiKeyFile)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error: %v\n", err)
			return 1
		}
		replayed, err := replayPending(context.Background(), stateDirectory, endpoint, apiKey, scheduled)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error: %v\n", err)
			return 1
		}
		if replayed {
			fmt.Println("Delivered retained Catalog Import work.")
			return 0
		}
	}

	if runID == "" {
		runID, err = newUUID()
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error: generate run ID: %v\n", err)
			return 1
		}
	}
	if outputPath == "" {
		outputPath = filepath.Join(stateDirectory, "packages", runID+".zip")
	}
	result, err := exporter.Run(context.Background(), exporter.Config{
		DataDirectory: dataDirectory, OutputPath: outputPath, StateDirectory: stateDirectory,
		RunID: runID, ExporterInstanceID: instanceID, ExporterVersion: version,
		CreatedAt: time.Now().UTC(), Detector: source.PlatformProcessDetector{},
	})
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		return 1
	}
	if result.Status == "skipped_source_in_use" {
		fmt.Printf("Catalog Import Run %s skipped: EasyWorship is running.\n", runID)
		return 0
	}
	if endpoint != "" {
		if err := deliverRun(context.Background(), stateDirectory, runID, endpoint, apiKey, scheduled); err != nil {
			fmt.Fprintf(os.Stderr, "Error: %v\n", err)
			return 1
		}
	}
	action := "created"
	if result.Status == "package_reused" {
		action = "reused"
	}
	fmt.Printf(
		"Catalog Import Run %s %s %s (%d songs, %d warnings, %s).\n",
		runID, action, outputPath, result.Manifest.Counts.Songs,
		result.Manifest.Counts.Warnings, result.SHA256,
	)
	return 0
}

func environmentDefault(fallback string, names ...string) string {
	for _, name := range names {
		if value := strings.TrimSpace(os.Getenv(name)); value != "" {
			return value
		}
	}
	return fallback
}

func replayPending(ctx context.Context, stateDirectory, endpoint, apiKey string, scheduled bool) (bool, error) {
	pending, err := outbox.Pending(stateDirectory)
	if err != nil {
		return false, err
	}
	delivered := false
	for _, run := range pending {
		_, found, err := runstate.Load(stateDirectory, run.RunID)
		if err != nil {
			return delivered, err
		}
		if !found {
			// Source-in-use and early source failures have durable local events but no
			// package that the Catalog Import endpoint can identify yet.
			continue
		}
		if err := deliverRun(ctx, stateDirectory, run.RunID, endpoint, apiKey, scheduled); err != nil {
			return delivered, err
		}
		delivered = true
	}
	return delivered, nil
}

func deliverRun(ctx context.Context, stateDirectory, runID, endpoint, apiKey string, scheduled bool) error {
	record, found, err := runstate.Load(stateDirectory, runID)
	if err != nil {
		return err
	}
	if !found {
		return fmt.Errorf("run %s has events but no durable package state", runID)
	}
	eventsPath := filepath.Join(stateDirectory, "outbox", runID+".ndjson")
	if err := delivery.Send(ctx, delivery.Config{
		Endpoint: endpoint, APIKey: apiKey, PackagePath: record.PackagePath,
		EventsPath: eventsPath, Scheduled: scheduled,
	}); err != nil {
		return err
	}
	return outbox.MarkDelivered(stateDirectory, runID)
}

func newUUID() (string, error) {
	data := make([]byte, 16)
	if _, err := rand.Read(data); err != nil {
		return "", err
	}
	data[6] = data[6]&0x0f | 0x40
	data[8] = data[8]&0x3f | 0x80
	encoded := hex.EncodeToString(data)
	return fmt.Sprintf("%s-%s-%s-%s-%s", encoded[0:8], encoded[8:12], encoded[12:16], encoded[16:20], encoded[20:32]), nil
}
