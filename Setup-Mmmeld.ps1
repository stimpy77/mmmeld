# Get the directory of the current script
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Create the mmmeld.ps1 script
@"
python "$scriptDir\mmmeld.py" `$args
"@ | Out-File -FilePath "$scriptDir\mmmeld.ps1" -Encoding utf8

# Add the script directory to PATH if it's not already there
$userPath = [Environment]::GetEnvironmentVariable("PATH", "User")
if ($userPath -notlike "*$scriptDir*") {
    $newPath = "$userPath;$scriptDir"
    [Environment]::SetEnvironmentVariable("PATH", $newPath, "User")
    $env:PATH = "$env:PATH;$scriptDir"
}

# Create a function to run mmmeld
$profileContent = @"
function mmmeld { & "$scriptDir\mmmeld.ps1" `$args }
"@

# Add the function to the PowerShell profile
if (!(Test-Path $PROFILE)) {
    New-Item -Path $PROFILE -ItemType File -Force
}
Add-Content -Path $PROFILE -Value $profileContent

Write-Host "mmmeld has been deployed. You may need to restart your PowerShell session to use it immediately."
