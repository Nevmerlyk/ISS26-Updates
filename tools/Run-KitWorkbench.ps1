$ErrorActionPreference = 'Stop'
$root = if ($args.Count -gt 0) { $args[0] } else { 'D:\ISS 26' }
$root = (Resolve-Path -LiteralPath $root).Path
$tmp = Join-Path ([IO.Path]::GetTempPath()) ('ISS26-KitWorkbench-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tmp | Out-Null
try {
    $base = 'https://raw.githubusercontent.com/Nevmerlyk/ISS26-Updates/b406887c7063878cc698e72fe8301d2f6bc6871b/tools/'
    foreach ($name in @('kit_resource_probe.py','kit_tex_workbench.py')) {
        Invoke-WebRequest -UseBasicParsing -Uri ($base+$name) -OutFile (Join-Path $tmp $name)
    }
    $probe = Join-Path $tmp 'kit_tex_workbench.py'
    $folder = Join-Path $root 'ISS26_Data\diagnostics'
    New-Item -ItemType Directory -Force -Path $folder | Out-Null
    $out = Join-Path $folder ('KitLayout_'+[DateTime]::Now.ToString('yyyyMMdd_HHmmss')+'_'+[guid]::NewGuid().ToString('N').Substring(0,6)+'.json')
    $python = Get-Command py -ErrorAction SilentlyContinue
    $prefix = @()
    if ($python) { $prefix = @('-3') } else { $python = Get-Command python -ErrorAction Stop }
    & $python.Source @prefix $probe self-test
    if ($LASTEXITCODE -ne 0) { throw 'Kit Workbench self-test failed; no game was modified' }
    & $python.Source @prefix $probe inventory --root $root --out $out
    if ($LASTEXITCODE -ne 0) { throw 'Read-only layout audit failed' }
    Write-Host "SUCCESS: $out"
} finally {
    Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
}
