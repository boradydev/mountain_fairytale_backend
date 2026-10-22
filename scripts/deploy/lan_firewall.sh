#!/bin/sh
# Environment comes from the systemd unit, not a shell-sourced secrets file.
set -eu
test "$(id -u)" -eq 0
: "${LAN_INTERFACE:?Set LAN_INTERFACE}"
: "${LAN_SUBNET:?Set LAN_SUBNET}"
: "${API_BIND_HOST:?Set API_BIND_HOST}"
: "${API_PORT:?Set API_PORT}"
# Only forwarded connections to this published API port are affected.
# SSH and connections originating inside the VM are not affected.
if ! iptables -w -C DOCKER-USER -i "$LAN_INTERFACE" -p tcp \
    -m conntrack --ctorigdst "$API_BIND_HOST" --ctorigdstport "$API_PORT" \
    ! -s "$LAN_SUBNET" -j DROP 2>/dev/null; then
    iptables -w -I DOCKER-USER 1 -i "$LAN_INTERFACE" -p tcp \
        -m conntrack --ctorigdst "$API_BIND_HOST" --ctorigdstport "$API_PORT" \
        ! -s "$LAN_SUBNET" -j DROP
fi
