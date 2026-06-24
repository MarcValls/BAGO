# Activate the working copy as the active BAGO install after fixes are in place.

# Order:
# 1. Fix repl.py indentation (creates .bak before touching anything).
# 2. Verify BagoREPL.run is back.
# 3. Verify system prompt bootstrap test still passes.
# 4. If both pass, promote to all 3 profiles via install-v4.ps1.
# 5. Otherwise, stop and surface the failure.

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repoRoot = 'C:\Program Files\BAGO'
Set-Location $repoRoot

# Step 1: indentation fix.
Write-Host "=== Step 1: fix repl.py indentation ===" -ForegroundColor Cyan
& python "$repoRoot\fix_repl_indent.py"
if ($LASTEXITCODE -ne 0) {
    Write-Error "fix_repl_indent.py failed. Stopping before any promotion."
    exit 1
}

# Step 2: verify run is back.
Write-Host ""
Write-Host "=== Step 2: verify BagoREPL.run ===" -ForegroundColor Cyan
$probe = & python -c "import sys; sys.path.insert(0, r'C:\Program Files\BAGO\.bago\chat'); import repl; print('OK' if hasattr(repl.BagoREPL, 'run') else 'FAIL')"
if ($probe -ne 'OK') {
    Write-Error "BagoREPL.run still missing after fix. Stopping."
    exit 1
}

# Step 3: pytest for system prompt.
Write-Host ""
Write-Host "=== Step 3: pytest system_prompt_bootstrap ===" -ForegroundColor Cyan
& python -m pytest tests/test_system_prompt_bootstrap.py -v
if ($LASTEXITCODE -ne 0) {
    Write-Error "test_system_prompt_bootstrap.py failed. Stopping."
    exit 1
}

# Step 4: smoke test the chat path with a quick import + dummy call.
Write-Host ""
Write-Host "=== Step 4: import-only smoke test ===" -ForegroundColor Cyan
$smoke = & python -c "import sys; sys.path.insert(0, r'C:\Program Files\BAGO\bago_core'); sys.path.insert(0, r'C:\Program Files\BAGO\.bago\chat'); from repl import BagoREPL; from system_prompt import get_system_prompt; r = BagoREPL(provider='ollama-local', model='llama3.2:3b', system_prompt=get_system_prompt(), base_path=r'C:\Program Files\BAGO'); print('run method:', callable(getattr(r, 'run', None)))"
if ($smoke -notlike '*run method: True*') {
    Write-Error "Smoke test failed: $smoke"
    exit 1
}

# Step 5: promote.
Write-Host ""
Write-Host "=== Step 5: promote to all profiles ===" -ForegroundColor Cyan
& powershell -NoProfile -ExecutionPolicy Bypass -File "$repoRoot\promote_all_profiles.ps1"
exit $LASTEXITCODE