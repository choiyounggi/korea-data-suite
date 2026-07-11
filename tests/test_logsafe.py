from app.core.logsafe import redact


def test_redact_masks_service_key_in_url():
    msg = "Client error '403 Forbidden' for url 'https://apis.data.go.kr/x?LAWD_CD=11680&serviceKey=FAKEKEY123abc&_type=json'"
    out = redact(msg)
    assert "FAKEKEY123abc" not in out
    assert "serviceKey=***" in out
    assert "LAWD_CD=11680" in out  # non-secret params preserved


def test_redact_masks_capitalized_servicekey():
    # KASI uses ServiceKey (capital S); MOLIT uses serviceKey — both must redact
    out = redact("...&ServiceKey=DEADBEEF&_type=json")
    assert "DEADBEEF" not in out
    assert "ServiceKey=***" in out


def test_redact_no_secret_is_unchanged():
    msg = "ConnectError: connection refused"
    assert redact(msg) == msg


def test_redact_json_and_encoded_and_alias_forms():
    assert "SECRET" not in redact('{"serviceKey": "SECRET", "x": 1}')
    assert "SECRET" not in redact("serviceKey%3DSECRET&_type=json")
    assert "SECRET" not in redact("authKey=SECRET&foo=bar")
    assert "SECRET" not in redact("'service_key': 'SECRET'")
