param(
    [string]$Distribution = 'Ubuntu-24.04',
    [switch]$InstallEngine
)

$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$contextPath = Join-Path $projectRoot 'docker\sandbox'

function Invoke-SandboxWsl {
    param([string[]]$CommandArguments)
    & wsl.exe --distribution $Distribution --user root --exec @CommandArguments
    if ($LASTEXITCODE -ne 0) { throw "WSL command failed with exit code $LASTEXITCODE" }
}

if ($InstallEngine) {
    Invoke-SandboxWsl -CommandArguments @('apt-get', 'update')
    Invoke-SandboxWsl -CommandArguments @('env', 'DEBIAN_FRONTEND=noninteractive', 'apt-get', 'install', '--yes', 'docker.io')
}
Invoke-SandboxWsl -CommandArguments @('/usr/sbin/service', 'docker', 'start')

$linuxContext = & wsl.exe --distribution $Distribution --user root --exec wslpath -a $contextPath
if ($LASTEXITCODE -ne 0) { throw 'Could not resolve the sandbox build context in WSL' }
$linuxContext = ($linuxContext -join '').Replace([string][char]0, '').Trim()
Invoke-SandboxWsl -CommandArguments @('/usr/bin/docker', '--host', 'unix:///var/run/docker.sock', 'build', '--tag', 'kavach-sandbox:1', $linuxContext)

$settingsPath = Join-Path $projectRoot 'backend\.env.sandbox'
@(
    'KAVACH_SANDBOX_ENABLED=true'
    "KAVACH_SANDBOX_WSL_DISTRO=$Distribution"
    'KAVACH_SANDBOX_DOCKER_HOST=unix:///var/run/docker.sock'
    'KAVACH_SANDBOX_IMAGE=kavach-sandbox:1'
) | Set-Content -LiteralPath $settingsPath -Encoding ASCII

Write-Output "Sandbox image built. Start the backend from backend/ with:"
Write-Output 'python -m uvicorn app.main:app --env-file .env.sandbox --host 127.0.0.1 --port 8000'
