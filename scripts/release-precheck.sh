#!/usr/bin/env bash
set -euo pipefail

FULL=0
if [[ "${1:-}" == "--full" ]]; then
  FULL=1
fi

step() {
  local title="$1"
  shift
  echo
  echo "==> ${title}"
  echo "    $*"
  "$@"
}

echo "OpenClaw Skill Deps release precheck"
echo "Workspace: $(pwd)"

step "Validate hints schema" python -m openclaw_skill_deps.cli --skills-dir clawhub-skill --validate-hints
step "Validate plugin contracts" python -m openclaw_skill_deps.cli --skills-dir clawhub-skill --validate-plugins
step "Verify hints migration clean" python scripts/migrate_hints_schema.py --in openclaw_skill_deps/data/hints.yaml --check
step "Check skill wrapper help" python clawhub-skill/openclaw-skill-deps/scripts/openclaw-skill-deps.py --help

if [[ "${FULL}" -eq 1 ]]; then
  step "Run unit tests" python -m pytest -q -p no:cacheprovider
  step "Run mypy" python -m mypy openclaw_skill_deps/
fi

echo
echo "Precheck finished successfully."
echo "Suggested publish command:"
echo "  clawhub publish --skill clawhub-skill/openclaw-skill-deps --slug openclaw-skill-deps --version <x.y.z> --verbose"
