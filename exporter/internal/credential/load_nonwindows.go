//go:build !windows

// Package credential loads the Integration Client key protected for one Windows user.
package credential

import "fmt"

// Load reports that Windows DPAPI credentials are unavailable on this platform.
func Load(path string) (string, error) {
	return "", fmt.Errorf("DPAPI credentials can only be loaded on Windows")
}
