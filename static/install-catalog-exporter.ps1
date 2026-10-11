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
    [string]$ReleaseRepository = "nicksspirit/worship-prep-platform"
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Security
$TaskName = "Worship Prep Catalog Import"

function Get-InstallationPaths {
    param([string]$UserProfile)
    $localDirectory = Join-Path $UserProfile ".local"
    $binaryDirectory = Join-Path $localDirectory "bin"
    $configurationDirectory = Join-Path $UserProfile ".config\WorshipPrep\CatalogExporter"
    return [pscustomobject]@{
        BinaryDirectory = $binaryDirectory
        StateDirectory = Join-Path $localDirectory "state\WorshipPrep\CatalogExporter"
        ConfigurationDirectory = $configurationDirectory
        ExecutablePath = Join-Path $binaryDirectory "catalog-exporter.exe"
        CredentialPath = Join-Path $configurationDirectory "api-key.dpapi"
        ConfigurationPath = Join-Path $configurationDirectory "config.json"
    }
}

function Assert-PacificTimeZone {
    param([string]$TimeZoneId)
    if ($TimeZoneId -ne "Pacific Standard Time") {
        throw "Windows time zone must be 'Pacific Standard Time' so the weekly 3:00 AM task follows America/Los_Angeles daylight-saving time. Current: $TimeZoneId."
    }
}

function Select-CompatibleRelease {
    param([object[]]$Releases)
    $release = $Releases | Where-Object {
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
    param([pscustomobject]$Release, [string]$ExecutablePath)
    $binaryAsset = $Release.assets | Where-Object { $_.name -eq "catalog-exporter.exe" } | Select-Object -First 1
    $checksumAsset = $Release.assets | Where-Object { $_.name -eq "checksums.txt" } | Select-Object -First 1
    if (-not $binaryAsset -or -not $checksumAsset) {
        throw "Release $($Release.tag_name) is missing the Windows binary or checksums."
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
    param([SecureString]$Secret, [string]$CredentialPath)
    if (-not $Secret) {
        $Secret = Read-Host "Paste the one-time Catalog Import API key" -AsSecureString
    }
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Secret)
    $bytes = $null
    try {
        $plaintext = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
        $bytes = [Text.Encoding]::UTF8.GetBytes($plaintext)
        $protected = [Security.Cryptography.ProtectedData]::Protect(
            $bytes,
            $null,
            [Security.Cryptography.DataProtectionScope]::CurrentUser
        )
        [IO.File]::WriteAllBytes($CredentialPath, $protected)
    }
    finally {
        if ($null -ne $bytes) {
            [Array]::Clear($bytes, 0, $bytes.Length)
        }
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
}

function Set-UserEnvironmentDefaults {
    param([pscustomobject]$Configuration, [pscustomobject]$Paths)
    $defaults = @{
        "WPP_EASYWORSHIP_DATA_DIR" = $Configuration.data_directory
        "WPP_CATALOG_EXPORTER_STATE_DIR" = $Paths.StateDirectory
        "WPP_CATALOG_EXPORTER_INSTANCE_ID" = $Configuration.exporter_instance_id
        "WPP_CATALOG_EXPORTER_ENDPOINT" = $Configuration.platform_url
        "WPP_CATALOG_EXPORTER_API_KEY_FILE" = $Paths.CredentialPath
    }
    foreach ($name in $defaults.Keys) {
        [Environment]::SetEnvironmentVariable($name, $defaults[$name], "User")
        [Environment]::SetEnvironmentVariable($name, $defaults[$name], "Process")
    }
}

function New-WeeklyTask {
    param([pscustomobject]$Configuration, [pscustomobject]$Paths, [string]$UserId)
    $arguments = @(
        '--data-dir', ('"' + $Configuration.data_directory + '"'),
        '--state-dir', ('"' + $Paths.StateDirectory + '"'),
        '--instance-id', $Configuration.exporter_instance_id,
        '--endpoint', ('"' + $Configuration.platform_url + '"'),
        '--api-key-file', ('"' + $Paths.CredentialPath + '"'),
        '--scheduled'
    ) -join ' '
    $action = New-ScheduledTaskAction -Execute $Paths.ExecutablePath -Argument $arguments
    $trigger = New-ScheduledTaskTrigger -Weekly -WeeksInterval 1 -DaysOfWeek $Configuration.schedule_day -At "03:00"
    $settings = New-ScheduledTaskSettingsSet `
        -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
        -RestartCount 1 `
        -RestartInterval (New-TimeSpan -Minutes 30) `
        -StartWhenAvailable
    $principal = New-ScheduledTaskPrincipal -UserId $UserId -LogonType Interactive -RunLevel Limited
    return New-ScheduledTask `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Principal $principal
}

function Resolve-AccountSid {
    param([string]$Account)
    if ($Account.StartsWith("S-1-")) {
        return ([Security.Principal.SecurityIdentifier]$Account).Value
    }
    return ([Security.Principal.NTAccount]$Account).Translate([Security.Principal.SecurityIdentifier]).Value
}

function Test-Installation {
    param([pscustomobject]$Paths, [string]$TaskName)
    Assert-PacificTimeZone -TimeZoneId (Get-TimeZone).Id
    foreach ($path in @($Paths.ExecutablePath, $Paths.CredentialPath, $Paths.ConfigurationPath)) {
        if (-not (Test-Path $path -PathType Leaf)) {
            throw "Required installation file is missing: $path"
        }
    }
    $configuration = Get-Content $Paths.ConfigurationPath -Raw | ConvertFrom-Json
    if (-not (Test-Path $configuration.data_directory -PathType Container)) {
        throw "EasyWorship Data directory is unavailable: $($configuration.data_directory)"
    }
    foreach ($database in @("Songs.db", "SongWords.db")) {
        if (-not (Test-Path (Join-Path $configuration.data_directory $database) -PathType Leaf)) {
            throw "Required EasyWorship database is missing: $database"
        }
    }
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    if ($task.Principal.LogonType -ne "Interactive" -or
        (Resolve-AccountSid -Account $task.Principal.UserId) -ne $currentUser.User.Value -or
        $task.Principal.RunLevel -ne "Limited") {
        throw "Scheduled task must use passwordless Interactive logon with limited privileges for the current Windows account."
    }
    if ($task.Settings.RestartCount -ne 1 -or $task.Settings.RestartInterval -ne "PT30M") {
        throw "Scheduled task retry policy is not one retry after 30 minutes."
    }
    Write-Host "Catalog Exporter diagnostics passed."
}

if ($Mode -eq "Validate") {
    $probe = [Text.Encoding]::UTF8.GetBytes("Catalog Exporter credential validation")
    $protected = [Security.Cryptography.ProtectedData]::Protect(
        $probe, $null, [Security.Cryptography.DataProtectionScope]::CurrentUser
    )
    $decrypted = [Security.Cryptography.ProtectedData]::Unprotect(
        $protected, $null, [Security.Cryptography.DataProtectionScope]::CurrentUser
    )
    if ([Convert]::ToBase64String($probe) -ne [Convert]::ToBase64String($decrypted)) {
        throw "Current-user DPAPI credential validation failed."
    }
    foreach ($command in @(
        "Get-TimeZone",
        "New-ScheduledTaskAction",
        "New-ScheduledTaskTrigger",
        "New-ScheduledTaskSettingsSet",
        "New-ScheduledTaskPrincipal",
        "New-ScheduledTask",
        "Register-ScheduledTask"
    )) {
        Get-Command $command -ErrorAction Stop | Out-Null
    }
    Write-Host "Catalog Exporter installer validation passed."
    exit 0
}

$paths = Get-InstallationPaths -UserProfile $env:USERPROFILE
if ($Mode -eq "Diagnose") {
    Test-Installation -Paths $paths -TaskName $TaskName
    exit 0
}

if (-not $PlatformUrl) {
    throw "-PlatformUrl is required for installation."
}
if (-not ([uri]$PlatformUrl).Scheme.Equals("https", [StringComparison]::OrdinalIgnoreCase)) {
    throw "PlatformUrl must use HTTPS."
}
Assert-PacificTimeZone -TimeZoneId (Get-TimeZone).Id
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
New-Item -ItemType Directory -Path $paths.BinaryDirectory -Force | Out-Null
New-Item -ItemType Directory -Path $paths.StateDirectory -Force | Out-Null
New-Item -ItemType Directory -Path $paths.ConfigurationDirectory -Force | Out-Null

$existingConfiguration = $null
if (Test-Path $paths.ConfigurationPath) {
    $existingConfiguration = Get-Content $paths.ConfigurationPath -Raw | ConvertFrom-Json
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
$configuration | ConvertTo-Json | Set-Content $paths.ConfigurationPath -Encoding UTF8
$releases = Invoke-RestMethod -Uri "https://api.github.com/repos/$ReleaseRepository/releases?per_page=50"
$release = Select-CompatibleRelease -Releases $releases
Install-VerifiedExporter -Release $release -ExecutablePath $paths.ExecutablePath
Save-UserScopedCredential -Secret $ApiKey -CredentialPath $paths.CredentialPath
Set-UserEnvironmentDefaults -Configuration $configuration -Paths $paths
$userId = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$task = New-WeeklyTask -Configuration $configuration -Paths $paths -UserId $userId
Register-ScheduledTask -TaskName $TaskName -InputObject $task -Force | Out-Null
Test-Installation -Paths $paths -TaskName $TaskName
Write-Host "Catalog Exporter installed. The weekly import runs $ScheduleDay at 3:00 AM America/Los_Angeles."
Write-Host "The task uses passwordless logon. Keep this Windows account signed in and the computer awake for scheduled imports."
