param(
    [switch]$Full
)

$ErrorActionPreference = "Stop"

function Invoke-Step {
    param(
        [string]$Title,
        [string]$Command
    )
    Write-Host ""
    Write-Host "==> $Title" -ForegroundColor Cyan
    Write-Host "    $Command"
    Invoke-Expression $Command
}

Write-Host "OpenClaw Skill Deps release precheck" -ForegroundColor Green
Write-Host "Workspace: $(Get-Location)"

Invoke-Step "Validate hints schema" "python -m openclaw_skill_deps.cli --skills-dir clawhub-skill --validate-hints"
Invoke-Step "Validate plugin contracts" "python -m openclaw_skill_deps.cli --skills-dir clawhub-skill --validate-plugins"
Invoke-Step "Verify hints migration clean" "python scripts/migrate_hints_schema.py --in openclaw_skill_deps/data/hints.yaml --check"
Invoke-Step "Check skill wrapper help" "python clawhub-skill/openclaw-skill-deps/scripts/openclaw-skill-deps.py --help"

if ($Full) {
    Invoke-Step "Run unit tests" "python -m pytest -q -p no:cacheprovider"
    Invoke-Step "Run mypy" "python -m mypy openclaw_skill_deps/"
}

Write-Host ""
Write-Host "Precheck finished successfully." -ForegroundColor Green
Write-Host "Suggested publish command:"
Write-Host "  clawhub publish --skill clawhub-skill/openclaw-skill-deps --slug openclaw-skill-deps --version <x.y.z> --verbose"
