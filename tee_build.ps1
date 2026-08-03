# tee_build.ps1
# Runs the given batch file and mirrors its combined output (stdout + stderr)
# to BOTH the console and a log file, so a build failure is never silent.
#
# Usage (invoked from build.bat):
#   powershell -File tee_build.ps1 "<bat path>" "<log path>"
param(
    [string]$Bat,
    [string]$Log
)

if (-not $Bat -or -not (Test-Path $Bat)) {
    Write-Error "tee_build.ps1: batch file not found: '$Bat'"
    exit 2
}

# Wrap the path in quotes for cmd.exe. Using a PowerShell string (not batch
# escaping) keeps this unambiguous.
$quoted = '"' + $Bat + '"'

try {
    & cmd /c $quoted 2>&1 | Tee-Object -FilePath $Log
    exit $LASTEXITCODE
} catch {
    Write-Error "tee_build.ps1 failed: $_"
    exit 1
}
