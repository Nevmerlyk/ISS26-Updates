param(
  [Parameter(Mandatory=$true)][string]$Track01,
  [string]$OutDir=(Join-Path $PSScriptRoot '..\artifacts\v0.9.6-test'),
  [string]$Baseline=''
)
$ErrorActionPreference='Stop'
$track=(Resolve-Path -LiteralPath $Track01).Path
$script=Join-Path $PSScriptRoot 'build_v096_test1.py'
$argsList=@($script,'--track',$track,'--out',$OutDir)
if ($Baseline) { $argsList += @('--baseline',(Resolve-Path -LiteralPath $Baseline).Path) }
& python @argsList
if ($LASTEXITCODE -ne 0) { throw 'ISS26 test build failed; no channel update' }
Write-Host "Local candidate built: $OutDir. Names only; not published. Run emulator tests before uploading."
