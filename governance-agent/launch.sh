#!/usr/bin/env bash
# Resumable launch: model pick -> environment -> CMA agent (Worker) -> governed session.
# Each step reads IDS.env first and skips objects that already exist.
set -euo pipefail
cd "$(dirname "$0")"
[ -f .env ] && { set -a; source .env; set +a; }
touch IDS.env; set -a; source IDS.env; set +a

# 0. preflight: policy evals and boundary attacks must pass before anything is created
python3 evals/run_evals.py >/dev/null || { echo "evals failing — not launching"; exit 1; }
python3 attacks/run_attacks.py >/dev/null || { echo "boundary attacks OPEN — not launching"; exit 1; }
python3 -c "import json,sys; sys.path.insert(0,'.'); from governor.attest import check_agent, check_environment; \
p=check_agent(json.load(open('agent.json')))+check_environment(json.load(open('environment.json'))); \
sys.exit('attestation failed: '+'; '.join(p) if p else 0)"
echo "✅ preflight: evals 12/12 · attacks all blocked · local config attested"
: "${ANTHROPIC_API_KEY:?put ANTHROPIC_API_KEY in governance-agent/.env or export it}"
BASE=https://api.anthropic.com/v1
H=(-H "x-api-key: $ANTHROPIC_API_KEY" -H "anthropic-version: 2023-06-01"
   -H "anthropic-beta: managed-agents-2026-04-01" -H "content-type: application/json")
get() { python3 -c "import json,sys; d=json.JSONDecoder(strict=False).decode(open('/tmp/gov_resp.json').read()); print(d$1)"; }

# 1. model: newest Opus-class unless MODEL is set
if [ -z "${MODEL:-}" ]; then
  curl -sS --fail-with-body "$BASE/models" "${H[@]:0:4}" -o /tmp/gov_resp.json
  MODEL=$(python3 -c "import json; ids=[m['id'] for m in json.load(open('/tmp/gov_resp.json'))['data'] if 'opus' in m['id']]; print(ids[0] if ids else 'claude-opus-5-5')")
  echo "MODEL=$MODEL" >> IDS.env
fi
echo "model  $MODEL"

# 2. environment
if [ -z "${ENV_ID:-}" ]; then
  curl -sS --fail-with-body "$BASE/environments" "${H[@]}" -d @environment.json -o /tmp/gov_resp.json
  ENV_ID=$(get "['id']"); echo "ENV_ID=$ENV_ID" >> IDS.env
fi
echo "✅ 📦 environment $ENV_ID"

# 3. agent (Worker: custom tool propose_action only)
if [ -z "${AGENT_ID:-}" ]; then
  python3 -c "import json; a=json.load(open('agent.json')); a['model']='$MODEL'; json.dump(a,open('/tmp/gov_agent.json','w'))"
  curl -sS --fail-with-body "$BASE/agents" "${H[@]}" -d @/tmp/gov_agent.json -o /tmp/gov_resp.json
  AGENT_ID=$(get "['id']"); AGENT_VERSION=$(get "['version']")
  printf 'AGENT_ID=%s\nAGENT_VERSION=%s\n' "$AGENT_ID" "$AGENT_VERSION" >> IDS.env
fi
echo "✅ 🤖 agent $AGENT_ID (v$AGENT_VERSION, $MODEL)"
echo "   https://platform.claude.com/workspaces/default/agents/$AGENT_ID"

# 4. governed session: Worker proposals -> Governor -> Executor -> audit log
python3 driver.py live
