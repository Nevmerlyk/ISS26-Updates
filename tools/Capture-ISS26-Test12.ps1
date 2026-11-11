#requires -Version 5.1
<#
ISS26 Test12: operator-labelled, read-only PCSX-Redux VRAM capture trigger.
Uses the private existing Academy Test Game Lua calibrator.request handler:
- Captures actual RAM, VRAM and screenshot on the next emulated Vsync.
- Does not touch original BIN/CUE, GPU memory, saves or stable Play Game.
- Distinct output names embed the PHASE selected by the human observer.

Examples (run during Test Game in a separate PowerShell window):
  powershell -NoProfile -ExecutionPolicy Bypass -File .\Capture-ISS26-Test12.ps1 -Phase prematch_banner
  powershell -NoProfile -ExecutionPolicy Bypass -File .\Capture-ISS26-Test12.ps1 -Phase carried_banner
  powershell -NoProfile -ExecutionPolicy Bypass -File .\Capture-ISS26-Test12.ps1 -Phase crowd_flags
  powershell -NoProfile -ExecutionPolicy Bypass -File .\Capture-ISS26-Test12.ps1 -Phase hud

GameRoot defaults to the current project's known Windows install D:\ISS 26.
Override it for other installations, or use -SessionPath copied from
Academy > Progress > Open current session.
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)]
  [ValidateSet('selection','prematch_banner','carried_banner','crowd_flags','hud')]
  [string]$Phase,
  [string]$GameRoot = 'D:\ISS 26',
  [string]$SessionPath
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'

function Check([bool]$ok,[string]$reason) {
  if(-not $ok) { throw $reason }
}

try {
  $sessionsRoot=[IO.Path]::GetFullPath((Join-Path $GameRoot 'ISS26_Data\explorer\sessions'))
  Check (Test-Path -LiteralPath $sessionsRoot -PathType Container) (
    'Academy session directory not found: ' + $sessionsRoot
  )
  Check (([IO.File]::GetAttributes($sessionsRoot) -band [IO.FileAttributes]::ReparsePoint) -eq 0) (
    'Session root must not be a symbolic link/junction.'
  )
  if(-not [string]::IsNullOrWhiteSpace($SessionPath)) {
    $folder=[IO.Path]::GetFullPath($SessionPath)
    Check (([IO.Path]::GetDirectoryName($folder)).TrimEnd('\') -eq $sessionsRoot.TrimEnd('\')) (
      'SessionPath must be a direct child of the configured session directory.'
    )
    Check (Test-Path -LiteralPath $folder -PathType Container) 'Selected Academy session is missing.'
  }
  else {
    $candidates=@(Get-ChildItem -LiteralPath $sessionsRoot -Directory |
      Where-Object {
        (Test-Path -LiteralPath (Join-Path $_.FullName 'session.json') -PathType Leaf) -and
        ($_.Name -match '^\d{8}_\d{6}_[a-z0-9]{6}$')
      } | Sort-Object LastWriteTimeUtc -Descending)
    Check ($candidates.Count -gt 0) 'Start Test Game; no Academy session is present.'
    $folder=$candidates[0].FullName
  }
  Check (([IO.File]::GetAttributes($folder) -band [IO.FileAttributes]::ReparsePoint) -eq 0) (
    'Session directory may not be a link/junction.'
  )
  $sessionInfo=Join-Path $folder 'session.json'
  Check (Test-Path -LiteralPath $sessionInfo -PathType Leaf) 'Missing Academy session metadata.'
  $session=Get-Content -LiteralPath $sessionInfo -Raw -Encoding UTF8 | ConvertFrom-Json
  Check ($session.mode -eq 'Test Game') (
    'Capture requires interactive Test Game, not the timed AutoTest.'
  )
  Check ($session.captureMode -eq 'full-state-on-request') 'Unexpected session capture mode.'
  $started=[DateTimeOffset]::Parse([string]$session.startedUtc)
  Check (([DateTimeOffset]::UtcNow - $started).TotalHours -lt 4) (
    'This session is not recent; close old sessions and start a new Test Game.'
  )
  $running=@(Get-Process -ErrorAction SilentlyContinue |
    Where-Object { $_.ProcessName -like '*pcsx*' })
  Check ($running.Count -gt 0) (
    'PCSX-Redux does not appear to be running. Start Test Game first.'
  )
  $tag='test12_' + $Phase + '_' + ([Guid]::NewGuid().ToString('N').Substring(0,6))
  Check ($tag.Length -le 70) 'Unexpected capture tag size.'
  $request=Join-Path $folder 'calibrator.request'
  Check (-not (Test-Path -LiteralPath $request)) (
    'An earlier VRAM capture request is still pending. Resume emulation before retrying.'
  )
  $payload=[Text.Encoding]::ASCII.GetBytes($tag + "`n")
  $stream=[IO.FileStream]::new($request,[IO.FileMode]::CreateNew,
    [IO.FileAccess]::Write,[IO.FileShare]::None)
  try { $stream.Write($payload,0,$payload.Length) }
  finally { $stream.Dispose() }

  Write-Host ('TEST12_CAPTURE_REQUESTED phase=' + $Phase) -ForegroundColor Green
  Write-Host ('Session: '+ $folder)
  Write-Host ('Expected capture filename prefix: cal_' + $tag + '_')
  Write-Host 'Resume PCSX-Redux for at least one frame. Wait for a matching .vram file.'
  Write-Host 'When all phases have been captured, use Academy > Progress > Export Rookie ZIP.'
  Write-Host 'These labels are HUMAN OBSERVATIONS, not automatic sprite identification.'
}
catch {
  Write-Error ('Test12 capture request was not completed: '+$_.Exception.Message)
  exit 1
}
