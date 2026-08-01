// Package outbox durably records Catalog Exporter events through delivery.
package outbox

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"
)

// Event is one exporter stage in a Catalog Import Run.
type Event struct {
	RunID      string         `json:"run_id"`
	Type       string         `json:"type"`
	OccurredAt time.Time      `json:"occurred_at"`
	Details    map[string]any `json:"details,omitempty"`
}

// PendingRun identifies one event timeline that has not been acknowledged.
type PendingRun struct {
	RunID      string
	EventsPath string
}

// Append writes and syncs an event so process failure does not erase history.
func Append(stateDirectory string, event Event) error {
	directory := filepath.Join(stateDirectory, "outbox")
	if err := os.MkdirAll(directory, 0o700); err != nil {
		return fmt.Errorf("create outbox directory: %w", err)
	}
	path := filepath.Join(directory, event.RunID+".ndjson")
	file, err := os.OpenFile(path, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o600)
	if err != nil {
		return fmt.Errorf("open outbox: %w", err)
	}
	defer file.Close()
	encoder := json.NewEncoder(file)
	encoder.SetEscapeHTML(false)
	if err := encoder.Encode(event); err != nil {
		return fmt.Errorf("write outbox event: %w", err)
	}
	if err := file.Sync(); err != nil {
		return fmt.Errorf("sync outbox event: %w", err)
	}
	return nil
}

// Pending returns retained run timelines in deterministic run-ID order.
func Pending(stateDirectory string) ([]PendingRun, error) {
	directory := filepath.Join(stateDirectory, "outbox")
	entries, err := os.ReadDir(directory)
	if os.IsNotExist(err) {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("read outbox: %w", err)
	}
	pending := make([]PendingRun, 0, len(entries))
	for _, entry := range entries {
		if entry.IsDir() || filepath.Ext(entry.Name()) != ".ndjson" {
			continue
		}
		pending = append(pending, PendingRun{
			RunID:      strings.TrimSuffix(entry.Name(), ".ndjson"),
			EventsPath: filepath.Join(directory, entry.Name()),
		})
	}
	sort.Slice(pending, func(left, right int) bool {
		return pending[left].RunID < pending[right].RunID
	})
	return pending, nil
}

// MarkDelivered archives acknowledged events so connectivity retries stop replaying them.
func MarkDelivered(stateDirectory, runID string) error {
	source := filepath.Join(stateDirectory, "outbox", runID+".ndjson")
	directory := filepath.Join(stateDirectory, "delivered")
	if err := os.MkdirAll(directory, 0o700); err != nil {
		return fmt.Errorf("create delivered event directory: %w", err)
	}
	if err := os.Rename(source, filepath.Join(directory, runID+".ndjson")); err != nil {
		return fmt.Errorf("archive delivered events: %w", err)
	}
	return nil
}
