package source

import "testing"

func TestEasyWorshipInTasklist(t *testing.T) {
	t.Parallel()
	output := `"explorer.exe","1200","Console","1","32,000 K"` + "\r\n" +
		`"EASYWORSHIP.EXE","2200","Console","1","150,000 K"` + "\r\n"
	running, err := easyWorshipInTasklist(output)
	if err != nil {
		t.Fatalf("easyWorshipInTasklist() error = %v", err)
	}
	if !running {
		t.Fatal("easyWorshipInTasklist() = false, want true")
	}
}
