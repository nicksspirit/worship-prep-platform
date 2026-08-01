package main

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"time"

	"github.com/nicksspirit/worship-prep-platform/exporter/internal/exporter"
	"github.com/nicksspirit/worship-prep-platform/exporter/internal/source"
)

var version = "dev"

func main() {
	os.Exit(run())
}

func run() int {
	var dataDirectory, outputPath, stateDirectory, runID, instanceID string
	flag.StringVar(&dataDirectory, "data-dir", "", "EasyWorship Data directory")
	flag.StringVar(&outputPath, "output", "", "Catalog Import Package output path")
	flag.StringVar(&stateDirectory, "state-dir", ".catalog-exporter", "durable local state directory")
	flag.StringVar(&runID, "run-id", "", "Catalog Import Run UUID (generated when omitted)")
	flag.StringVar(&instanceID, "instance-id", "", "stable Catalog Exporter instance UUID")
	flag.Parse()

	if runID == "" {
		var err error
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
