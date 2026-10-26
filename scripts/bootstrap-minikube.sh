#!/usr/bin/env bash
# Start a minikube cluster sized for a 16 GB laptop, build the images inside it and deploy the minikube overlay.
#
# Environment overrides:
#   MINIKUBE_PROFILE (infinity)  MINIKUBE_MEMORY (8192)  MINIKUBE_CPUS (4)  MINIKUBE_DISK (30g)
#   NEXT_PUBLIC_API_BASE_URL (http://localhost:8080)  SKIP_BUILD (0)  ROLLOUT_TIMEOUT (300s)
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
overlay="$repo_root/k8s/overlays/minikube"
namespace=infinity
registry=ghcr.io/toubani12/infinity-mlops

profile=${MINIKUBE_PROFILE:-infinity}
memory=${MINIKUBE_MEMORY:-8192}
cpus=${MINIKUBE_CPUS:-4}
disk=${MINIKUBE_DISK:-30g}
api_base_url=${NEXT_PUBLIC_API_BASE_URL:-http://localhost:8080}
rollout_timeout=${ROLLOUT_TIMEOUT:-300s}

# name:build context relative to the repository root. Plain arrays only: macOS ships bash 3.2.
images=(
  mlflow:infra/mlflow
  backend-spring:apps/backend-spring
  fastapi-ml:apps/fastapi-ml
  frontend-next:apps/frontend-next
  agents-langgraph:services/agents-langgraph
  drift-monitor:services/drift-monitor
  pipelines:pipelines
)
built=()

log() { printf '\n==> %s\n' "$*"; }

require() {
  for tool in "$@"; do
    command -v "$tool" > /dev/null || { echo "missing required tool: $tool" >&2; exit 1; }
  done
}

start_cluster() {
  if minikube -p "$profile" status > /dev/null 2>&1; then
    log "minikube profile $profile is already running"
  else
    log "starting minikube profile $profile (${memory} MB, ${cpus} CPUs)"
    minikube start -p "$profile" --memory "$memory" --cpus "$cpus" --disk-size "$disk"
  fi
  minikube -p "$profile" addons enable metrics-server
  kubectl config use-context "$profile" > /dev/null
}

ensure_secrets() {
  if [ ! -f "$overlay/secrets.env" ]; then
    log "creating $overlay/secrets.env from the example; edit it to change credentials"
    cp "$overlay/secrets.env.example" "$overlay/secrets.env"
  fi
}

build_images() {
  if [ "${SKIP_BUILD:-0}" = 1 ]; then
    log "SKIP_BUILD=1, using images already present in minikube"
    for spec in "${images[@]}"; do built+=("${spec%%:*}"); done
    return
  fi
  for spec in "${images[@]}"; do
    name=${spec%%:*}
    context="$repo_root/${spec#*:}"
    if [ ! -f "$context/Dockerfile" ]; then
      echo "skip $name: no Dockerfile in ${spec#*:} yet"
      continue
    fi
    log "building $registry/$name:latest"
    if [ "$name" = frontend-next ]; then
      minikube -p "$profile" image build -t "$registry/$name:latest" \
        --build-opt="build-arg=NEXT_PUBLIC_API_BASE_URL=$api_base_url" "$context"
    else
      minikube -p "$profile" image build -t "$registry/$name:latest" "$context"
    fi
    built+=("$name")
  done
}

deploy() {
  log "applying the minikube overlay"
  # Finished init Jobs are immutable; deleting them lets apply recreate them with the current spec.
  kubectl -n "$namespace" delete job kafka-topics minio-buckets --ignore-not-found > /dev/null 2>&1 || true
  kubectl apply -k "$overlay"
}

wait_for_rollouts() {
  log "waiting for the infrastructure"
  for sts in kafka postgres minio; do
    kubectl -n "$namespace" rollout status "statefulset/$sts" --timeout "$rollout_timeout"
  done
  kubectl -n "$namespace" wait --for=condition=complete job/kafka-topics job/minio-buckets --timeout "$rollout_timeout"

  for name in ${built[@]+"${built[@]}"} prometheus grafana; do
    if kubectl -n "$namespace" get "deployment/$name" > /dev/null 2>&1; then
      kubectl -n "$namespace" rollout status "deployment/$name" --timeout "$rollout_timeout"
    fi
  done
}

print_access() {
  local ip
  ip=$(minikube -p "$profile" ip)
  cat <<EOF

Deployed to namespace $namespace.

  kubectl -n $namespace get pods
  kubectl -n $namespace port-forward svc/backend-spring 8080:8080
  kubectl -n $namespace port-forward svc/frontend-next 3000:3000
  kubectl -n $namespace port-forward svc/mlflow 5000:5000
  kubectl -n $namespace port-forward svc/grafana 3001:3000

NodePorts (Linux, or macOS with "minikube -p $profile service --url"):
  backend-spring  http://$ip:30080
  frontend-next   http://$ip:30300
  grafana         http://$ip:30301
EOF
}

require minikube kubectl
start_cluster
ensure_secrets
build_images
deploy
wait_for_rollouts
print_access
