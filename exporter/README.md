# Catalog Exporter

The Catalog Exporter is a portable, no-CGO Go command that reads an EasyWorship
Library without changing it and produces a versioned Catalog Import Package.
Delivery to Worship Prep Platform is intentionally outside slice 2.

## Safety contract

1. Generate a Catalog Import Run ID before any source work.
2. On Windows, exit with `skipped_source_in_use` while `EasyWorship.exe` runs.
3. Require `Songs.db` and `SongWords.db`; treat `SongKeys.db` as optional diagnostics.
4. Copy source databases into a unique private temporary directory.
5. Open only those immutable copies and force table scans for source content.
6. Remove the temporary copies after success or failure.
7. Durably append local run events under `<state-dir>/outbox`.

The exporter never receives PostgreSQL credentials and does not deliver a package in
this slice. DPAPI credential storage, installer/task configuration, and HTTPS delivery
arrive with their scheduled slices.

## Build and test

```bash
cd exporter
go test ./...
CGO_ENABLED=0 GOOS=windows GOARCH=amd64 go build ./cmd/catalog-exporter
```

Go 1.26 or newer is required. The only direct runtime dependency is
`modernc.org/sqlite`, selected because it implements SQLite without CGO and supports
portable Windows cross-compilation. Dependency versions and checksums are pinned in
`go.mod` and `go.sum`.

## Manual package creation

```bash
go run ./cmd/catalog-exporter \
  --data-dir 'C:\Users\operator\Documents\Softouch\EasyWorship\Default\Databases\Data' \
  --state-dir 'C:\Users\operator\AppData\Local\WorshipPrep\CatalogExporter' \
  --instance-id '<stable-exporter-instance-uuid>'
```

`--run-id` is optional and generated when omitted. `--output` defaults to
`<state-dir>/packages/<run-id>.zip`. The command reports aggregate counts and a
transport SHA-256; it does not print song content.

See [`../contracts/catalog-import/v1/README.md`](../contracts/catalog-import/v1/README.md)
for the package contract.
