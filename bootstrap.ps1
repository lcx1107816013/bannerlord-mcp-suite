<#
.SYNOPSIS
  把本伞仓跑起来：检查环境 → 探测三个业务 MCP 的位置 → 报告缺什么。

.DESCRIPTION
  本伞仓**刻意不 vendor** 那三个业务 MCP（理由见 docs/why-umbrella-repo.md）。
  所以新使用者需要知道"我缺哪个、该放哪"。本脚本就干这件事。

  ★ 它**只读、不写任何东西**（除 -WriteEnv 时生成一个 .env.ps1）。
  ⇒ 先跑它看清现状，再决定要不要配。

.PARAMETER WriteEnv
  把探测到的路径写成本目录下的 `.env.ps1`（供你 `source` 后使用）。
  默认**不写**（只报告）。

.PARAMETER Check
  只做环境检查（Python / Bun / 游戏目录 / 三个上游），不跑自测。

.EXAMPLE
  .\bootstrap.ps1
  检查并报告，然后跑一次 --selftest。

.EXAMPLE
  .\bootstrap.ps1 -WriteEnv
  探测路径并写出 .env.ps1。
#>
[CmdletBinding()]
param(
    [switch]$WriteEnv,
    [switch]$Check
)

$ErrorActionPreference = 'Continue'
$Root = $PSScriptRoot
Set-Location $Root

function Say($m) { Write-Host $m }
function Ok($m)   { Write-Host "  [ok]   $m" -ForegroundColor Green }
function Warn($m) { Write-Host "  [warn] $m" -ForegroundColor Yellow }
function Bad($m)  { Write-Host "  [MISS] $m" -ForegroundColor Red }

Say "bannerlord-mcp-suite · 环境探测"
Say ("=" * 68)
Say ""

# ── 1. Python ─────────────────────────────────────────────────────────────
Say "1) Python"
$py = $null
foreach ($cand in @(
    (Get-Command python  -ErrorAction SilentlyContinue | Select-Object -First 1).Source,
    (Get-Command python3 -ErrorAction SilentlyContinue | Select-Object -First 1).Source,
    'D:\Program Files\Python312\python.exe'
)) {
    if ($cand -and (Test-Path $cand)) { $py = $cand; break }
}
if ($py) {
    $ver = & $py --version 2>&1
    Ok "$py  ($ver)"
} else {
    Bad "找不到 Python —— 必需（本伞仓全部代码都是 Python）"
}

# ── 2. Bun（可选） ────────────────────────────────────────────────────────
Say ""
Say "2) Bun（仅当要挂 bannerlordsage / bannerlordhelper 时需要）"
$bun = $env:DSH_CHAIN_BUN
if (-not $bun -or -not (Test-Path $bun)) {
    $bun = $null
    foreach ($cand in @(
        (Get-Command bun -ErrorAction SilentlyContinue | Select-Object -First 1).Source
    ) + (Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Recurse -Filter 'bun.exe' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName)) {
        if ($cand -and (Test-Path $cand)) { $bun = $cand; break }
    }
}
if ($bun) { Ok "$bun" } else { Warn "没找到 Bun —— 两个 TS 上游将无法启动（其余照常）" }

# ── 3. 游戏目录 ───────────────────────────────────────────────────────────
Say ""
Say "3) 游戏根目录（Bannerlord）"
$game = $env:BANNERLORD_DIR
$gameCands = @($game) + @(
    'G:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord',
    'C:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord',
    'D:\Steam\steamapps\common\Mount & Blade II Bannerlord'
)
$gameFound = $null
foreach ($c in $gameCands) {
    if ($c -and (Test-Path (Join-Path $c 'Modules'))) { $gameFound = $c; break }
}
if ($gameFound) { Ok "$gameFound" } else { Warn "没找到（不影响 --selftest；但审计工具需要它）" }

# ── 4. 三个业务 MCP ───────────────────────────────────────────────────────
Say ""
Say "4) 三个业务 MCP（★ 本伞仓不包含它们，见 docs/why-umbrella-repo.md）"

$checks = @(
    @{ name='blbridge';         env='DSH_CHAIN_BLBRIDGE'; repo='https://github.com/lcx1107816013/Bannerlord-blbridge.git';
       cands=@($env:DSH_CHAIN_BLBRIDGE, 'C:\Users\LCGX\CodeBuddy\20260923171333\BlBridge'); probe='tools\bl_mcp.py' },
    @{ name='bannerlordsage';   env='DSH_CHAIN_SAGE';     repo='https://github.com/lcx1107816013/BannerlordSage-variant.git';
       cands=@($env:DSH_CHAIN_SAGE,     'F:\Program Files\BannerlordSage');               probe='src\entrypoints\bannerlord-full-stdio.ts' },
    @{ name='bannerlordhelper'; env='DSH_CHAIN_HELPER';   repo='https://github.com/lcx1107816013/Bannerlord-Helper-variant.git';
       cands=@($env:DSH_CHAIN_HELPER,   'F:\Program Files\Bannerlord.Helper');            probe='mcp\server.ts' }
)
$resolved = @{}
$missing = @()
foreach ($c in $checks) {
    $hit = $null
    foreach ($p in $c.cands) {
        # ★ 健壮性：`Join-Path`/`Test-Path` 遇到**不存在的驱动器**（如 X:\）会报
        #   "找不到驱动器" —— 而"用户还没 clone"正是**最常见的正常情形**，
        #   不该让它刷一屏红字。
        #   ⚠️ 这类是**非终止错误**，`try/catch` 抓不到 ⇒ 必须显式
        #      `-ErrorAction SilentlyContinue` + 清 `$Error`。
        if (-not $p) { continue }
        $probe = $null
        try {
            $probe = Join-Path $p $c.probe -ErrorAction SilentlyContinue
        } catch {
            $probe = $null
        }
        if (-not $probe) { continue }
        $ok = Test-Path -LiteralPath $probe -ErrorAction SilentlyContinue
        if ($ok) { $hit = $p; break }
    }
    if ($hit) {
        $resolved[$c.env] = $hit
        Ok "$($c.name)  ->  $hit"
    } else {
        $missing += $c
        Bad "$($c.name)  —— 没找到"
        Write-Host "         ★ 从这拿：$($c.repo)" -ForegroundColor Yellow
        Write-Host "           然后设 `$env:$($c.env) = '<你 clone 的路径>'" -ForegroundColor Yellow
    }
}
$Error.Clear()   # 清掉上面探测产生的非终止错误，别让它们影响后续输出

# 第 4 个 MCP：这个**就在本仓库里**，永远可用
$la = Join-Path $Root 'localization-audit\la_mcp.py'
if (Test-Path $la) { Ok "localization-audit  ->  本仓库内（自带，无需外部部署）" }
else { Bad "localization-audit 缺失（本仓库应自带它 —— 请检查 clone 完整性）" }

# 若有缺失 ⇒ 汇总一句可照抄的修复指引
if ($missing.Count -gt 0) {
    Say ""
    Say "  ── 缺失的上游怎么补（复制粘贴即可）──"
    foreach ($c in $missing) {
        Write-Host "     git clone $($c.repo)" -ForegroundColor Cyan
    }
    Write-Host "     # 然后把上面提示的 DSH_CHAIN_* 变量指到你的 clone 路径" -ForegroundColor Cyan
    Write-Host "     # 详见 README「快速开始 → 第 1/2 步」" -ForegroundColor Cyan
}

# ── 5. 可选的 tokenizer ───────────────────────────────────────────────────
Say ""
Say "5) 真实 tokenizer（可选：设了才精确计数，否则按 bytes/3.80 估算）"
if ($env:DSH_CHAIN_TOKENIZER -and (Test-Path $env:DSH_CHAIN_TOKENIZER)) {
    Ok $env:DSH_CHAIN_TOKENIZER
} else {
    Warn "未设置 —— 度量会用估算（功能不受影响）"
}

# ── 写出 .env.ps1 ─────────────────────────────────────────────────────────
if ($WriteEnv) {
    Say ""
    Say "6) 写出 .env.ps1"
    $lines = @('# 由 bootstrap.ps1 生成 —— 供 `source` 后使用（本文件已 gitignore）')
    if ($py)         { $lines += "`$env:DSH_CHAIN_PYTHON = '$py'" }
    if ($bun)        { $lines += "`$env:DSH_CHAIN_BUN = '$bun'" }
    if ($gameFound)  { $lines += "`$env:BANNERLORD_DIR = '$gameFound'" }
    foreach ($k in $resolved.Keys) { $lines += "`$env:$k = '$($resolved[$k])'" }
    $out = Join-Path $Root '.env.ps1'
    $lines | Out-File -FilePath $out -Encoding utf8
    Ok "已写 $out"
    Warn "★ 该文件可能含本机路径 —— 已在 .gitignore 里，**不要**提交"
}

# ── 跑自测 ────────────────────────────────────────────────────────────────
if (-not $Check -and $py) {
    Say ""
    Say "6) 自测（连不上的上游会被点名，其余照常）"
    Say ("-" * 68)
    & $py (Join-Path $Root 'bl_chain.py') --selftest
    $code = $LASTEXITCODE
    Say ("-" * 68)
    if ($code -eq 0) { Ok "自测通过" } else { Warn "自测返回 $code（看上面哪个上游连不上）" }
}

Say ""
Say "下一步：见 README 的「快速开始」。"
