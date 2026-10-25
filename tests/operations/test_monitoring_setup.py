from scripts.deploy.init_monitoring_env import add_settings
from scripts.deploy.network_firewall import rules


def test_monitoring_defaults_preserve_existing_secrets_and_are_idempotent(tmp_path, capsys):
    path = tmp_path / ".env"
    path.write_text("API_IMAGE=existing\nGLITCHTIP_SECRET_KEY=keep-this-secret", encoding="utf-8")
    add_settings(path, "192.168.0.25", "10.77.50.11")
    first = path.read_text(encoding="utf-8")
    add_settings(path, "192.168.0.25", "10.77.50.11")
    assert path.read_text(encoding="utf-8") == first
    assert "GLITCHTIP_SECRET_KEY=keep-this-secret\n" in first
    assert 'GLITCHTIP_BACKUP_KEEP="3"' in first
    assert 'GLITCHTIP_RETENTION_DAYS="30"' in first
    assert "keep-this-secret" not in capsys.readouterr().out


def test_monitoring_port_is_protected_on_every_interface():
    environment = {
        "LAN_INTERFACE": "eth0", "LAN_SUBNET": "192.168.0.0/24", "API_PORT": "8000",
        "SUPPORT_VPN_ENABLED": "true", "SUPPORT_VPN_ADMIN_IP": "10.77.50.10",
        "GLITCHTIP_ENABLED": "true", "GLITCHTIP_PORT": "8080",
    }
    result = rules(environment)
    assert "--ctorigdstport 8080 -j MF_API" in result
    assert "-A MF_API -i support0 -s 10.77.50.10/32 -j ACCEPT" in result
    assert "-A MF_API -j DROP" in result
    environment["GLITCHTIP_ENABLED"] = "false"
    assert "--ctorigdstport 8080" not in rules(environment)
