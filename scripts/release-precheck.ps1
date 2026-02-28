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
    if ($LASTEXITCODE -ne 0) {
        throw "Step failed with exit code ${LASTEXITCODE}: $Title"
    }
}

Write-Host "Skill Deps Doctor release precheck" -ForegroundColor Green
Write-Host "Workspace: $(Get-Location)"

Invoke-Step "Validate hints schema" "python -m skill_deps_doctor.cli --skills-dir clawhub-skill --validate-hints"
Invoke-Step "Validate plugin contracts" "python -m skill_deps_doctor.cli --skills-dir clawhub-skill --validate-plugins"
Invoke-Step "Verify hints migration clean" "python scripts/migrate_hints_schema.py --in skill_deps_doctor/data/hints.yaml --check"
Invoke-Step "Check skill wrapper help" "python clawhub-skill/skill-deps-doctor/scripts/skill-deps-doctor.py --help"

if ($Full) {
    Invoke-Step "Run unit tests" "python -m pytest -q -p no:cacheprovider"
    Invoke-Step "Run mypy" "python -m mypy skill_deps_doctor/"
}

Write-Host ""
Write-Host "Precheck finished successfully." -ForegroundColor Green
Write-Host "Suggested publish command:"
Write-Host "  clawhub publish --skill clawhub-skill/skill-deps-doctor --slug skill-deps-doctor --version <x.y.z> --verbose"
