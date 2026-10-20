# 研究组信息管理系统 —— 一键部署/更新到远程服务器（模板）
#
# 用法（在仓库根目录执行）:
#   powershell -ExecutionPolicy Bypass -File scripts\update.ps1            # 构建前端 + 上传 + 重启
#   powershell -ExecutionPolicy Bypass -File scripts\update.ps1 -SkipBuild  # 只改了后端时用
#
# 通过环境变量配置目标服务器（运行前设置，或写入你的 PowerShell profile）：
#   $env:LAB_REMOTE_HOST = "your.server.ip.or.domain"
#   $env:LAB_REMOTE_USER = "deploy"              # 远程 SSH 用户（需有写入权限）
#   $env:LAB_REMOTE_PATH = "/opt/lab_manage"     # 服务器上的应用目录
#   $env:LAB_SSH_KEY      = "$env:USERPROFILE\.ssh\id_ed25519"  # SSH 私钥路径
#
# 服务器侧还需执行 scripts/deploy_server.sh（本脚本会自动通过 SSH 调用）。
param([switch]$SkipBuild)

$ErrorActionPreference = "Stop"

$RemoteHost = $env:LAB_REMOTE_HOST
$RemoteUser = $env:LAB_REMOTE_USER
$RemotePath = $env:LAB_REMOTE_PATH
$SshKey     = $env:LAB_SSH_KEY

if (-not $RemoteHost -or -not $RemoteUser -or -not $RemotePath -or -not $SshKey) {
    Write-Error "请先设置环境变量 LAB_REMOTE_HOST / LAB_REMOTE_USER / LAB_REMOTE_PATH / LAB_SSH_KEY。参见脚本顶部说明。"
    exit 1
}

$Target = "$RemoteUser@$RemoteHost"

if (!$SkipBuild) {
    Write-Output "===== 构建前端 ====="
    Push-Location "$PSScriptRoot\..\frontend"
    npm run build
    Pop-Location
}

Write-Output "===== 上传后端代码 ====="
scp -i $SshKey -r "$PSScriptRoot\..\backend\app" "$PSScriptRoot\..\backend\scripts" "$PSScriptRoot\..\backend\requirements.txt" "${Target}:${RemotePath}/backend/"

Write-Output "===== 上传前端产物 ====="
scp -i $SshKey -r "$PSScriptRoot\..\frontend\dist" "${Target}:${RemotePath}/frontend/"

Write-Output "===== 上传部署脚本 ====="
scp -i $SshKey "$PSScriptRoot\deploy_server.sh" "$PSScriptRoot\im.service" "${Target}:${RemotePath}/scripts/"

Write-Output "===== 服务器安装依赖并重启服务 ====="
ssh -i $SshKey $Target "bash ${RemotePath}/scripts/deploy_server.sh"
