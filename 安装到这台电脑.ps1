$ErrorActionPreference = "Stop"
$installer = Join-Path $PSScriptRoot "安装工作流.py"
$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
$pyCommand = Get-Command py -ErrorAction SilentlyContinue
if ($pythonCommand) {
    & $pythonCommand.Source $installer install
} elseif ($pyCommand) {
    & $pyCommand.Source -3 $installer install
} else {
    Write-Error "需要 Python 3.10 或更新版本。也可以在 Codex 中使用启动指南里的完整指令。"
    exit 1
}
exit $LASTEXITCODE
