#!/usr/bin/env bash
# Runs on your Mac. Builds the API image for the VM's CPU arch, ships repo + image
# to the VM, bootstraps k3s if needed, applies the kustomize manifests, waits for rollout.
#
#   deploy/vm/deploy.sh <vm-public-ip> [ssh-user]
#
# Works on any Ubuntu 22.04/24.04 or Debian 12/13 VM (Hetzner, OVH, Scaleway, DigitalOcean, Oracle, ...).
# Requires: docker (buildx), rsync, ssh access to the VM, k8s/.env filled in.
#
# TLS (optional): point a DNS A record at the VM, then
#   API_HOST=api.example.com ACME_EMAIL=you@example.com deploy/vm/deploy.sh <ip>
# cert-manager requests a Let's Encrypt certificate and HTTP is redirected to HTTPS.
# Without API_HOST the API stays on plain http://<ip>/.
#
# Pangolin (alternative to TLS above): set PANGOLIN_ENDPOINT / NEWT_ID / NEWT_SECRET in k8s/.env
# (from Pangolin -> Sites -> Add Site) and the deploy runs the Newt connector in the cluster. Then
# add a Resource in Pangolin targeting http api.bubblemaps-test.svc.cluster.local:80.
set -euo pipefail

VM="${1:?usage: deploy.sh <vm-ip> [ssh-user]}"
USER_="${2:-root}"
HOST="${USER_}@${VM}"
REMOTE_DIR="~/bubblemaps-test"
NS=bubblemaps-test
# Each deployment must consume with its own Kafka group, or Confluent splits the partitions
# between it and your laptop cluster. Base name comes from the schema; we suffix it on the VM copy.
KAFKA_GROUP_SUFFIX="${KAFKA_GROUP_SUFFIX:-vm}"
API_HOST="${API_HOST:-}"
ACME_EMAIL="${ACME_EMAIL:-}"
if [[ -n "${API_HOST}" && -z "${ACME_EMAIL}" ]]; then echo "ACME_EMAIL is required with API_HOST"; exit 1; fi
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

[[ -f "${ROOT}/k8s/.env" ]] || { echo "k8s/.env missing (copy k8s/.env.example)"; exit 1; }

echo "==> detecting VM architecture (and installing rsync if missing)"
ssh "${HOST}" 'command -v rsync >/dev/null || { S=$(command -v sudo || true); $S apt-get update -qq && DEBIAN_FRONTEND=noninteractive $S apt-get install -y -qq rsync curl >/dev/null; }'
case "$(ssh "${HOST}" uname -m)" in
  x86_64)          PLATFORM=linux/amd64 ;;
  aarch64|arm64)   PLATFORM=linux/arm64 ;;
  *) echo "unsupported arch"; exit 1 ;;
esac
echo "    ${PLATFORM}"

echo "==> building shib-api:dev for ${PLATFORM}"
docker buildx build --platform "${PLATFORM}" -t shib-api:dev \
  -o type=docker,dest=/tmp/shib-api.tar "${ROOT}/api"

echo "==> syncing repo to ${HOST}:${REMOTE_DIR}"
rsync -az --delete \
  --exclude '.git' --exclude '.context' --exclude '__pycache__' --exclude '.venv' \
  "${ROOT}/" "${HOST}:${REMOTE_DIR}/"
rsync -az /tmp/shib-api.tar "${HOST}:/tmp/shib-api.tar"

# With Pangolin/Newt publishing the API, nothing but ssh needs to be reachable on the VM.
if grep -qE '^NEWT_ID=.+' "${ROOT}/k8s/.env" && ! grep -qE '^NEWT_ID=changeme' "${ROOT}/k8s/.env"; then
  PUBLIC_PORTS="22"
else
  PUBLIC_PORTS="22, 80, 443"
fi
echo "==> bootstrap (no-op if already done; public ports: ${PUBLIC_PORTS})"
ssh "${HOST}" "PUBLIC_PORTS='${PUBLIC_PORTS}' bash ${REMOTE_DIR}/deploy/vm/bootstrap.sh"

echo "==> importing image + applying manifests (kafka group suffix: ${KAFKA_GROUP_SUFFIX})"
ssh "${HOST}" bash <<REMOTE
set -euo pipefail
sudo k3s ctr images import /tmp/shib-api.tar >/dev/null
cd ${REMOTE_DIR}
sed -i -E "s/(kafka_group_name *= *'[^']*)'/\\1-${KAFKA_GROUP_SUFFIX}'/" clickhouse/initdb/schema.sql
grep -o "kafka_group_name *= *'[^']*'" clickhouse/initdb/schema.sql
sudo k3s kubectl apply -k k8s/
sudo k3s kubectl -n ${NS} rollout status statefulset/clickhouse --timeout=300s
# re-apply the schema (idempotent) so new tables/views land without a pod restart
sudo k3s kubectl -n ${NS} exec -i clickhouse-0 -- sh -c 'clickhouse-client --password "\$CLICKHOUSE_PASSWORD" --multiquery' < clickhouse/initdb/schema.sql
sudo k3s kubectl -n ${NS} rollout restart deployment/api
sudo k3s kubectl -n ${NS} rollout status deployment/api --timeout=180s
if grep -qE '^NEWT_ID=.+' k8s/.env && ! grep -qE '^NEWT_ID=changeme' k8s/.env; then
  echo "newt (Pangolin connector) enabled"
  sudo k3s kubectl apply -k k8s/newt/
  sudo k3s kubectl -n ${NS} rollout status deployment/newt --timeout=120s
  sudo k3s kubectl -n ${NS} logs deployment/newt --tail=5
fi
if [[ -n "${API_HOST}" ]]; then
  sed -i "s/__API_HOST__/${API_HOST}/g; s/__ACME_EMAIL__/${ACME_EMAIL}/g" k8s/tls/*.yaml
  sudo k3s kubectl apply -f k8s/tls/
  echo "waiting for certificate (Let's Encrypt HTTP-01 on port 80)..."
  sudo k3s kubectl -n ${NS} wait --for=condition=Ready certificate/api-tls --timeout=180s || \
    sudo k3s kubectl -n ${NS} describe certificate api-tls | tail -15
fi
sudo k3s kubectl -n ${NS} get pods,svc,ingress,pvc
REMOTE

echo
if [[ -n "${API_HOST}" ]]; then echo "==> API: https://${API_HOST}/docs"; else echo "==> API: http://${VM}/docs"; fi
