#!/usr/bin/env bash
# Run the autograder on your machine, exactly like CI: scripted model, phase 1, restart, phase 2.
#   bash scripts/local_eval.sh            full run (builds two Docker images; first time takes a few minutes)
set -uo pipefail
cd "$(dirname "$0")/.."
RED='\033[0;31m'; GREEN='\033[0;32m'; BLUE='\033[0;34m'; NC='\033[0m'
info() { echo -e "${BLUE}[eval]${NC} $*"; }
CONTAINER="eval-local-$$"; VOLUME="eval-local-data-$$"; PORT="${EVAL_PORT:-8000}"
cleanup() { docker rm -f "$CONTAINER" >/dev/null 2>&1 || true; docker volume rm "$VOLUME" >/dev/null 2>&1 || true; }
trap cleanup EXIT

info "building the app image (runner) and the test image"
docker build -q --target runner -t eval-app-local . >/dev/null || { echo -e "${RED}[eval]${NC} app image failed to build"; exit 1; }
docker build -q --target test -t eval-test-local . >/dev/null || { echo -e "${RED}[eval]${NC} test image failed to build"; exit 1; }

rm -rf results && mkdir -p results
docker volume create "$VOLUME" >/dev/null
docker run -d --name "$CONTAINER" --memory 1g --cpus 1 -p "$PORT:8000" -v "$VOLUME:/data" eval-app-local >/dev/null

wait_health() {
    for _ in $(seq 1 60); do curl -sf "http://localhost:$PORT/health" >/dev/null && return 0; sleep 2; done
    echo -e "${RED}[eval]${NC} the app did not become healthy. Its log:"; docker logs --tail 40 "$CONTAINER"; return 1
}
run_tests() {  # $1 = phase marker
    docker run --rm --network host -e BASE_URL="http://localhost:$PORT" -e ASSESSMENT_ID=agentic-ai-extension \
        -v "$PWD/results:/app/results" eval-test-local pytest tests/ -m "$1" --tb=short -q
}
wait_health || exit 1
info "phase 1: before the restart"; run_tests phase1
info "restarting the container (same data volume)"; docker restart "$CONTAINER" >/dev/null; wait_health || exit 1
info "phase 2: after the restart"; run_tests phase2

echo
python3 - <<'PY'
import json
s = json.load(open("results/summary.json"))
print(f"\n{s['earnedPoints']}/{s['totalPoints']} points\n")
for c in s["checks"]:
    print(("  PASS " if c["passed"] else "  FAIL "), c["points"], c["id"], "-", c["name"])
PY
echo -e "\n(the app's log is in 'docker logs'; it is removed with the container. Re-run after fixing.)"
