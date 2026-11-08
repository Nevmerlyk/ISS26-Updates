#requires -Version 5.1
<# Read-only validation of EU ISS Pro Evolution 2 edited 12-track CUE. #>
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$Cue)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
try {
  $Cue=[IO.Path]::GetFullPath($Cue)
  if (-not (Test-Path -LiteralPath $Cue -PathType Leaf)) {throw "CUE not found: $Cue"}
  $dir=Split-Path -Parent $Cue
  $body=[IO.File]::ReadAllText($Cue)
  $refs=[regex]::Matches($body,'(?im)^\s*FILE\s+"([^"]+)"\s+BINARY\s*$')
  if ($refs.Count -ne 12) {throw "Expected 12 BINARY files, found $($refs.Count)"}
  if ($body -notmatch '(?im)^\s*TRACK\s+01\s+MODE2/2352\s*$') {throw 'Expected TRACK 01 MODE2/2352.'}
  $audio=[regex]::Matches($body,'(?im)^\s*TRACK\s+\d+\s+AUDIO\s*$')
  if ($audio.Count -ne 11) {throw "Expected 11 AUDIO tracks, found $($audio.Count)"}
  $files=@()
  for($i=0;$i -lt $refs.Count;$i++) {
    $name=$refs[$i].Groups[1].Value
    $file=[IO.Path]::GetFullPath((Join-Path $dir $name))
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) {throw "Track $($i+1) missing: $file"}
    $len=(Get-Item -LiteralPath $file).Length
    if ($len -lt 2352 -or $len % 2352 -ne 0) {throw "Track $($i+1) invalid length $len bytes: $name"}
    $files+=$file
    Write-Host ("OK Track {0:00}: {1} sectors" -f ($i+1), [int64]($len/2352))
  }
  $stream=[IO.File]::OpenRead($files[0]);$buffer=New-Object byte[] 2352
  try {
    if ($stream.Read($buffer,0,2352) -ne 2352) {throw 'Cannot read data track.'}
    if ($buffer[0] -ne 0 -or $buffer[11] -ne 0 -or $buffer[15] -ne 2) {throw 'Invalid MODE2 sync/header.'}
    for($i=1;$i -le 10;$i++) {if($buffer[$i] -ne 255) {throw 'Invalid MODE2 sync data.'}}
    [void]$stream.Seek(16*2352,[IO.SeekOrigin]::Begin)
    if ($stream.Read($buffer,0,2352) -ne 2352) {throw 'Cannot read volume descriptor.'}
    if ($buffer[24] -ne 1 -or [Text.Encoding]::ASCII.GetString($buffer,25,5) -ne 'CD001') {throw 'Missing ISO9660 PVD at sector 16.'}
  } finally {$stream.Dispose()}
  $original=Join-Path $dir 'ISS Pro Evolution 2 (Europe) (En,Fr,De).cue'
  if ((Test-Path -LiteralPath $original) -and $Cue -ine $original) {
    $old=[regex]::Matches([IO.File]::ReadAllText($original),'(?im)^\s*FILE\s+"([^"]+)"\s+BINARY\s*$')
    if ($old.Count -eq 12) {
      for($i=1;$i -lt 12;$i++) {if ($old[$i].Groups[1].Value -cne $refs[$i].Groups[1].Value) {throw "Audio track $($i+1) has different reference from original."}}
      Write-Host 'OK: audio track references match original.'
    }
  }
  Write-Host 'PASS: 12-track edited CUE is structurally valid.' -ForegroundColor Green
  Write-Host 'This does NOT validate BIOS, MIPS patch safety, or game stability.'
} catch { Write-Host ('FAIL: '+$_.Exception.Message) -ForegroundColor Red; exit 1 }
