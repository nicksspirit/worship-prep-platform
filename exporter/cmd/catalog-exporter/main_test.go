package main

import (
	"context"
	"testing"
	"time"

	"github.com/nicksspirit/worship-prep-platform/exporter/internal/outbox"
)

func TestReplayPendingDoesNotBlockOnSourceFailureWithoutPackage(t *testing.T) {
	directory := t.TempDir()
	if err := outbox.Append(directory, outbox.Event{
		RunID:      "11111111-1111-4111-8111-111111111111",
		Type:       "skipped_source_in_use",
		OccurredAt: time.Now(),
	}); err != nil {
		t.Fatal(err)
	}

	replayed, err := replayPending(
		context.Background(), directory, "https://example.com", "unused", true,
	)
	if err != nil {
		t.Fatal(err)
	}
	if replayed {
		t.Fatal("replayPending() replayed a run without a package")
	}
}

func TestEnvironmentDefaultUsesFirstNonEmptyConfiguredValue(t *testing.T) {
	t.Setenv("WPP_CATALOG_EXPORTER_DATA_DIR", "C:\\Worship\\Data")
	t.Setenv("EASYWORSHIP_DATA_DIR", "C:\\EasyWorship\\Data")

	actual := environmentDefault(
		"", "WPP_CATALOG_EXPORTER_DATA_DIR", "EASYWORSHIP_DATA_DIR",
	)

	if actual != "C:\\Worship\\Data" {
		t.Fatalf("environmentDefault() = %q, want configured WPP path", actual)
	}
}

func TestEnvironmentDefaultFallsBackWhenNoConfiguredValueExists(t *testing.T) {
	t.Setenv("WPP_CATALOG_EXPORTER_STATE_DIR", "")

	actual := environmentDefault(".catalog-exporter", "WPP_CATALOG_EXPORTER_STATE_DIR")

	if actual != ".catalog-exporter" {
		t.Fatalf("environmentDefault() = %q, want fallback", actual)
	}
}
