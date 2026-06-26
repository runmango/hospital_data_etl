from src.utils.masking import hmac_sha256, mask_id_card, mask_name, mask_phone


def test_mask_name_single_surname():
    assert mask_name("张三") == "张*"


def test_mask_name_compound_surname():
    assert mask_name("欧阳娜娜") == "欧阳**"


def test_mask_phone():
    assert mask_phone("13812345678") == "138****5678"


def test_mask_phone_invalid():
    assert mask_phone("12345") == "***"


def test_mask_id_card():
    assert mask_id_card("330102199001011234") == "330***********1234"


def test_hmac_stable_and_not_plaintext():
    first = hmac_sha256("patient-1", secret="unit-test-secret")
    second = hmac_sha256("patient-1", secret="unit-test-secret")
    assert first == second
    assert first.startswith("hmac_sha256:")
    assert "patient-1" not in first
