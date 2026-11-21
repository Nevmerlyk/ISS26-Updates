# ISS26 Academy 0.9.6.14: build, verify and publish Windows launcher.
# Does not modify game BIN/CUE, saves or Stable game patch.
$ErrorActionPreference="Stop"
$ProgressPreference="SilentlyContinue"
$v="0.9.6.14"
$repo="Nevmerlyk/ISS26-Android"
$updates="Nevmerlyk/ISS26-Updates"
$branch="release/academy-0.9.6.14-stable-rc1"
$pin="002a5bc755a504ee07b34ad33ddb70f99ea24804"
$tag="launcher-v$v"
$url="https://github.com/$updates/releases/download/$tag/ISS26-LauncherUpdate.zip"
$root=Join-Path $env:LOCALAPPDATA "ISS26\releases\academy-$v"
$src=Join-Path $root "source"
$out=Join-Path $root "output"
$logs=Join-Path $root "logs"
New-Item -ItemType Directory -Force -Path $logs | Out-Null
Start-Transcript -LiteralPath (Join-Path $logs "publish.log") -Append | Out-Null
function RefreshPath {
  $env:PATH=[Environment]::GetEnvironmentVariable("PATH","Machine")+";"+[Environment]::GetEnvironmentVariable("PATH","User")
}
function NeedCommand([string]$cmd,[string]$package) {
  if(Get-Command $cmd -ErrorAction SilentlyContinue){return}
  if(-not(Get-Command winget -ErrorAction SilentlyContinue)){throw "Missing $cmd. Install $package."}
  & winget install --id $package --exact --accept-source-agreements --accept-package-agreements
  if($LASTEXITCODE -ne 0){throw "Could not install $package"}
  RefreshPath
  if(-not(Get-Command $cmd -ErrorAction SilentlyContinue)){throw "$cmd not on PATH; reopen PowerShell."}
}
function Gh([string[]]$p) {
  $old=$ErrorActionPreference
  try { $ErrorActionPreference="Continue";$output=& gh @p 2>&1;$ec=$LASTEXITCODE }
  finally { $ErrorActionPreference=$old }
  if($ec -ne 0){throw "GitHub CLI failed: gh $($p -join ' ') : $($output -join ' ')"}
  return ($output -join [Environment]::NewLine)
}
function GetMeta([string]$path){ Gh @("api","repos/$updates/contents/$path") | ConvertFrom-Json }
function Hash([string]$path){(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToUpperInvariant()}
try {
  if($env:OS -ne "Windows_NT"){throw "Windows required"}
  $who=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
  if($who.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw "Run as a normal Windows user, not Administrator."}
  NeedCommand "git" "Git.Git"
  NeedCommand "gh" "GitHub.cli"
  NeedCommand "dotnet" "Microsoft.DotNet.SDK.8"
  NeedCommand "luajit" "DEVCOM.LuaJIT"
  if(-not(@(dotnet --list-sdks)|Where-Object {$_ -match '^8\.'})){throw "Install .NET SDK 8, not only runtime."}
  $old=$ErrorActionPreference
  try{$ErrorActionPreference="Continue";& gh auth status *> $null;$signed=$LASTEXITCODE -eq 0}
  finally{$ErrorActionPreference=$old}
  if(-not $signed){& gh auth login --web;if($LASTEXITCODE -ne 0){throw "GitHub login failed"}}
  & gh auth setup-git
  if($LASTEXITCODE -ne 0){throw "Git credential setup failed"}
  if(-not(Test-Path (Join-Path $src ".git"))){
    & git clone --depth 1 --single-branch --branch $branch "https://github.com/$repo.git" $src
    if($LASTEXITCODE -ne 0){throw "Private GitHub clone failed"}
  }else{
    & git -C $src fetch origin $branch --depth 1
    if($LASTEXITCODE -ne 0){throw "Git fetch failed"}
    & git -C $src checkout --detach FETCH_HEAD
    if($LASTEXITCODE -ne 0){throw "Git checkout failed"}
  }
  $head=(& git -C $src rev-parse HEAD).Trim().ToLowerInvariant()
  if($head -ne $pin){throw "Source changed from reviewed release: $head (expected $pin)"}
  Write-Host "Compiling Academy $v and running all C# + LuaJIT tests..."
  New-Item -ItemType Directory -Force -Path $out | Out-Null
  $build=Join-Path $src "windows\build-academy-dev56.ps1"
  $stdout=Join-Path $logs "build.out.log"
  $stderr=Join-Path $logs "build.err.log"
  $arguments=@("-NoProfile","-ExecutionPolicy","Bypass","-File",('"' + $build + '"'),"-Output",('"' + $out + '"'))
  $proc=Start-Process powershell.exe -ArgumentList $arguments -Wait -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
  if($proc.ExitCode -ne 0){
    Get-Content $stdout -Tail 40 | Write-Host
    if((Test-Path $stderr) -and (Get-Item $stderr).Length -gt 0){Get-Content $stderr -Tail 20 | Write-Host}
    throw "Build/test failed; logs in $logs"
  }
  if(-not((Get-Content $stdout -Raw).Contains("BUILD PASSED: DEV56 local candidate"))){throw "Build did not confirm passing tests"}
  $launcher=Join-Path $out "binaries\ISS26.exe"
  $updater=Join-Path $out "binaries\ISS26.Updater.exe"
  $candidate=Join-Path $out "ISS26-DEV56-LOCAL-ONLY.zip"
  foreach($file in @($launcher,$updater,$candidate)){if(-not(Test-Path $file)){throw "Missing: $file"}}
  foreach($file in @($launcher,$updater)){
    $fv=[Diagnostics.FileVersionInfo]::GetVersionInfo($file).FileVersion
    if(-not $fv.StartsWith($v)){throw "Wrong binary version $fv in $file"}
  }
  Add-Type -AssemblyName System.IO.Compression
  $zip=[IO.Compression.ZipFile]::OpenRead($candidate)
  try{
    $names=@($zip.Entries|ForEach-Object{$_.FullName})
    if($names.Count -ne 2 -or $names -cnotcontains "ISS26.exe" -or $names -cnotcontains "ISS26.Updater.exe"){throw "Unexpected ZIP contents"}
    foreach($entry in $zip.Entries){
      $file=if($entry.FullName -ceq "ISS26.exe"){$launcher}else{$updater}
      if($entry.Length -lt 1000000 -or $entry.Length -gt 160MB){throw "Invalid executable size"}
      $stream=$entry.Open()
      try{$sha=[Security.Cryptography.SHA256]::Create();try{$digest=[BitConverter]::ToString($sha.ComputeHash($stream)).Replace("-","")}finally{$sha.Dispose()}}finally{$stream.Dispose()}
      if($digest -ne (Hash $file)){throw "ZIP binary hash mismatch: $($entry.FullName)"}
    }
  }finally{$zip.Dispose()}
  if((Get-Item $candidate).Length -gt 160MB){throw "ZIP exceeds updater size limit"}
  $ziphash=Hash $candidate
  $feed=GetMeta "launcher/latest.json"
  $state=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String(($feed.content -replace '\s+','')))|ConvertFrom-Json
  $stable=GetMeta "stable/latest.json"
  if($state.latest.version -eq $v){
    if($state.latest.zipSha256 -eq $ziphash -and $state.latest.launcherSha256 -eq (Hash $launcher) -and $state.latest.updaterSha256 -eq (Hash $updater)){Write-Host "ALREADY ACTIVE 0.9.6.14";return}
    throw "A different 0.9.6.14 binary is already active"
  }
  if($state.latest.version -ne "0.9.6.11"){throw "Unexpected current launcher $($state.latest.version)"}
  $old=$ErrorActionPreference
  try{$ErrorActionPreference="Continue";& gh release view $tag --repo $updates *> $null;$exists=$LASTEXITCODE -eq 0}
  finally{$ErrorActionPreference=$old}
  if(-not $exists){
    Gh @("release","create",$tag,$candidate,"--repo",$updates,"--target","main","--latest=false","--title","ISS26 Academy $v Stable Windows launcher","--notes","Launcher-only release; game BIN/CUE and Stable PS1 patch unchanged.")|Out-Null
  }
  $remote=Join-Path $out "verified-public.zip"
  for($i=0;$i -lt 5;$i++){
    try{
      Invoke-WebRequest -Uri $url -OutFile $remote -UseBasicParsing -TimeoutSec 120
      if((Hash $remote) -ne $ziphash){throw "Remote release differs from tested local ZIP"}
      break
    }catch{if($i -eq 4){throw};Start-Sleep -Seconds 4}
  }
  $check=GetMeta "launcher/latest.json"
  if($check.sha -ne $feed.sha){throw "Launcher feed updated concurrently"}
  if((GetMeta "stable/latest.json").sha -ne $stable.sha){throw "Game Stable feed changed; refusing publication"}
  $body=@{schemaVersion=1;latest=@{
    version=$v;zipUrl=$url;zipSha256=$ziphash;
    launcherSha256=(Hash $launcher);updaterSha256=(Hash $updater);
    notes="Academy $v stable Windows launcher; original CUE, PgUp/PgDn and reviewed GitHub scripts. Stable PS1 game patch unchanged."
  }}|ConvertTo-Json -Depth 8
  $req=@{branch="main";sha=$feed.sha;message="Release verified Academy $v Windows auto-update";content=[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($body))}|ConvertTo-Json -Depth 6
  $request=Join-Path $out "publish-feed.json"
  [IO.File]::WriteAllText($request,$req,[Text.UTF8Encoding]::new($false))
  Gh @("api","--method","PUT","repos/$updates/contents/launcher/latest.json","--input",$request)|Out-Null
  $verified=GetMeta "launcher/latest.json"
  $actual=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String(($verified.content -replace '\s+','')))|ConvertFrom-Json
  if($actual.latest.version -ne $v -or $actual.latest.zipSha256 -ne $ziphash){throw "Feed readback mismatch"}
  Write-Host "PUBLISHED: ISS26 $v ACTIVE! Run your usual ISS26.exe to auto-update." -ForegroundColor Green
}catch{
  Write-Host ("STOPPED: "+$_.Exception.Message) -ForegroundColor Red
  Write-Host "Logs: $logs"
  throw
}finally{Stop-Transcript|Out-Null}
