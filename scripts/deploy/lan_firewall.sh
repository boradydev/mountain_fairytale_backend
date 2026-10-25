#!/bin/sh
# Environment comes from the systemd unit, not a shell-sourced secrets file.
set -eu
test "$(id -u)" -eq 0
cd /opt/mountain-fairytale
exec /usr/bin/python3 -m scripts.deploy.network_firewall
