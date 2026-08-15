#Requires -Version 5.1
[CmdletBinding()]
param(
    [ValidateSet("Install", "Diagnose", "Validate")]
    [string]$Mode = "Install",
    [string]$PlatformUrl,
    [string]$DataDirectory,
    [ValidateSet("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")]
    [string]$ScheduleDay = "Sunday",
    [SecureString]$ApiKey,
    [PSCredential]$TaskCredential,
    [string]$ReleaseRepository = "nicksspirit/worship-prep-platform"
)

$ErrorActionPreference = "Stop"
$TaskName = "Worship Prep Catalog Import"
$LocalDirectory = Join-Path $env:USERPROFILE ".local"
$BinaryDirectory = Join-Path $LocalDirectory "bin"
$StateDirectory = Join-Path $LocalDirectory "state\WorshipPrep\CatalogExporter"
$ConfigurationDirectory = Join-Path $env:USERPROFILE ".config\WorshipPrep\CatalogExporter"
$ExecutablePath = Join-Path $BinaryDirectory "catalog-exporter.exe"
$CredentialPath = Join-Path $ConfigurationDirectory "api-key.dpapi"
$ConfigurationPath = Join-Path $ConfigurationDirectory "config.json"

function Assert-PacificTimeZone {
    $timeZone = Get-TimeZone
    if ($timeZone.Id -ne "Pacific Standard Time") {
        throw "Windows time zone must be 'Pacific Standard Time' so the weekly 3:00 AM task follows America/Los_Angeles daylight-saving time. Current: $($timeZone.Id)."
    }
}

function Get-CompatibleRelease {
    $releases = Invoke-RestMethod -Uri "https://api.github.com/repos/$ReleaseRepository/releases?per_page=50"
    $release = $releases | Where-Object {
        -not $_.draft -and
        -not $_.prerelease -and
        $_.tag_name -match '^exporter/v[0-9]+\.[0-9]+\.[0-9]+$'
    } | Select-Object -First 1
    if (-not $release) {
        throw "No compatible exporter/v* release is available."
    }
    return $release
}

function Install-VerifiedExporter {
    $release = Get-CompatibleRelease
    $binaryAsset = $release.assets | Where-Object { $_.name -eq "catalog-exporter.exe" } | Select-Object -First 1
    $checksumAsset = $release.assets | Where-Object { $_.name -eq "checksums.txt" } | Select-Object -First 1
    if (-not $binaryAsset -or -not $checksumAsset) {
        throw "Release $($release.tag_name) is missing the Windows binary or checksums."
    }

    $downloadDirectory = Join-Path ([System.IO.Path]::GetTempPath()) ("wpp-exporter-" + [guid]::NewGuid())
    New-Item -ItemType Directory -Path $downloadDirectory | Out-Null
    try {
        $downloadedBinary = Join-Path $downloadDirectory "catalog-exporter.exe"
        $downloadedChecksums = Join-Path $downloadDirectory "checksums.txt"
        Invoke-WebRequest -Uri $binaryAsset.browser_download_url -OutFile $downloadedBinary
        Invoke-WebRequest -Uri $checksumAsset.browser_download_url -OutFile $downloadedChecksums
        $checksumLine = Get-Content $downloadedChecksums | Where-Object { $_ -match '^[0-9a-fA-F]{64}\s+\*?catalog-exporter\.exe$' } | Select-Object -First 1
        if (-not $checksumLine) {
            throw "checksums.txt does not contain catalog-exporter.exe."
        }
        $expectedChecksum = ($checksumLine -split '\s+')[0].ToLowerInvariant()
        $actualChecksum = (Get-FileHash $downloadedBinary -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actualChecksum -ne $expectedChecksum) {
            throw "Catalog Exporter checksum verification failed."
        }
        Copy-Item $downloadedBinary $ExecutablePath -Force
    }
    finally {
        Remove-Item $downloadDirectory -Recurse -Force -ErrorAction SilentlyContinue
    }
}

function Save-UserScopedCredential {
    param([SecureString]$Secret)
    if (-not $Secret) {
        $Secret = Read-Host "Paste the one-time Catalog Import API key" -AsSecureString
    }
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Secret)
    try {
        $plaintext = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
        $bytes = [Text.Encoding]::UTF8.GetBytes($plaintext)
        $protected = [Security.Cryptography.ProtectedData]::Protect(
            $bytes,
            $null,
            [Security.Cryptography.DataProtectionScope]::CurrentUser
        )
        [IO.File]::WriteAllBytes($CredentialPath, $protected)
        [Array]::Clear($bytes, 0, $bytes.Length)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
}

function Set-UserEnvironmentDefaults {
    param([pscustomobject]$Configuration)
    $defaults = @{
        "WPP_CATALOG_EXPORTER_STATE_DIR" = $StateDirectory
        "WPP_CATALOG_EXPORTER_INSTANCE_ID" = $Configuration.exporter_instance_id
        "WPP_CATALOG_EXPORTER_ENDPOINT" = $Configuration.platform_url
        "WPP_CATALOG_EXPORTER_API_KEY_FILE" = $CredentialPath
    }
    foreach ($name in $defaults.Keys) {
        [Environment]::SetEnvironmentVariable($name, $defaults[$name], "User")
        [Environment]::SetEnvironmentVariable($name, $defaults[$name], "Process")
    }
}

function Register-WeeklyTask {
    param(
        [pscustomobject]$Configuration,
        [PSCredential]$Credential
    )
    $arguments = @(
        '--state-dir', ('"' + $StateDirectory + '"'),
        '--instance-id', $Configuration.exporter_instance_id,
        '--endpoint', ('"' + $Configuration.platform_url + '"'),
        '--api-key-file', ('"' + $CredentialPath + '"'),
        '--scheduled'
    ) -join ' '
    $action = New-ScheduledTaskAction -Execute $ExecutablePath -Argument $arguments
    $trigger = New-ScheduledTaskTrigger -Weekly -WeeksInterval 1 -DaysOfWeek $Configuration.schedule_day -At "03:00"
    $settings = New-ScheduledTaskSettingsSet `
        -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
        -RestartCount 1 `
        -RestartInterval (New-TimeSpan -Minutes 30) `
        -StartWhenAvailable
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    if (-not $Credential) {
        $Credential = Get-Credential -UserName $currentUser -Message "Enter the current Windows account password so the Catalog Exporter can run while signed out."
    }
    if ($Credential.UserName -ne $currentUser -and $Credential.UserName -ne $env:USERNAME) {
        throw "The scheduled task must run as the current Windows user ($currentUser) because the API key uses current-user DPAPI."
    }
    $password = $Credential.GetNetworkCredential().Password
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -User $currentUser `
        -Password $password `
        -RunLevel Limited `
        -Force | Out-Null
    $password = $null
}

function Test-Installation {
    Assert-PacificTimeZone
    foreach ($path in @($ExecutablePath, $CredentialPath, $ConfigurationPath)) {
        if (-not (Test-Path $path -PathType Leaf)) {
            throw "Required installation file is missing: $path"
        }
    }
    $configuration = Get-Content $ConfigurationPath -Raw | ConvertFrom-Json
    if (-not (Test-Path $configuration.data_directory -PathType Container)) {
        throw "EasyWorship Data directory is unavailable: $($configuration.data_directory)"
    }
    foreach ($database in @("Songs.db", "SongWords.db")) {
        if (-not (Test-Path (Join-Path $configuration.data_directory $database) -PathType Leaf)) {
            throw "Required EasyWorship database is missing: $database"
        }
    }
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
    if ($task.Settings.RestartCount -ne 1 -or $task.Settings.RestartInterval -ne "PT30M") {
        throw "Scheduled task retry policy is not one retry after 30 minutes."
    }
    Write-Host "Catalog Exporter diagnostics passed."
}

if ($Mode -eq "Validate") {
    foreach ($command in @(
        "Get-TimeZone",
        "New-ScheduledTaskAction",
        "New-ScheduledTaskTrigger",
        "New-ScheduledTaskSettingsSet",
        "Register-ScheduledTask"
    )) {
        Get-Command $command -ErrorAction Stop | Out-Null
    }
    Write-Host "Catalog Exporter installer validation passed."
    exit 0
}

if ($Mode -eq "Diagnose") {
    Test-Installation
    exit 0
}

if (-not $PlatformUrl) {
    throw "-PlatformUrl is required for installation."
}
if (-not ([uri]$PlatformUrl).Scheme.Equals("https", [StringComparison]::OrdinalIgnoreCase)) {
    throw "PlatformUrl must use HTTPS."
}
Assert-PacificTimeZone
if (-not $DataDirectory) {
    $DataDirectory = $env:WPP_EASYWORSHIP_DATA_DIR
}
if (-not $DataDirectory) {
    $DataDirectory = [Environment]::GetEnvironmentVariable("WPP_EASYWORSHIP_DATA_DIR", "User")
}
if (-not $DataDirectory) {
    throw "WPP_EASYWORSHIP_DATA_DIR must identify the EasyWorship Data directory."
}
if (-not (Test-Path $DataDirectory -PathType Container)) {
    throw "EasyWorship Data directory does not exist: $DataDirectory"
}
New-Item -ItemType Directory -Path $BinaryDirectory -Force | Out-Null
New-Item -ItemType Directory -Path $StateDirectory -Force | Out-Null
New-Item -ItemType Directory -Path $ConfigurationDirectory -Force | Out-Null

$existingConfiguration = $null
if (Test-Path $ConfigurationPath) {
    $existingConfiguration = Get-Content $ConfigurationPath -Raw | ConvertFrom-Json
}
$instanceId = if ($existingConfiguration.exporter_instance_id) {
    $existingConfiguration.exporter_instance_id
} else {
    [guid]::NewGuid().ToString()
}
$configuration = [pscustomobject]@{
    platform_url = $PlatformUrl.TrimEnd('/')
    data_directory = (Resolve-Path $DataDirectory).Path
    exporter_instance_id = $instanceId
    schedule_day = $ScheduleDay
}
$configuration | ConvertTo-Json | Set-Content $ConfigurationPath -Encoding UTF8
Install-VerifiedExporter
Save-UserScopedCredential -Secret $ApiKey
Set-UserEnvironmentDefaults -Configuration $configuration
Register-WeeklyTask -Configuration $configuration -Credential $TaskCredential
Test-Installation
Write-Host "Catalog Exporter installed. The weekly import runs $ScheduleDay at 3:00 AM America/Los_Angeles."
