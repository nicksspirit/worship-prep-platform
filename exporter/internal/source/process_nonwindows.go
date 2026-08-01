//go:build !windows

package source

// PlatformProcessDetector is a no-op outside Windows, where EasyWorship runs.
type PlatformProcessDetector struct{}

// EasyWorshipRunning always returns false on non-Windows development hosts.
func (PlatformProcessDetector) EasyWorshipRunning() (bool, error) {
	return false, nil
}
