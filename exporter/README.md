# Catalog Exporter

The Catalog Exporter is a portable, no-CGO Go command that reads an EasyWorship
Library without changing it, produces a versioned Catalog Import Package, and delivers
durable work to Worship Prep Platform over HTTPS.

## Safety contract

1. Generate a Catalog Import Run ID before any source work.
2. On Windows, exit with `skipped_source_in_use` while `EasyWorship.exe` runs.
3. Require `Songs.db` and `SongWords.db`; treat `SongKeys.db` as optional diagnostics.
4. Copy source databases into a unique private temporary directory.
5. Open only those immutable copies and force table scans for source content.
6. Remove the temporary copies after success or failure.
7. Durably append local run events under `<state-dir>/outbox` and replay the same run
   after connectivity or server failures.

The exporter never receives PostgreSQL credentials. Its import-scoped API key is
protected with current-user Windows DPAPI; scheduled work must run under that same
Windows account.

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
`<state-dir>/packages/<run-id>.zip`. Add `--endpoint`, `--api-key-file`, and optionally
`--scheduled` to deliver it. The command reports aggregate counts and a transport
SHA-256; it does not print song content.

## Windows installation and schedule

Download the stable installer from
`/static/install-catalog-exporter.ps1` on the deployed platform and run it with
PowerShell 7. It downloads the latest `exporter/v*` release, verifies its checksum,
protects the one-time API key with DPAPI, and creates a weekly 3:00 AM Pacific task with
one retry after 30 minutes:

```powershell
./install-catalog-exporter.ps1 `
  -PlatformUrl 'https://wpp-api.example.com' `
  -DataDirectory 'C:\Users\operator\Documents\Softouch\EasyWorship\Default\Databases\Data'
```

The weekday defaults to Sunday and can be changed with `-ScheduleDay`. Windows must use
the `Pacific Standard Time` zone so daylight-saving transitions remain aligned with
America/Los_Angeles. Re-run with `-Mode Diagnose` after machine or account changes.
`PlatformUrl` is the Django Bolt API service base URL, not the rendered web-app URL.
An authorized operator can start an immediate run without changing the weekly schedule:

```powershell
Start-ScheduledTask -TaskName 'Worship Prep Catalog Import'
```

See [`../contracts/catalog-import/v1/README.md`](../contracts/catalog-import/v1/README.md)
for the package contract.
