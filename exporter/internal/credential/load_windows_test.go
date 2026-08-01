//go:build windows

package credential

import (
	"os/exec"
	"path/filepath"
	"testing"
)

func TestLoadDecryptsCurrentUserDPAPICredential(t *testing.T) {
	path := filepath.Join(t.TempDir(), "api-key.dpapi")
	script := `[IO.File]::WriteAllBytes($args[0], [Security.Cryptography.ProtectedData]::Protect([Text.Encoding]::UTF8.GetBytes('wpp_live_test.secret'), $null, [Security.Cryptography.DataProtectionScope]::CurrentUser))`
	if output, err := exec.Command("powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script, path).CombinedOutput(); err != nil {
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
