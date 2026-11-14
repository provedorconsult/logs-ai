import importlib.util
from pathlib import Path
from unittest.mock import Mock

import pytest

spec = importlib.util.spec_from_file_location(
    "readonly_monitor", Path("scripts/mikrotik/readonly_monitor.py")
)
monitor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(monitor)


def test_unknown_host_key_cannot_receive_password():
    transport = Mock()
    transport.get_remote_server_key.return_value.asbytes.return_value = b"synthetic-host-key"
    with pytest.raises(ValueError, match="host key"):
        monitor.authenticate(transport, "SHA256:untrusted", "synthetic-user", "synthetic-password")
    transport.auth_password.assert_not_called()


def test_confirmed_host_key_allows_only_password_auth_without_fallback():
    transport = Mock()
    key = transport.get_remote_server_key.return_value
    key.asbytes.return_value = b"synthetic-host-key"
    monitor.authenticate(
        transport, monitor.fingerprint(key), "synthetic-user", "synthetic-password"
    )
    transport.auth_password.assert_called_once_with(
        "synthetic-user", "synthetic-password", fallback=False
    )
