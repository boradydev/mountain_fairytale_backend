import pytest

from scripts.deploy.install_support_vpn import configuration
from scripts.deploy.network_firewall import rules


def settings() -> dict[str, str]:
    return {
        "LAN_INTERFACE": "eth0", "LAN_SUBNET": "192.168.0.0/24", "API_PORT": "8000",
        "SUPPORT_VPN_ENABLED": "true", "SUPPORT_VPN_PROTOCOL": "sstp",
        "SUPPORT_VPN_HOST": "support.example.com", "SUPPORT_VPN_PORT": "443",
        "SUPPORT_VPN_USERNAME": "test-user", "SUPPORT_VPN_PASSWORD": 'test $secret#"\\ value',
        "SUPPORT_VPN_SUBNET": "10.77.50.0/24", "SUPPORT_VPN_EXPECTED_IP": "10.77.50.11",
        "SUPPORT_VPN_ADMIN_IP": "10.77.50.10",
    }


def test_sstp_routes_only_support_network_and_keeps_credentials_off_command_line():
    values = settings()
    peer, hook = configuration(values)
    assert "nodefaultroute" in peer
    assert "usepeerdns" not in peer
    assert "--cert-warn" not in peer
    assert "--tls-ext" in peer
    assert "--ca-path /etc/ssl/certs" in peer
    assert 'support.example.com"' in peer
    assert "support.example.com:443" not in peer
    assert "--password" not in peer
    assert "--user" not in peer
    assert 'password "test $secret#\\"\\\\ value"' in peer
    assert "ifname support0" in peer
    assert "noipv6" in peer
    assert "route replace 10.77.50.0/24 dev support0 src 10.77.50.11" in hook
    assert '"${PPP_LOCAL:-}" = "10.77.50.11"' in hook


@pytest.mark.parametrize(("key", "value"), [
    ("SUPPORT_VPN_HOST", "https://support.example.com"),
    ("SUPPORT_VPN_HOST", "server; touch /tmp/injected"),
    ("SUPPORT_VPN_PASSWORD", "value\nnodefaultroute"),
    ("SUPPORT_VPN_EXPECTED_IP", "10.77.50.10"),
    ("SUPPORT_VPN_SUBNET", "192.168.0.0/16"),
    ("SUPPORT_VPN_ADMIN_IP", "192.168.0.10"),
    ("SUPPORT_VPN_INTERFACE", "eth0;bad"),
])
def test_invalid_vpn_configuration_is_rejected(key: str, value: str):
    values = settings()
    values[key] = value
    with pytest.raises(ValueError, match="."):
        configuration(values)


def test_firewall_limits_published_api_and_blocks_vpn_lateral_access():
    output = rules(settings())
    assert "--ctstate DNAT --ctdir ORIGINAL --ctorigdstport 8000" in output
    assert "--ctorigdst 0.0.0.0" not in output
    assert "-A MF_API -i eth0 -s 192.168.0.0/24 -j ACCEPT" in output
    assert "-A MF_API -i support0 -s 10.77.50.10/32 -j ACCEPT" in output
    assert "-A MF_API -j DROP" in output
    assert "-A MF_FORWARD -i support0 -j DROP" in output
    assert "-s 10.77.50.10/32 -p tcp --dport 22 -j ACCEPT" in output
    assert "-s 10.77.50.0/24" not in output


def test_disabled_vpn_does_not_allow_admin_and_never_changes_default_policies():
    values = settings()
    values["SUPPORT_VPN_ENABLED"] = "false"
    output = rules(values)
    assert "10.77.50.10" not in output
    assert "-A MF_FORWARD -i support0 -j DROP" in output
    assert ":INPUT" not in output
    assert ":FORWARD" not in output
