# ISS26 remote diagnostics demo: local read-only Windows summary.
$ErrorActionPreference = 'Stop'
Write-Output ('ISS26_ACADEMY_POWERSHELL ' + $PSVersionTable.PSVersion.ToString())
Write-Output ('Windows ' + [Environment]::OSVersion.VersionString)
Write-Output ('Is64BitProcess ' + [Environment]::Is64BitProcess)
