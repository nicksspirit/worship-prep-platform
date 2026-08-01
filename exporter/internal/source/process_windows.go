//go:build windows

package source

import (
	"fmt"
	"os/exec"
)

// PlatformProcessDetector uses the built-in tasklist command on Windows.
type PlatformProcessDetector struct{}

// EasyWorshipRunning reports whether an EasyWorship executable is active.
func (PlatformProcessDetector) EasyWorshipRunning() (bool, error) {
	output, err := exec.Command("tasklist.exe", "/FO", "CSV", "/NH").Output()
	if err != nil {
		return false, fmt.Errorf("run tasklist: %w", err)
	}
	return easyWorshipInTasklist(string(output))
}
