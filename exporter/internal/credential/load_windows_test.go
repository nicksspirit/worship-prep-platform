//go:build windows

package credential

import (
	"os"
	"os/exec"
	"path/filepath"
	"testing"
)

func TestLoadDecryptsCurrentUserDPAPICredential(t *testing.T) {
	path := filepath.Join(t.TempDir(), "api-key.dpapi")
	script := `Add-Type -AssemblyName System.Security; [IO.File]::WriteAllBytes($env:WPP_DPAPI_TEST_PATH, [Security.Cryptography.ProtectedData]::Protect([Text.Encoding]::UTF8.GetBytes('wpp_live_test.secret'), $null, [Security.Cryptography.DataProtectionScope]::CurrentUser))`
	command := exec.Command(
		"powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script,
	)
	command.Env = append(os.Environ(), "WPP_DPAPI_TEST_PATH="+path)
	if output, err := command.CombinedOutput(); err != nil {
		t.Fatalf("protect fixture: %v: %s", err, output)
	}
	got, err := Load(path)
	if err != nil {
		t.Fatal(err)
	}
	if got != "wpp_live_test.secret" {
		t.Fatalf("Load() = %q", got)
	}
}
