#requires -Version 5.1
<#
ISS26 flag style inspector: read-only.
Reads five known 78-byte selection/club flag style tables inside raw
European PS1 Track 01 BIN. Never patches or copies game images.
Use: powershell.exe -NoProfile -ExecutionPolicy Bypass -File "Inspect-ISS26-FlagStyles.ps1" -Cue "D:\ISS 26\ISS26_Neuer_AI_v02.cue"
Optional -OutputCsv "D:\ISS 26\ISS26_Data\diagnostics\flags.csv"
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$Cue,
  [string]$OutputCsv
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$offsets = @(
  [int64]0x1D6F48,
  [int64]0x1E94CC,
  [int64]0x224C50,
  [int64]0x4AD4B8,
  [int64]0x575864
)
$slots = @{
  0='C.VERDE'; 1='ALGERIA'; 3='I.COAST'; 17='GHANA'
  19='DR CONGO'; 22='HAITI'; 24='CURACAO'; 25='JORDAN'
  26='IRAQ'; 27='N.ZEAL'; 30='BOSNIA'; 35='SENEGAL'
  39='CANADA'; 42='ECUADOR'; 43='PANAMA'; 49='UZBEK'; 51='QATAR'
}

function Check([bool]$ok, [string]$message) {
  if (-not $ok) {throw $message}
}

try {
  $Cue=[IO.Path]::GetFullPath($Cue)
  Check (Test-Path -LiteralPath $Cue -PathType Leaf) ('CUE not found: ' + $Cue)
  $body=[IO.File]::ReadAllText($Cue)
  $files=[regex]::Matches($body, '(?im)^\s*FILE\s+"([^"]+)"\s+BINARY\s*$')
  Check ($files.Count -eq 12) ('Expected 12 Track FILE BINARY entries: got ' + $files.Count)
  $first=$files[0].Groups[1].Value
  $track=if([IO.Path]::IsPathRooted($first)){$first}else{Join-Path (Split-Path $Cue -Parent) $first}
  $track=[IO.Path]::GetFullPath($track)
  Check (Test-Path -LiteralPath $track -PathType Leaf) ('Track 01 missing: ' + $track)

  $stream=[IO.File]::Open($track,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
  try {
    Check ($stream.Length -ge ($offsets[-1]+78)) 'Track 01 is too short for all known tables.'
    $tables=New-Object 'System.Collections.Generic.List[byte[]]'
    foreach ($off in $offsets) {
      [void]$stream.Seek($off,[IO.SeekOrigin]::Begin)
      $block=New-Object byte[] 78
      $read=$stream.Read($block,0,78)
      Check ($read -eq 78) ('Short style table at offset 0x{0:X}' -f $off)
      [void]$tables.Add($block)
    }
  }
  finally {$stream.Dispose()}

  Write-Host ('Track 01: ' + $track)
  Write-Host 'Known style-table offsets:' ($offsets | ForEach-Object { '0x{0:X}' -f $_ })
  Write-Host 'Entries 00-53 are national teams; 54-77 are clubs.'
  Write-Host 'Slot names below are ISS26 project targets; an older image may use other team names.'
  Write-Host ''
  $rows=@()
  $mismatches=0
  for($i=0; $i -lt 78; $i++) {
    $values=@(0..4 | ForEach-Object {[int]$tables[$_][$i]})
    $same=(@($values|Select-Object -Unique).Count -eq 1)
    if(-not $same){$mismatches++}
    $category=if($i -lt 54){'national'}else{'club'}
    $name=if($slots.ContainsKey($i)){$slots[$i]}else{''}
    $row=[PSCustomObject]@{
      Slot=$i
      Category=$category
      ISS26Target=$name
      StyleId=$values[0]
      Table1=$values[0]; Table2=$values[1]; Table3=$values[2]
      Table4=$values[3]; Table5=$values[4]
      TablesAgree=$same
    }
    $rows+=$row
    if($name) {
      $mark=if($same){'OK'}else{'MISMATCH'}
      Write-Host ('[{0}] slot {1,2}: {2,-9} style {3,2}  tables={4}' -f
        $mark,$i,$name,$values[0],($values -join '/'))
    }
  }
  Write-Host ''
  Write-Host ('All 78 slots: {0} mismatched across the five tables.' -f $mismatches)
  $invalid=@($rows | Where-Object {$_.Category -eq 'national' -and $_.StyleId -gt 43})
  Write-Host ('National style IDs outside observed 0-43 range: {0}' -f $invalid.Count)
  if($invalid.Count){$invalid | Format-Table Slot,ISS26Target,StyleId -AutoSize | Out-Host}
  $groups=@($rows | Where-Object {$_.Category -eq 'national'} |
    Group-Object StyleId | Where-Object {$_.Count -gt 1})
  Write-Host ('Shared national style IDs: {0}' -f $groups.Count)
  foreach ($g in $groups) {
    Write-Host ('  Style {0}: slots {1}' -f $g.Name,
      (($g.Group | ForEach-Object {$_.Slot}) -join ', '))
  }
  if($OutputCsv){
    $OutputCsv=[IO.Path]::GetFullPath($OutputCsv)
    $parent=Split-Path -Parent $OutputCsv
    if(-not (Test-Path -LiteralPath $parent)){
      New-Item -Path $parent -ItemType Directory -Force | Out-Null
    }
    $rows | Export-Csv -Path $OutputCsv -Encoding UTF8 -NoTypeInformation
    Write-Host ('CSV saved: '+$OutputCsv) -ForegroundColor Green
  }
  Write-Host 'Read-only inspection complete. No game data were changed.' -ForegroundColor Green
}
catch {
  Write-Host ('ERROR: '+$_.Exception.Message) -ForegroundColor Red
  exit 1
}
