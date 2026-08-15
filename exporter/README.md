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

On the EasyWorship Windows machine, set `WPP_EASYWORSHIP_DATA_DIR` once for the Windows
user that runs EasyWorship, then open a new built-in Windows PowerShell 5.1 or later
session and use the platform's one-line bootstrap. The installer obtains the latest
`exporter/v*` release, verifies its checksum, protects the one-time API key with DPAPI,
and creates a weekly 3:00 AM Pacific task with one retry after 30 minutes:

```powershell
[Environment]::SetEnvironmentVariable(
  'WPP_EASYWORSHIP_DATA_DIR',
  'C:\\Users\\operator\\Documents\\Softouch\\EasyWorship\\Default\\Databases\\Data',
  'User'
)
```

```powershell
irm https://wpp-api.example.com/install | iex
```

The weekday defaults to Sunday. Windows must use the `Pacific Standard Time` zone so
daylight-saving transitions remain aligned with America/Los_Angeles. Re-run the command
after machine or account changes to reinstall; `-Mode Diagnose` remains available from
the downloaded installer. The platform URL is the Django Bolt API service base URL, not
the rendered web-app URL.

The installer places `catalog-exporter.exe` in `%USERPROFILE%\.local\bin`, durable
packages and outbox state in `%USERPROFILE%\.local\state\WorshipPrep\CatalogExporter`,
and configuration plus the current-user DPAPI-protected API key in
`%USERPROFILE%\.config\WorshipPrep\CatalogExporter`. It writes these non-secret
per-user defaults so the executable can be run directly without repeating flags:

- `WPP_EASYWORSHIP_DATA_DIR`
- `WPP_CATALOG_EXPORTER_STATE_DIR`
- `WPP_CATALOG_EXPORTER_INSTANCE_ID`
- `WPP_CATALOG_EXPORTER_ENDPOINT`
- `WPP_CATALOG_EXPORTER_API_KEY_FILE`

`WPP_EASYWORSHIP_DATA_DIR` takes precedence over `EASYWORSHIP_DATA_DIR`; an explicit
command-line flag takes precedence over either environment variable. The API key itself
is never placed in an environment variable.
An authorized operator can start an immediate run without changing the weekly schedule:

```powershell
Start-ScheduledTask -TaskName 'Worship Prep Catalog Import'
```

See [`../contracts/catalog-import/v1/README.md`](../contracts/catalog-import/v1/README.md)
for the package contract.
