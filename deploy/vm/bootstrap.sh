#!/usr/bin/env bash
# Runs ON the VM (Ubuntu 22.04/24.04 or Debian 12/13, x86_64 or aarch64). Idempotent.
# - installs k3s (with its bundled Traefik ingress, which owns ports 80/443 on the node)
set -euo pipefail

# Debian minimal images have no sudo; as root just run commands directly
if ! command -v sudo >/dev/null 2>&1; then
  if [[ "$(id -u)" == "0" ]]; then
    apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq sudo >/dev/null
  else
    echo "sudo missing and not root"; exit 1
  fi
fi

echo "==> base packages"
if ! command -v curl >/dev/null 2>&1 || ! command -v rsync >/dev/null 2>&1; then
  sudo apt-get update -qq && sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq curl rsync ca-certificates >/dev/null
fi

K3S_EXEC="--write-kubeconfig-mode 644"
if ! command -v k3s >/dev/null 2>&1; then
  echo "==> installing k3s"
  curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="${K3S_EXEC}" sh -
elif grep -qE "^[[:space:]]*'(--disable=)?traefik'" /etc/systemd/system/k3s.service 2>/dev/null; then
  echo "==> k3s installed without traefik; re-running installer to enable it (keeps data)"
  # --disable leaves a .skip marker that keeps the bundled chart from being applied
  sudo rm -f /var/lib/rancher/k3s/server/manifests/traefik.yaml.skip
  curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="${K3S_EXEC}" sh -
else
  echo "==> k3s already installed"
fi

echo "==> waiting for node to be Ready"
for _ in $(seq 1 60); do
  if sudo k3s kubectl get nodes 2>/dev/null | grep -q ' Ready'; then break; fi
  sleep 2
done
sudo k3s kubectl get nodes

# kubectl convenience for the login user
if ! grep -q KUBECONFIG ~/.bashrc 2>/dev/null; then
  echo 'export KUBECONFIG=/etc/rancher/k3s/k3s.yaml' >> ~/.bashrc
fi
echo "==> bootstrap done"
