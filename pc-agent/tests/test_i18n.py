"""i18n 단위 테스트."""

import pytest
import utils.i18n as i18n
from utils.i18n import t, set_language, get_language, TRANSLATIONS


@pytest.fixture(autouse=True)
def reset_language():
    """각 테스트 후 기본 언어(en)로 복원."""
    yield
    set_language("en")


class TestGetSetLanguage:
    def test_default_language_is_en(self):
        set_language("en")
        assert get_language() == "en"

    def test_set_language_ko(self):
        set_language("ko")
        assert get_language() == "ko"

    def test_set_language_unknown_does_not_raise(self):
        set_language("fr")
        assert get_language() == "fr"


class TestTranslation:
    def test_en_key_returns_english_string(self):
        set_language("en")
        assert t("btn_start") == "Start Monitoring"

    def test_ko_key_returns_korean_string(self):
        set_language("ko")
        assert t("btn_start") == "모니터링 시작"

    def test_missing_key_returns_key_itself(self):
        set_language("en")
        assert t("nonexistent_key_xyz") == "nonexistent_key_xyz"

    def test_unknown_language_returns_key(self):
        set_language("fr")
        assert t("btn_start") == "btn_start"

    def test_task_status_keys_exist_in_both_languages(self):
        status_keys = [
            "task_status_running",
            "task_status_completed",
            "task_status_stopped",
            "task_status_frozen",
            "task_status_idle",
        ]
        for key in status_keys:
            assert key in TRANSLATIONS["en"], f"Missing EN key: {key}"
            assert key in TRANSLATIONS["ko"], f"Missing KO key: {key}"

    def test_title_keys_exist_in_both_languages(self):
        for key in ("title_standby", "title_monitoring"):
            assert key in TRANSLATIONS["en"]
            assert key in TRANSLATIONS["ko"]

    def test_en_and_ko_have_same_keys(self):
        en_keys = set(TRANSLATIONS["en"].keys())
        ko_keys = set(TRANSLATIONS["ko"].keys())
        missing_in_ko = en_keys - ko_keys
        missing_in_en = ko_keys - en_keys
        assert not missing_in_ko, f"Keys in EN but not KO: {missing_in_ko}"
        assert not missing_in_en, f"Keys in KO but not EN: {missing_in_en}"
