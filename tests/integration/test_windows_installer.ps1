#Requires -Version 5.1
$ErrorActionPreference = "Stop"

$installerPath = Join-Path $PSScriptRoot "..\..\static\install-catalog-exporter.ps1"
$tokens = $null
$parseErrors = $null
$installer = [Management.Automation.Language.Parser]::ParseFile(
    $installerPath, [ref]$tokens, [ref]$parseErrors
)
if ($parseErrors.Count) {
    throw "Installer syntax errors: $parseErrors"
}
# Load function definitions without executing the installer's effectful entry point.
$definitions = $installer.FindAll({
        param($node)
        $node -is [Management.Automation.Language.FunctionDefinitionAst]
    }, $true)
foreach ($definition in $definitions) {
    Invoke-Expression $definition.Extent.Text
}
function Get-Credential { throw "Passwordless installation must not request Windows credentials." }
# Hosted Windows runners use UTC; the existing workflow checks Pacific DST separately.
function Get-TimeZone { return [pscustomobject]@{ Id = "Pacific Standard Time" } }

$releases = @(
    [pscustomobject]@{ tag_name = "exporter/v2.0.0"; draft = $true; prerelease = $false },
    [pscustomobject]@{ tag_name = "exporter/v1.0.0"; draft = $false; prerelease = $true },
    [pscustomobject]@{ tag_name = "app/v1.0.0"; draft = $false; prerelease = $false },
    [pscustomobject]@{ tag_name = "exporter/v0.1.2"; draft = $false; prerelease = $false },
    [pscustomobject]@{ tag_name = "exporter/v0.1.1"; draft = $false; prerelease = $false }
)
if ((Select-CompatibleRelease -Releases $releases).tag_name -ne "exporter/v0.1.2") {
    throw "Release selection must use the newest stable exporter release."
}
$rejected = $false
try { Select-CompatibleRelease -Releases @() | Out-Null }
catch {
    if ($_.Exception.Message -ne "No compatible exporter/v* release is available.") { throw }
    $rejected = $true
}
if (-not $rejected) { throw "An empty release list must be rejected." }

Assert-PacificTimeZone -TimeZoneId "Pacific Standard Time"
$rejected = $false
try { Assert-PacificTimeZone -TimeZoneId "UTC" }
catch {
    if ($_.Exception.Message -notlike "Windows time zone must be*") { throw }
    $rejected = $true
}
if (-not $rejected) { throw "Non-Pacific time zones must be rejected." }

$TaskName = "WPP installer test " + [guid]::NewGuid()
$testDirectory = Join-Path $env:TEMP $TaskName
$paths = Get-InstallationPaths -UserProfile $testDirectory
if ($paths.ExecutablePath -ne (Join-Path $testDirectory ".local\bin\catalog-exporter.exe") -or
    $paths.CredentialPath -ne (Join-Path $testDirectory ".config\WorshipPrep\CatalogExporter\api-key.dpapi")) {
    throw "Installation paths must be scoped to the supplied Windows profile."
}
$paths.ExecutablePath = Join-Path $PSHOME "powershell.exe"
$configuration = [pscustomobject]@{
    data_directory = Join-Path $testDirectory "EasyWorship Data"
    platform_url = "https://api.rccgcm.org"
    exporter_instance_id = [guid]::NewGuid().ToString()
    schedule_day = "Sunday"
}

try {
    New-Item -ItemType Directory -Path $configuration.data_directory -Force | Out-Null
    New-Item -ItemType Directory -Path $paths.ConfigurationDirectory -Force | Out-Null
    foreach ($name in @("Songs.db", "SongWords.db")) {
        New-Item -ItemType File -Path (Join-Path $configuration.data_directory $name) | Out-Null
    }
    Add-Type -AssemblyName System.Security
    $secret = ConvertTo-SecureString "installer test credential" -AsPlainText -Force
    Save-UserScopedCredential -Secret $secret -CredentialPath $paths.CredentialPath
    $existingKey = [IO.File]::ReadAllBytes($paths.CredentialPath)
    Save-UserScopedCredential -CredentialPath $paths.CredentialPath
    if ([Convert]::ToBase64String([IO.File]::ReadAllBytes($paths.CredentialPath)) -ne
        [Convert]::ToBase64String($existingKey)) {
        throw "Reinstallation must preserve the existing protected API key."
    }
    $configuration | ConvertTo-Json | Set-Content $paths.ConfigurationPath

    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $definition = New-WeeklyTask -Configuration $configuration -Paths $paths -UserId $currentUser.User.Value
    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        throw "Task construction must not register a task."
    }
    Register-ScheduledTask -TaskName $TaskName -InputObject $definition -Force | Out-Null
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
    if ($task.Actions.Arguments -notlike '*--endpoint "https://api.rccgcm.org"*') {
        throw "Scheduled uploads must use the API domain."
    }
    if ($task.Principal.LogonType -ne "Interactive" -or
        $task.Principal.RunLevel -ne "Limited" -or
        (Resolve-AccountSid -Account $task.Principal.UserId) -ne $currentUser.User.Value) {
        throw ("Task principal differs: logon={0}, privileges={1}, account={2}; expected SID={3}, name={4}." -f
            $task.Principal.LogonType, $task.Principal.RunLevel, $task.Principal.UserId,
            $currentUser.User.Value, $currentUser.Name)
    }
    if ((Resolve-AccountSid -Account $currentUser.User.Value) -ne $currentUser.User.Value) {
        throw "Account SID resolution must also accept a SID directly."
    }
    if ($task.Triggers[0].DaysOfWeek -ne 1 -or
        $task.Triggers[0].WeeksInterval -ne 1 -or
        ([datetime]$task.Triggers[0].StartBoundary).TimeOfDay -ne (New-TimeSpan -Hours 3)) {
        throw "Task must run weekly on Sunday at 03:00."
    }
    if ($task.Settings.RestartCount -ne 1 -or
        $task.Settings.RestartInterval -ne "PT30M" -or
        $task.Settings.ExecutionTimeLimit -ne "PT1H" -or
        -not $task.Settings.StartWhenAvailable) {
        throw "Task must preserve the time limit, missed-run policy, and one retry after 30 minutes."
    }
    foreach ($required in @(
        ('--data-dir "' + $configuration.data_directory + '"'),
        ('--state-dir "' + $paths.StateDirectory + '"'),
        ('--instance-id ' + $configuration.exporter_instance_id),
        '--endpoint "https://api.rccgcm.org"',
        ('--api-key-file "' + $paths.CredentialPath + '"'),
        '--scheduled'
    )) {
        if (-not $task.Actions[0].Arguments.Contains($required)) {
            throw "Task argument is missing: $required"
        }
    }
    Test-Installation -Paths $paths -TaskName $TaskName

    # Replace only the read result to check rejection without changing the registered task.
    $invalidTask = $task
    $invalidTask.Principal.LogonType = "Password"
    function Get-ScheduledTask { return $invalidTask }
    $rejected = $false
    try {
        Test-Installation -Paths $paths -TaskName $TaskName
    }
    catch {
        if ($_.Exception.Message -notlike "*passwordless Interactive logon*") {
            throw
        }
        $rejected = $true
    }
    if (-not $rejected) {
        throw "Diagnostics accepted a password-based task."
    }
    Write-Host "Passwordless task registration and diagnostics passed."
}
finally {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Remove-Item $testDirectory -Recurse -Force -ErrorAction SilentlyContinue
}
