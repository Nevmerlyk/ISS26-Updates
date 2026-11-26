param([string]$Root = "D:\ISS 26", [string]$Plan = "")
$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"
$work = Join-Path $Root "ISS26_Data\dev85-kits"
New-Item -ItemType Directory -Force $work | Out-Null
$src = Join-Path $work "source"
if (!(Test-Path (Join-Path $src ".git"))) {
    git clone --depth 1 https://github.com/Nevmerlyk/ISS26-Updates.git $src
    if ($LASTEXITCODE -ne 0) { throw "Git clone failed" }
} else {
    git -C $src pull --ff-only
    if ($LASTEXITCODE -ne 0) { throw "Git update failed" }
}
$name = "ISS Pro Evolution 2 (Europe) (En,Fr,De) (Track 01).bin"
$track = Join-Path $Root $name
if (!(Test-Path -LiteralPath $track)) {
    $candidates = @(Get-ChildItem -LiteralPath $Root -Filter $name -File -Recurse -ErrorAction SilentlyContinue)
    $track = $null
    foreach ($f in $candidates) {
        if ($f.Length -eq 496156752 -and (Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash -eq "D9B483BDEA7774346DF437FEBF038E68CB2C4AD9932A7AD993D3C2B1F620EA44") {
            $track = $f.FullName; break
        }
    }
    if (!$track) { throw "Clean European Track 01 not found under $Root" }
}
$patch = Join-Path $work "ISS26_0.9.7.iss26p"
if (!(Test-Path $patch) -or (Get-FileHash $patch -Algorithm SHA256).Hash -ne "A97C3DA1264FA46E0C0AF41E3BA600696C0D432F0D0279C8B29BF8AD5D0786B6") {
    Invoke-WebRequest "https://github.com/Nevmerlyk/ISS26-Updates/releases/download/v0.9.7/ISS26_0.9.7.iss26p" -OutFile $patch
}
$out = Join-Path $work ("DEV85_" + (Get-Date -Format "yyyyMMdd_HHmmss"))
$argsList = @((Join-Path $src "tools\build_dev85_kits.py"),"--track",$track,"--stable",$patch,"--out",$out)
if ($Plan) { $argsList += @("--plan",$Plan) }
python @argsList
if ($LASTEXITCODE -ne 0) { throw "DEV85 tool failed; game unchanged" }
if (!$Plan) {
    $archive = "$out.zip"
    Compress-Archive -Path "$out\*" -DestinationPath $archive
    Write-Host "Send this inventory and preview archive: $archive" -ForegroundColor Cyan
} else {
    Write-Host "Standalone candidate in $out. Not published." -ForegroundColor Cyan
}
