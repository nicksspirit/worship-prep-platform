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
