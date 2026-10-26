#!/usr/bin/env bash
# Short end-to-end scenario against a cluster running the platform in namespace infinity
# (kind in CI, minikube locally after `make minikube`):
#   1. bootstrap a deliberately weak champion trained on a small sample, while the full dataset
#      the retrain Job reads goes to MinIO, so the agent's challenger has something to beat;
#   2. post transactions through the backend and check they come back scored;
#   3. publish a drift.detected alert, wait for the agent's approval request;
#   4. approve through the backend and check that @champion moved and fastapi-ml serves it.
#
# Needs kubectl (pointed at the cluster), curl and jq.
#
# Environment overrides:
#   NAMESPACE (infinity)  PIPELINES_IMAGE (ghcr.io/toubani12/infinity-mlops/pipelines:latest)
#   TRANSACTIONS (20)  ROLLOUT_TIMEOUT (300s)  STEP_TIMEOUT (300 seconds)  RUN_TIMEOUT (900 seconds)
#   BACKEND_PORT (18080)  INFERENCE_PORT (18000)  MLFLOW_PORT (15000)
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
namespace=${NAMESPACE:-infinity}
pipelines_image=${PIPELINES_IMAGE:-ghcr.io/toubani12/infinity-mlops/pipelines:latest}
transactions=${TRANSACTIONS:-20}
rollout_timeout=${ROLLOUT_TIMEOUT:-300s}
step_timeout=${STEP_TIMEOUT:-300}
run_timeout=${RUN_TIMEOUT:-900}
backend_port=${BACKEND_PORT:-18080}
inference_port=${INFERENCE_PORT:-18000}
mlflow_port=${MLFLOW_PORT:-15000}
model_name=fraud-xgb
bootstrap_job=e2e-bootstrap-champion

backend="http://127.0.0.1:$backend_port"
inference="http://127.0.0.1:$inference_port"
mlflow="http://127.0.0.1:$mlflow_port"
forwards=()
token=""
report_id=""
run=""

log() { printf '\n==> %s\n' "$*"; }
fail() { printf '\nFAILED: %s\n' "$*" >&2; exit 1; }
k() { kubectl -n "$namespace" "$@"; }

require() {
  for tool in "$@"; do
    command -v "$tool" > /dev/null || fail "missing required tool: $tool"
  done
}

new_uuid() {
  if command -v uuidgen > /dev/null; then uuidgen | tr '[:upper:]' '[:lower:]'; else cat /proc/sys/kernel/random/uuid; fi
}

# Runs "$@" every 3 s until it succeeds or $1 seconds have passed.
retry_for() {
  local seconds=$1 description=$2
  shift 2
  local deadline=$((SECONDS + seconds))
  until "$@" > /dev/null 2>&1; do
    [ "$SECONDS" -lt "$deadline" ] || fail "timed out after ${seconds}s: $description"
    sleep 3
  done
}

cleanup() {
  for pid in ${forwards[@]+"${forwards[@]}"}; do kill "$pid" 2> /dev/null || true; done
}
trap cleanup EXIT

port_forward() {
  local service=$1 local_port=$2 remote_port=$3
  k port-forward "svc/$service" "$local_port:$remote_port" > /dev/null 2>&1 &
  forwards+=("$!")
}

api() {
  local method=$1 path=$2 body=${3:-}
  local args=(-fsS -X "$method" -H "Authorization: Bearer $token")
  if [ -n "$body" ]; then args+=(-H 'Content-Type: application/json' -d "$body"); fi
  curl "${args[@]}" "$backend$path"
}

wait_for_platform() {
  log "waiting for the platform in namespace $namespace"
  for sts in kafka postgres minio; do
    k rollout status "statefulset/$sts" --timeout "$rollout_timeout"
  done
  # The init Jobs delete themselves 10 minutes after they finish.
  for job in kafka-topics minio-buckets; do
    if k get "job/$job" > /dev/null 2>&1; then
      k wait --for=condition=complete "job/$job" --timeout "$rollout_timeout"
    fi
  done
  for deployment in mlflow backend-spring fastapi-ml agents-langgraph; do
    k rollout status "deployment/$deployment" --timeout "$rollout_timeout"
  done
}

bootstrap_job_manifest() {
  cat <<EOF
apiVersion: batch/v1
kind: Job
metadata:
  name: $bootstrap_job
  labels:
    app.kubernetes.io/part-of: infinity-mlops
    app.kubernetes.io/name: pipelines
    app.kubernetes.io/component: bootstrap
spec:
  backoffLimit: 0
  ttlSecondsAfterFinished: 3600
  template:
    metadata:
      labels:
        app.kubernetes.io/part-of: infinity-mlops
        app.kubernetes.io/name: pipelines
        app.kubernetes.io/component: bootstrap
    spec:
      restartPolicy: Never
      containers:
        - name: bootstrap
          image: $pipelines_image
          imagePullPolicy: IfNotPresent
          command: ["sh", "-c"]
          # registry.promote also points @champion at the weak model when an earlier run left a
          # stronger one, which keeps the scenario repeatable on the same cluster.
          args:
            - |
              set -e
              python -m data.synthetic --rows 60000 --fraud-rate 0.01 --seed 42 --out /tmp/full.csv
              python -m data.ingest --src /tmp/full.csv --dest s3://datasets/raw/creditcard.parquet
              python -m data.synthetic --rows 6000 --fraud-rate 0.01 --seed 7 --out /tmp/sample.csv
              python -m training.train --data /tmp/sample.csv --bootstrap-champion
              python -m registry.promote
          envFrom:
            - configMapRef:
                name: platform-config
            - secretRef:
                name: platform-secrets
          resources:
            requests:
              cpu: 500m
              memory: 512Mi
            limits:
              memory: 1536Mi
EOF
}

job_state() {
  k get "job/$1" -o jsonpath='{.status.succeeded}/{.status.failed}'
}

bootstrap_champion() {
  log "bootstrapping a weak champion with $pipelines_image"
  k delete job "$bootstrap_job" --ignore-not-found > /dev/null
  bootstrap_job_manifest | k apply -f -
  local deadline=$((SECONDS + step_timeout)) state
  while :; do
    state=$(job_state "$bootstrap_job")
    case $state in
      1/*) break ;;
      */1) k logs "job/$bootstrap_job" --tail 40 || true; fail "bootstrap job failed" ;;
    esac
    [ "$SECONDS" -lt "$deadline" ] || { k logs "job/$bootstrap_job" --tail 40 || true; fail "bootstrap job still running after ${step_timeout}s"; }
    sleep 5
  done
  k logs "job/$bootstrap_job" --tail 1
}

champion_version() {
  curl -fsS "$mlflow/api/2.0/mlflow/registered-models/alias?name=$model_name&alias=champion" |
    jq -er '.model_version.version'
}

served_version() {
  curl -fsS "$inference/model" | jq -er '.version'
}

served_version_is() {
  [ "$(served_version)" = "$1" ]
}

open_port_forwards() {
  log "port-forwarding backend-spring, fastapi-ml and mlflow"
  port_forward backend-spring "$backend_port" 8080
  port_forward fastapi-ml "$inference_port" 8000
  port_forward mlflow "$mlflow_port" 5000
  retry_for 60 "backend health" curl -fsS "$backend/actuator/health"
  retry_for 60 "fastapi-ml health" curl -fsS "$inference/health"
  retry_for 60 "mlflow health" curl -fsS "$mlflow/health"
}

sign_in() {
  token=$(curl -fsS -X POST -H 'Content-Type: application/json' \
    -d '{"username":"e2e-admin","role":"admin"}' "$backend/api/auth/dev-token" | jq -er '.token') ||
    fail "no dev token: is the backend running with SPRING_PROFILES_ACTIVE=local?"
}

transaction_payload() {
  jq -nc --arg id "$1" --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" --argjson n "$2" '{
    transactionId: $id,
    timestamp: $ts,
    amount: (5 + $n * 3.7),
    features: ([range(1; 29)] | map({key: "v\(.)", value: (((($n * 7 + . * 13) % 17) - 8) / 4)}) | from_entries)
  }'
}

is_scored() {
  api GET "/api/transactions/$1" | jq -e '.fraudScore != null' > /dev/null
}

score_transactions() {
  log "posting $transactions transactions through the backend"
  local ids=() id
  for n in $(seq 1 "$transactions"); do
    id=$(new_uuid)
    api POST /api/transactions "$(transaction_payload "$id" "$n")" > /dev/null
    ids+=("$id")
  done
  for id in "${ids[@]}"; do
    retry_for "$step_timeout" "transaction $id scored" is_scored "$id"
  done
  api GET "/api/transactions/${ids[0]}" | jq -c '{transactionId, fraudScore, isFraud, modelVersion}'
  echo "all $transactions transactions scored"
}

ensure_no_run_waiting() {
  local waiting
  waiting=$(api GET '/api/agent/runs?size=100' | jq -r '[.content[] | select(.status == "AWAITING_APPROVAL" or .status == "RUNNING") | .runId] | join(" ")')
  [ -z "$waiting" ] || fail "agent run(s) $waiting still open; approve or reject them first (one retrain at a time)"
}

publish_drift_alert() {
  report_id=$(new_uuid)
  log "publishing drift.detected $report_id"
  local report
  report=$(jq -c --arg id "$report_id" --arg now "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    '.report_id = $id | .detected_at = $now | del(.model_version, .report_uri)' \
    "$repo_root/libs/contracts/examples/drift.detected.v1.json")
  printf '%s|%s\n' "$report_id" "$report" | k exec -i kafka-0 -- /opt/kafka/bin/kafka-console-producer.sh \
    --bootstrap-server kafka:9092 --topic drift.detected --property parse.key=true --property key.separator='|'
}

agent_run() {
  api GET '/api/agent/runs?size=100' | jq -c --arg id "$report_id" 'first(.content[] | select(.reportId == $id)) // empty'
}

wait_for_run() {
  local wanted=$1 deadline=$((SECONDS + run_timeout)) status=""
  while :; do
    run=$(agent_run || true)
    status=$(jq -r '.status // empty' <<< "${run:-null}")
    case $status in
      "$wanted") return 0 ;;
      FAILED | KEPT_CHAMPION | NOISE | ESCALATED | REJECTED)
        fail "agent run ended as $status: $(jq -r '.lastMessage' <<< "$run")" ;;
    esac
    [ "$SECONDS" -lt "$deadline" ] || fail "no $wanted run after ${run_timeout}s (last status: ${status:-none})"
    sleep 5
  done
}

approve() {
  local run_id
  run_id=$(jq -r '.runId' <<< "$run")
  log "approving run $run_id: challenger v$(jq -r '.challengerVersion' <<< "$run") against champion v$(jq -r '.championVersion' <<< "$run")"
  api POST "/api/agent/runs/$run_id/approve" | jq -c '{runId, status}'
}

main() {
  require kubectl curl jq
  wait_for_platform
  bootstrap_champion
  open_port_forwards
  local baseline
  baseline=$(champion_version) || fail "no $model_name@champion after the bootstrap"
  retry_for "$step_timeout" "fastapi-ml loads a champion" served_version
  echo "champion v$baseline registered, fastapi-ml serves v$(served_version)"

  sign_in
  score_transactions

  ensure_no_run_waiting
  publish_drift_alert
  log "waiting for the agent to retrain and ask for approval"
  wait_for_run AWAITING_APPROVAL
  approve
  wait_for_run PROMOTED

  local promoted champion
  promoted=$(jq -r '.promotedVersion' <<< "$run")
  champion=$(champion_version)
  [ "$champion" = "$promoted" ] || fail "run promoted v$promoted but @champion is v$champion"
  [ "$champion" != "$baseline" ] || fail "@champion did not move from v$baseline"
  retry_for "$step_timeout" "fastapi-ml serves v$champion" served_version_is "$champion"

  log "done: @champion moved from v$baseline to v$champion and fastapi-ml serves it"
}

main "$@"
