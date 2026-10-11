// This integration helper exercises production delivery against a local trusted proxy.
package main

import (
	"context"
	"crypto/tls"
	"crypto/x509"
	"fmt"
	"net/http"
	"os"
	"time"

	"github.com/nicksspirit/worship-prep-platform/exporter/internal/delivery"
)

func main() {
	if len(os.Args) != 6 {
		panic("usage: deliver-fixture endpoint certificate package events api-key")
	}
	certificate, err := os.ReadFile(os.Args[2])
	if err != nil {
		panic(err)
	}
	pool := x509.NewCertPool()
	if !pool.AppendCertsFromPEM(certificate) {
		panic("invalid test certificate")
	}
	transport := http.DefaultTransport.(*http.Transport).Clone()
	transport.TLSClientConfig = &tls.Config{RootCAs: pool, MinVersion: tls.VersionTLS12}
	client := &http.Client{Transport: transport, Timeout: 10 * time.Minute}
	err = delivery.Send(context.Background(), delivery.Config{
		Endpoint: os.Args[1], PackagePath: os.Args[3], EventsPath: os.Args[4],
		APIKey: os.Args[5], Scheduled: true, Client: client,
	})
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
