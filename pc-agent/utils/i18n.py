"""국제화(i18n) 모듈.

한국어/영어 번역 딕셔너리와 번역 함수를 제공한다.
"""

_current_lang: str = "ko"

TRANSLATIONS: dict[str, dict[str, str]] = {
    "ko": {
        "progress_monitoring": "진행률 모니터링",
        "status_standby": "● 대기 중",
        "status_monitoring": "● 모니터링 중",
        "empty_state": "등록된 모니터링 영역이 없습니다.\n아래 버튼을 눌러 시작하세요.",
        "btn_add_bar": "진행률 바 추가",
        "btn_add_ocr": "진행률 숫자 추가",
        "btn_start": "모니터링 시작",
        "btn_stop": "● 모니터링 정지",
        "btn_edit": "✏ 작업 수정",
        "btn_view": "👁 영역보기",
        "btn_delete": "🗑 삭제",
        "type_bar": "진행률 바",
        "type_ocr": "진행률 숫자",
        "card_standby": "대기 중",
        "card_update": "⏱ 업데이트: {time}",
        "settings_title": "⚙ 설정",
        "settings_window_title": "설정",
        "settings_interval": "모니터링 간격",
        "settings_interval_suffix": " 초",
        "settings_language": "언어",
        "btn_cancel": "취소",
        "btn_save": "저장",
        "settings_account": "계정",
        "settings_logged_in_as": "로그인: {email}",
        "btn_logout": "로그아웃",
        "welcome_title": "👋 ProgressEye에 오신 것을 환영합니다!",
        "welcome_subtitle": "시작하기 전에 기본 설정을 확인해주세요.",
        "btn_start_app": "시작하기",
        "tray_open": "메인 창 열기",
        "tray_quit": "종료",
    },
    "en": {
        "progress_monitoring": "Progress Monitoring",
        "status_standby": "● Standby",
        "status_monitoring": "● Monitoring",
        "empty_state": "No registered monitoring areas.\nPress button below to start.",
        "btn_add_bar": "Add Progress Bar",
        "btn_add_ocr": "Add Progress Number",
        "btn_start": "Start Monitoring",
        "btn_stop": "● Stop Monitoring",
        "btn_edit": "✏ Edit Task",
        "btn_view": "👁 View Area",
        "btn_delete": "🗑 Delete",
        "type_bar": "Progress Bar",
        "type_ocr": "Progress Number",
        "card_standby": "Standby",
        "card_update": "⏱ Updated: {time}",
        "settings_title": "⚙ Settings",
        "settings_window_title": "Settings",
        "settings_interval": "Monitoring Interval",
        "settings_interval_suffix": " sec",
        "settings_language": "Language",
        "btn_cancel": "Cancel",
        "btn_save": "Save",
        "settings_account": "Account",
        "settings_logged_in_as": "Logged in: {email}",
        "btn_logout": "Log Out",
        "welcome_title": "👋 Welcome to ProgressEye!",
        "welcome_subtitle": "Please review the settings before getting started.",
        "btn_start_app": "Get Started",
        "tray_open": "Open Main Window",
        "tray_quit": "Quit",
    },
}


def t(key: str) -> str:
    """현재 언어로 번역된 문자열을 반환한다.

    키가 없으면 키 자체를 반환한다.
    """
    return TRANSLATIONS.get(_current_lang, {}).get(key, key)


def set_language(lang: str) -> None:
    """표시 언어를 변경한다."""
    global _current_lang  # noqa: PLW0603
    _current_lang = lang


def get_language() -> str:
    """현재 언어 코드를 반환한다."""
    return _current_lang
