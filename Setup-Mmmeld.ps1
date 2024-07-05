# Get the directory of the current script
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Create the mmmeld.ps1 script
@"
if (`$args.Count -eq 0) {
    python "$scriptDir\mmmeld.py"
} else {
    python "$scriptDir\mmmeld.py" `$args
}
"@ | Out-File -FilePath "$scriptDir\mmmeld.ps1" -Encoding utf8

# Create .local and .local/bin if they don't exist
$localPath = Join-Path $env:USERPROFILE ".local"
$localBinPath = Join-Path $localPath "bin"
if (-not (Test-Path $localPath)) {
    New-Item -ItemType Directory -Path $localPath -Force | Out-Null
}
if (-not (Test-Path $localBinPath)) {
    New-Item -ItemType Directory -Path $localBinPath -Force | Out-Null
}

# Move the mmmeld.ps1 script to .local/bin
Move-Item -Path "$scriptDir\mmmeld.ps1" -Destination "$localBinPath\mmmeld.ps1" -Force

# Add .local/bin to PATH if it's not already there
$userPath = [Environment]::GetEnvironmentVariable("PATH", "User")
if ($userPath -notlike "*$localBinPath*") {
    $newPath = "$userPath;$localBinPath"
    [Environment]::SetEnvironmentVariable("PATH", $newPath, "User")
    $env:PATH = "$env:PATH;$localBinPath"
    Write-Host ".local/bin has been added to your PATH environment variable."
} else {
    Write-Host ".local/bin is already in your PATH environment variable."
}

# Create a function to run mmmeld
$profileContent = @"
function mmmeld {
    if (`$args.Count -eq 0) {
        & "$localBinPath\mmmeld.ps1"
    } else {
        & "$localBinPath\mmmeld.ps1" `$args
    }
}
"@

# Update the function in the PowerShell profile
$profilePath = $PROFILE.CurrentUserAllHosts
if (-not (Test-Path $profilePath)) {
    New-Item -ItemType File -Path $profilePath -Force | Out-Null
}
Add-Content -Path $profilePath -Value $profileContent

Write-Host "mmmeld has been deployed. You may need to restart your PowerShell session to use it immediately."
