# Install the Catalog Exporter on Windows

Complete these steps on the Windows computer that contains the EasyWorship Library.

The platform website is [https://app.rccgcm.org](https://app.rccgcm.org).

## 1. Obtain the API key

Create a key in **Admin → API Keys → Add API key** after the admin fix is deployed.

- Set the name to `EasyWorship Windows Exporter`.
- Select only **Catalog: Import**.
- Leave the expiration date blank for the continuous weekly task.
- Copy the full key when the page shows it. The page shows it only once.

Keep the key private. Paste it only into the installer's API key prompt.

## 2. Prepare the Windows account and source folder

Sign in with the Windows account that will run the exporter.
The installer protects the key for this account with Windows encryption (DPAPI).
The scheduled task must use the same account.

Find the EasyWorship Data folder. It must contain `Songs.db` and `SongWords.db`.
Copy the folder path from File Explorer.

Close EasyWorship before the first import. The exporter skips source reading while EasyWorship runs.

Set the Windows time zone to **Pacific Time (US & Canada)** in Windows Settings.
The installer requires the time zone ID `Pacific Standard Time`.

## 3. Set the source folder

Open built-in **Windows PowerShell 5.1 or later** under the same Windows account.
Run these commands and paste the actual Data folder path when prompted:

```powershell
$dataDir = Read-Host 'Paste the EasyWorship Data folder path'
Test-Path (Join-Path $dataDir 'Songs.db')
Test-Path (Join-Path $dataDir 'SongWords.db')
Get-TimeZone
```

Continue only if both file checks return `True` and the time zone ID is `Pacific Standard Time`.

Run these commands to save the folder for this account and the current PowerShell session:

```powershell
[Environment]::SetEnvironmentVariable('WPP_EASYWORSHIP_DATA_DIR', $dataDir, 'User')
$env:WPP_EASYWORSHIP_DATA_DIR = $dataDir
```

## 4. Install the exporter

Run this in PowerShell. It downloads and runs the platform's bootstrap, which then
downloads the checksum-verified exporter installer:

```powershell
irm https://app.rccgcm.org/install | iex
```

Paste the full API key into **Paste the one-time Catalog Import API key**.
The installer does not ask for a Windows account password or Windows Hello PIN.

The installer verifies the executable's SHA-256 checksum and encrypts the API key for this Windows account.
It creates **Worship Prep Catalog Import** for Sunday at **3:00 AM Pacific**.
It retries a failed command once after 30 minutes.
The task uses passwordless **Interactive** logon for the same account that protects the API key.
Keep that account signed in and the computer awake for scheduled imports.
You can lock the screen. Signing out prevents the task from running.

Wait for `Catalog Exporter diagnostics passed.` and the installation confirmation.

The bootstrap downloads the installer from the app domain and configures uploads
to `https://api.rccgcm.org`. The app domain no longer forwards `/api/` requests.
Check the import route before the first import:

```powershell
Invoke-WebRequest -UseBasicParsing -Method Options `
  -Uri 'https://api.rccgcm.org/api/v1/catalog/imports' |
  Select-Object StatusCode
```

Expect HTTP `204`. HTTP `502` means the API backend is not ready; resolve that
before uploading.

If an older installer reports `Unable to find type [Security.Cryptography.ProtectedData]`, run these commands in the same PowerShell window:

```powershell
Add-Type -AssemblyName System.Security
irm https://app.rccgcm.org/install | iex
```

Paste the same API key again when prompted. This command loads the Windows encryption type without changing the API key.

### Reinstall an existing exporter

After deploying the new app and verifying the API route, reinstall under the
same Windows account:

```powershell
irm https://app.rccgcm.org/install | iex
```

Reinstallation preserves the exporter instance ID, outbox/state directory, and
existing encrypted API key unless a replacement key is explicitly supplied. It
updates the saved endpoint and per-user environment and replaces the scheduled
task. Until reinstallation, the old app-domain endpoint returns 404 and scheduled
imports fail; perform the switch together during the rollout.

Check the saved endpoint and scheduled task after reinstalling:

```powershell
[Environment]::GetEnvironmentVariable('WPP_CATALOG_EXPORTER_ENDPOINT', 'User')
(Get-ScheduledTask -TaskName 'Worship Prep Catalog Import').Actions.Arguments
```

Both must reference `https://api.rccgcm.org`. Open a new PowerShell session for
subsequent manual runs so it loads the updated per-user environment.

## 5. Run and verify the first import

Keep EasyWorship closed. Open a new PowerShell session under the same account.
Run the exporter directly to see its output:

```powershell
& "$env:USERPROFILE\.local\bin\catalog-exporter.exe"
$LASTEXITCODE
```

Expect exit code `0`. A message that says EasyWorship is running means the source import was skipped.
If the source import was skipped, close EasyWorship and run the exporter again.

Open **Admin → Song Catalog → Import runs** at [Worship Prep Admin](https://app.rccgcm.org/admin/catalog/catalogimportrun/).
Confirm that the new run has status **Completed**. Check the song count and warnings.

Check the scheduled task:

```powershell
Get-ScheduledTask -TaskName 'Worship Prep Catalog Import' |
  Select-Object TaskName, State,
    @{Name='LogonType'; Expression={$_.Principal.LogonType}}
```

Expect **Ready** and **Interactive** after installation.

To start a scheduled run immediately:

```powershell
Start-ScheduledTask -TaskName 'Worship Prep Catalog Import'
```

## Installation paths

| Item | Path |
| --- | --- |
| Executable | `%USERPROFILE%\.local\bin\catalog-exporter.exe` |
| Encrypted API key | `%USERPROFILE%\.config\WorshipPrep\CatalogExporter\api-key.dpapi` |
| Configuration | `%USERPROFILE%\.config\WorshipPrep\CatalogExporter\config.json` |
| Packages and pending deliveries | `%USERPROFILE%\.local\state\WorshipPrep\CatalogExporter` |

The exporter reads private temporary copies of the EasyWorship databases. It does not change the source databases.

The latest published release checked on October 10, 2026, is [exporter/v0.1.1](https://github.com/nicksspirit/worship-prep-platform/releases/tag/exporter/v0.1.1).
The Windows installation and end-to-end import have not been tested on the actual computer.
