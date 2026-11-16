param([Parameter(Mandatory=$true)][string]$Track01,[string]$OutputDir=(Join-Path $PSScriptRoot '..\database-preflight'))
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$track=(Resolve-Path -LiteralPath $Track01).Path
$reg=Get-Content -Raw (Join-Path $root 'data\integration\eu_v096_registry.json') | ConvertFrom-Json
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$patch=Join-Path $OutputDir 'ISS26_0.9.5_RC1.iss26p'
if (!(Test-Path -LiteralPath $patch) -or (Get-FileHash -Algorithm SHA256 -LiteralPath $patch).Hash -ne $reg.baseline.patch_sha256) {
  Invoke-WebRequest -UseBasicParsing -Uri $reg.baseline.url -OutFile $patch
}
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $patch).Hash -ne $reg.baseline.patch_sha256) { throw 'RC1 patch SHA mismatch' }
& python (Join-Path $root 'tools\integration_preflight_v096.py') --track $track --baseline $patch --out $OutputDir
if ($LASTEXITCODE -ne 0) { throw 'Database preflight failed' }
Write-Host "Read-only preflight complete: $OutputDir. No patch built or published."
