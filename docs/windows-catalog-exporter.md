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

Download the installer from the platform website.
Set the installer's `-PlatformUrl` argument to the API service address that accepts catalog imports:

```powershell
$installer = Join-Path $env:TEMP 'install-catalog-exporter.ps1'
Invoke-WebRequest -UseBasicParsing `
  -Uri 'https://app.rccgcm.org/static/install-catalog-exporter.ps1' `
  -OutFile $installer
& $installer -PlatformUrl 'https://wpp-api-zxdtzfpwua-uw.a.run.app'
```

Paste the full API key into **Paste the one-time Catalog Import API key**.
Enter this Windows account's password at the scheduled-task prompt. Use the password, not the Windows Hello PIN.

The installer verifies the executable's SHA-256 checksum and encrypts the API key for this Windows account.
It creates **Worship Prep Catalog Import** for Sunday at **3:00 AM Pacific**.
It retries a failed command once after 30 minutes.

Wait for `Catalog Exporter diagnostics passed.` and the installation confirmation.

The current `/install` bootstrap supplies the application address as the API address.
Use the explicit command above for this deployment.
The platform website's `/api/v1/catalog/imports` route returned HTTP 404 when checked on October 10, 2026.
The API service's same route accepted `OPTIONS` and advertised `POST` support.

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
Get-ScheduledTask -TaskName 'Worship Prep Catalog Import'
```

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
