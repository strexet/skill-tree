$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$node = Get-Command node -ErrorAction SilentlyContinue

if (-not $node) {
  Write-Error "Node.js 18 or newer is required."
  exit 1
}

& node (Join-Path $scriptDir ".skill-tree/bin/install.js") @args
exit $LASTEXITCODE
