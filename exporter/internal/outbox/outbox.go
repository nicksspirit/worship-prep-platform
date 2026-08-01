// Package outbox durably records Catalog Exporter events before delivery exists.
package outbox

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"time"
)

// Event is one exporter stage in a Catalog Import Run.
type Event struct {
	RunID      string         `json:"run_id"`
	Type       string         `json:"type"`
	OccurredAt time.Time      `json:"occurred_at"`
	Details    map[string]any `json:"details,omitempty"`
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
