package source

import (
	"errors"
	"os"
	"path/filepath"
	"testing"
)

type fixedDetector struct {
	running bool
	err     error
}

func (d fixedDetector) EasyWorshipRunning() (bool, error) {
	return d.running, d.err
}

func TestAcquireRefusesSourceWhileEasyWorshipRuns(t *testing.T) {
	t.Parallel()
	_, err := Acquire(t.TempDir(), fixedDetector{running: true})
	if !errors.Is(err, ErrSourceInUse) {
		t.Fatalf("Acquire() error = %v, want ErrSourceInUse", err)
	}
}

func TestAcquireRequiresCanonicalDatabases(t *testing.T) {
	t.Parallel()
	directory := t.TempDir()
	if err := os.WriteFile(filepath.Join(directory, "Songs.db"), []byte("songs"), 0o600); err != nil {
		t.Fatal(err)
	}
	_, err := Acquire(directory, fixedDetector{})
	if err == nil || err.Error() != "required EasyWorship database is missing: SongWords.db" {
		t.Fatalf("Acquire() error = %v", err)
	}
}

func TestAcquireUsesPrivateCopiesAndAllowsMissingDiagnosticDatabase(t *testing.T) {
	t.Parallel()
	directory := t.TempDir()
	for name, content := range map[string]string{
		"Songs.db": "original songs", "SongWords.db": "original words",
	} {
		if err := os.WriteFile(filepath.Join(directory, name), []byte(content), 0o600); err != nil {
			t.Fatal(err)
		}
	}
	acquisition, err := Acquire(directory, fixedDetector{})
	if err != nil {
		t.Fatalf("Acquire() error = %v", err)
	}
	t.Cleanup(func() { _ = acquisition.Cleanup() })
	if acquisition.Directory == directory {
		t.Fatal("Acquire() returned live source directory")
	}
	if err := os.WriteFile(filepath.Join(directory, "Songs.db"), []byte("changed live file"), 0o600); err != nil {
		t.Fatal(err)
	}
	copied, err := os.ReadFile(filepath.Join(acquisition.Directory, "Songs.db"))
	if err != nil {
		t.Fatal(err)
	}
	if got, want := string(copied), "original songs"; got != want {
		t.Fatalf("copied Songs.db = %q, want %q", got, want)
	}
	if got := acquisition.Files[2]; got.Name != "SongKeys.db" || got.Present || got.Required {
		t.Fatalf("optional source metadata = %#v", got)
	}
	if err := acquisition.Cleanup(); err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat(acquisition.Directory); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("temporary directory still exists: %v", err)
	}
}
