#!/bin/sh
# Install only the local, reviewed deployment service. No GitHub credentials are needed.
set -eu
test "$(id -u)" -eq 0
command -v git >/dev/null
project=/opt/mountain-fairytale
test -f "$project/.env"
test -f "$project/backup.env"
test -f "$project/scripts/deploy/pull_deploy.py"
test -f "$project/scripts/deploy/release_manifest.py"
install -d -m 0700 "$project/.deploy"
install -m 0644 "$project/deploy/mountain-fairytale.service" /etc/systemd/system/
install -m 0644 "$project/deploy/mountain-fairytale-deploy.service" /etc/systemd/system/
install -m 0644 "$project/deploy/mountain-fairytale-deploy.timer" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now mountain-fairytale-deploy.timer
echo 'Deployment timer enabled; requests are read from the public deployment branch.'
