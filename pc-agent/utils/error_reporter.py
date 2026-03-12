"""미처리 예외를 Firestore에 기록하는 오류 보고 모듈."""

from __future__ import annotations

import platform
import sys
import time
import traceback
import uuid

from utils.logger import log  # pyright: ignore[reportImplicitRelativeImport]

_PROJECT_ID = "progresseye-49244"
_FIRESTORE_URL = (
    f"https://firestore.googleapis.com/v1/projects/{_PROJECT_ID}"
    f"/databases/progress/documents/errorReports"
)

# 로그인 후 main.py에서 설정
_uid: str = ""
_get_id_token: object = None  # () -> str | None


def init(uid: str, get_id_token: object) -> None:
    """오류 보고 모듈을 초기화하고 sys.excepthook을 등록한다."""
    global _uid, _get_id_token
    _uid = uid
    _get_id_token = get_id_token
    sys.excepthook = _handle_exception
    log.debug("[ErrorReporter] 초기화 완료 (uid=%s)", uid)


def reset() -> None:
    """로그아웃 시 상태를 초기화한다."""
    global _uid, _get_id_token
    _uid = ""
    _get_id_token = None
    sys.excepthook = sys.__excepthook__


def _handle_exception(
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_tb: object,
) -> None:
    """미처리 예외를 캡처하여 Firestore에 전송한다."""
    # KeyboardInterrupt는 무시
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return

    tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    log.error("[ErrorReporter] 미처리 예외:\n%s", tb_str)

    _send_report(
        error=f"{exc_type.__name__}: {exc_value}",
        traceback_str=tb_str,
    )

    sys.__excepthook__(exc_type, exc_value, exc_tb)


def _send_report(error: str, traceback_str: str) -> None:
    """Firestore errorReports 컬렉션에 오류를 기록한다."""
    if not _uid or not callable(_get_id_token):
        log.debug("[ErrorReporter] 미로그인 상태 — 오류 보고 건너뜀")
        return

    token = _get_id_token()  # type: ignore[call-arg]
    if not token:
        log.debug("[ErrorReporter] 토큰 없음 — 오류 보고 건너뜀")
        return

    from firebase.device_manager import APP_VERSION  # pyright: ignore[reportImplicitRelativeImport]
    import requests as _requests

    report_id = uuid.uuid4().hex[:16]
    now = int(time.time() * 1000)

    body = {
        "fields": {
            "uid": {"stringValue": _uid},
            "error": {"stringValue": error[:500]},
            "traceback": {"stringValue": traceback_str[:4000]},
            "appVersion": {"stringValue": APP_VERSION},
            "os": {"stringValue": platform.platform()},
            "ts": {"integerValue": str(now)},
        }
    }

    try:
        resp = _requests.post(
            f"{_FIRESTORE_URL}?documentId={report_id}",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=8,
        )
        if resp.status_code in (200, 201):
            log.info("[ErrorReporter] 오류 보고 전송 완료 (%s)", report_id)
        else:
            log.warning("[ErrorReporter] 전송 실패: %d", resp.status_code)
    except Exception as exc:
        log.warning("[ErrorReporter] 전송 예외: %s", exc)
