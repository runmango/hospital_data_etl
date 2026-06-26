from src.utils.secret_redactor import redact_mapping, redact_text


def test_password_assignment_redacted():
    assert redact_text("PASSWORD=abc123") == "PASSWORD=<redacted>"


def test_yaml_password_redacted():
    assert redact_text("password: abc123") == "password: <redacted>"


def test_authorization_bearer_redacted():
    assert redact_text("Authorization: Bearer abc.def") == "Authorization: Bearer <redacted>"


def test_mapping_sensitive_keys_redacted():
    original = {"password": "abc123", "token": "tok", "nested": {"secret": "s"}}
    safe = redact_mapping(original)
    assert safe["password"] == "<redacted>"
    assert safe["token"] == "<redacted>"
    assert safe["nested"]["secret"] == "<redacted>"
    assert original["password"] == "abc123"


def test_mapping_non_sensitive_preserved():
    safe = redact_mapping({"host": "192.168.0.65", "service_name": "orcl"})
    assert safe["host"] == "192.168.0.65"
    assert safe["service_name"] == "orcl"
