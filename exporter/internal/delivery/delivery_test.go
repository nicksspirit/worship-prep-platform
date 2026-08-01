package delivery

import (
	"context"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
)

func TestSendUploadsPackageEventsAndScheduledIdentity(t *testing.T) {
	directory := t.TempDir()
	packagePath := filepath.Join(directory, "run.zip")
	eventsPath := filepath.Join(directory, "run.ndjson")
	if err := os.WriteFile(packagePath, []byte("package"), 0o600); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(eventsPath, []byte("event\n"), 0o600); err != nil {
		t.Fatal(err)
	}

	server := httptest.NewServer(http.HandlerFunc(func(response http.ResponseWriter, request *http.Request) {
		if request.URL.Path != "/api/v1/catalog/imports" {
			t.Errorf("path = %q", request.URL.Path)
		}
		if got := request.Header.Get("Authorization"); got != "Bearer secret" {
			t.Errorf("authorization = %q", got)
		}
		if got := request.Header.Get("X-Catalog-Import-Trigger"); got != "scheduled" {
			t.Errorf("trigger = %q", got)
		}
		if err := request.ParseMultipartForm(1024); err != nil {
			t.Fatal(err)
		}
		for field, want := range map[string]string{"package": "package", "events": "event\n"} {
			file, _, err := request.FormFile(field)
			if err != nil {
				t.Fatal(err)
			}
			got, _ := io.ReadAll(file)
			file.Close()
			if string(got) != want {
				t.Errorf("%s = %q, want %q", field, got, want)
			}
		}
		response.WriteHeader(http.StatusCreated)
	}))
	defer server.Close()

	err := Send(context.Background(), Config{
		Endpoint: server.URL, APIKey: "secret", PackagePath: packagePath,
		EventsPath: eventsPath, Scheduled: true, Client: server.Client(),
	})
	if err != nil {
		t.Fatal(err)
	}
}

func TestSendRetainsServerFailureDetails(t *testing.T) {
	directory := t.TempDir()
	packagePath := filepath.Join(directory, "run.zip")
	if err := os.WriteFile(packagePath, []byte("package"), 0o600); err != nil {
		t.Fatal(err)
	}
	server := httptest.NewServer(http.HandlerFunc(func(response http.ResponseWriter, request *http.Request) {
		http.Error(response, `{"error":{"code":"invalid_package"}}`, http.StatusUnprocessableEntity)
	}))
	defer server.Close()

	err := Send(context.Background(), Config{
		Endpoint: server.URL, APIKey: "secret", PackagePath: packagePath, Client: server.Client(),
	})
	if err == nil {
		t.Fatal("Send() error = nil")
	}
}

func TestSendRejectsNonHTTPSRemoteEndpoint(t *testing.T) {
	err := Send(context.Background(), Config{
		Endpoint: "http://example.com", APIKey: "secret", PackagePath: "unused",
	})
	if err == nil {
		t.Fatal("Send() error = nil")
	}
}
