// Package delivery sends durable Catalog Import work to Worship Prep Platform.
package delivery

import (
	"context"
	"fmt"
	"io"
	"mime/multipart"
	"net/http"
	"net/textproto"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"time"
)

// Config describes one idempotent Catalog Import delivery attempt.
type Config struct {
	Endpoint    string
	APIKey      string
	PackagePath string
	EventsPath  string
	Scheduled   bool
	Client      *http.Client
}

// Send uploads a package and its retained exporter timeline in one request.
func Send(ctx context.Context, config Config) error {
	endpoint, err := importURL(config.Endpoint)
	if err != nil {
		return err
	}
	if strings.TrimSpace(config.APIKey) == "" {
		return fmt.Errorf("Integration Client API key is required")
	}

	body, bodyWriter := io.Pipe()
	writer := multipart.NewWriter(bodyWriter)
	contentType := writer.FormDataContentType()
	go func() {
		if err := addFile(writer, "package", config.PackagePath, "application/zip"); err != nil {
			bodyWriter.CloseWithError(err)
			return
		}
		if config.EventsPath != "" {
			if err := addFile(writer, "events", config.EventsPath, "application/x-ndjson"); err != nil {
				bodyWriter.CloseWithError(err)
				return
			}
		}
		if err := writer.Close(); err != nil {
			bodyWriter.CloseWithError(fmt.Errorf("finish delivery body: %w", err))
			return
		}
		bodyWriter.Close()
	}()

	request, err := http.NewRequestWithContext(ctx, http.MethodPost, endpoint, body)
	if err != nil {
		body.Close()
		return fmt.Errorf("create delivery request: %w", err)
	}
	request.Header.Set("Authorization", "Bearer "+config.APIKey)
	request.Header.Set("Content-Type", contentType)
	trigger := "manual"
	if config.Scheduled {
		trigger = "scheduled"
	}
	request.Header.Set("X-Catalog-Import-Trigger", trigger)

	client := config.Client
	if client == nil {
		client = &http.Client{Timeout: 10 * time.Minute}
	}
	response, err := client.Do(request)
	if err != nil {
		return fmt.Errorf("deliver Catalog Import: %w", err)
	}
	defer response.Body.Close()
	if response.StatusCode < 200 || response.StatusCode >= 300 {
		message, _ := io.ReadAll(io.LimitReader(response.Body, 16*1024))
		return fmt.Errorf(
			"Catalog Import delivery returned %s: %s",
			response.Status,
			strings.TrimSpace(string(message)),
		)
	}
	return nil
}

func importURL(rawEndpoint string) (string, error) {
	parsed, err := url.Parse(strings.TrimSpace(rawEndpoint))
	if err != nil || parsed.Host == "" {
		return "", fmt.Errorf("valid platform endpoint is required")
	}
	if parsed.Scheme != "https" && parsed.Hostname() != "localhost" && parsed.Hostname() != "127.0.0.1" {
		return "", fmt.Errorf("platform endpoint must use HTTPS")
	}
	path := strings.TrimRight(parsed.Path, "/")
	if !strings.HasSuffix(path, "/api/v1/catalog/imports") {
		path += "/api/v1/catalog/imports"
	}
	parsed.Path = path
	return parsed.String(), nil
}

func addFile(writer *multipart.Writer, field, path, contentType string) error {
	file, err := os.Open(path)
	if err != nil {
		return fmt.Errorf("open %s: %w", field, err)
	}
	defer file.Close()
	header := make(textproto.MIMEHeader)
	header.Set("Content-Disposition", fmt.Sprintf(`form-data; name="%s"; filename="%s"`, field, filepath.Base(path)))
	header.Set("Content-Type", contentType)
	part, err := writer.CreatePart(header)
	if err != nil {
		return fmt.Errorf("create %s form part: %w", field, err)
	}
	if _, err := io.Copy(part, file); err != nil {
		return fmt.Errorf("copy %s form part: %w", field, err)
	}
	return nil
}
