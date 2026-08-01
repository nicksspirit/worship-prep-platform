package outbox

import (
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestPendingAndMarkDeliveredPreserveAcknowledgedHistory(t *testing.T) {
	directory := t.TempDir()
	runID := "11111111-1111-4111-8111-111111111111"
	if err := Append(directory, Event{RunID: runID, Type: "started", OccurredAt: time.Now()}); err != nil {
		t.Fatal(err)
	}
	pending, err := Pending(directory)
	if err != nil {
		t.Fatal(err)
	}
	if len(pending) != 1 || pending[0].RunID != runID {
		t.Fatalf("Pending() = %#v", pending)
	}
	if err := MarkDelivered(directory, runID); err != nil {
		t.Fatal(err)
	}
	pending, err = Pending(directory)
	if err != nil {
		t.Fatal(err)
	}
	if len(pending) != 0 {
		t.Fatalf("Pending() after delivery = %#v", pending)
	}
	if _, err := os.Stat(filepath.Join(directory, "delivered", runID+".ndjson")); err != nil {
		t.Fatal(err)
	}
}
