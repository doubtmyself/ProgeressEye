"""Telegram Bot — 알림 발송 + 명령 수신 (순수 requests 기반).

외부 라이브러리 없이 Telegram Bot API를 직접 호출한다.
명령어:
    /status  — 전체 작업 진행률 목록
    /screenshot <작업명|all> — 해당 작업 영역 스크린샷 전송
    /start_monitor — 모니터링 시작
    /stop_monitor  — 모니터링 정지
"""

# pyright: reportMissingImports=false, reportMissingModuleSource=false

from __future__ import annotations

import io
import threading
import time
from typing import Any, Callable

import requests

from utils.logger import log  # pyright: ignore[reportImplicitRelativeImport]


class TelegramBot:
    """Telegram Bot API 경량 클라이언트."""

    API_BASE = "https://api.telegram.org/bot{token}"

    def __init__(
        self,
        token: str,
        chat_id: str,
        *,
        on_command: Callable[[str, list[str]], None] | None = None,
    ) -> None:
        """
        Args:
            token: Telegram Bot API 토큰 (@BotFather에서 발급).
            chat_id: 메시지를 보낼 채팅 ID.
            on_command: 명령 수신 콜백 (command, args).
        """
        self._token = token
        self._chat_id = chat_id
        self._on_command = on_command
        self._base_url = self.API_BASE.format(token=token)
        self._session = requests.Session()
        self._polling_thread: threading.Thread | None = None
        self._running = False
        self._last_update_id = 0

    # ── 공개 API: 발송 ──

    def send_message(self, text: str) -> bool:
        """텍스트 메시지를 전송한다."""
        return self._call("sendMessage", {"chat_id": self._chat_id, "text": text})

    def send_photo(self, image_bytes: bytes, caption: str = "") -> bool:
        """이미지(바이트)를 전송한다."""
        try:
            resp = self._session.post(
                f"{self._base_url}/sendPhoto",
                data={"chat_id": self._chat_id, "caption": caption},
                files={
                    "photo": ("screenshot.png", io.BytesIO(image_bytes), "image/png")
                },
                timeout=30,
            )
            if not resp.ok:
                log.warning("Telegram sendPhoto 실패: %s", resp.text)
                return False
            return True
        except requests.RequestException as exc:
            log.warning("Telegram sendPhoto 네트워크 오류: %s", exc)
            return False

    # ── 공개 API: 폴링 ──

    def start_polling(self) -> None:
        """백그라운드 스레드에서 명령 수신 폴링을 시작한다."""
        if self._polling_thread is not None:
            return
        self._running = True
        self._polling_thread = threading.Thread(
            target=self._poll_loop,
            daemon=True,
            name="telegram-poll",
        )
        self._polling_thread.start()
        log.info("Telegram Bot 폴링 시작")

    def stop_polling(self) -> None:
        """폴링을 중지한다."""
        self._running = False
        self._polling_thread = None
        log.info("Telegram Bot 폴링 중지")

    @property
    def is_configured(self) -> bool:
        """토큰과 chat_id가 설정되어 있는지 확인."""
        return bool(self._token) and bool(self._chat_id)

    def update_credentials(self, token: str, chat_id: str) -> None:
        """토큰과 chat_id를 런타임에 변경한다."""
        self._token = token
        self._chat_id = chat_id
        self._base_url = self.API_BASE.format(token=token)

    # ── 내부 ──

    def _call(self, method: str, payload: dict[str, Any]) -> bool:
        """Telegram API를 호출한다."""
        try:
            resp = self._session.post(
                f"{self._base_url}/{method}",
                json=payload,
                timeout=10,
            )
            if not resp.ok:
                log.warning("Telegram %s 실패: %s", method, resp.text)
                return False
            return True
        except requests.RequestException as exc:
            log.warning("Telegram %s 네트워크 오류: %s", method, exc)
            return False

    def _poll_loop(self) -> None:
        """Long polling으로 업데이트를 수신한다."""
        while self._running:
            try:
                resp = self._session.get(
                    f"{self._base_url}/getUpdates",
                    params={
                        "offset": self._last_update_id + 1,
                        "timeout": 30,
                    },
                    timeout=35,
                )
                if not resp.ok:
                    log.debug("Telegram getUpdates 실패: %s", resp.status_code)
                    time.sleep(5)
                    continue

                data = resp.json()
                for update in data.get("result", []):
                    self._last_update_id = update["update_id"]
                    self._handle_update(update)

            except requests.RequestException:
                time.sleep(5)
            except Exception as exc:
                log.warning("Telegram 폴링 오류: %s", exc)
                time.sleep(5)

    def _handle_update(self, update: dict[str, Any]) -> None:
        """수신한 업데이트를 처리한다."""
        message = update.get("message", {})
        text = message.get("text", "")
        # 보안: 허용된 chat_id만 처리
        msg_chat_id = str(message.get("chat", {}).get("id", ""))
        if msg_chat_id != self._chat_id:
            log.debug(
                "Telegram: 허용되지 않은 chat_id %s (허용: %s)",
                msg_chat_id,
                self._chat_id,
            )
            return

        if not text.startswith("/"):
            return

        parts = text.strip().split()
        command = parts[0].lower().split("@")[0]  # /command@botname 형식 처리
        args = parts[1:]

        log.info("Telegram 명령 수신: %s %s", command, args)
        if self._on_command:
            try:
                self._on_command(command, args)
            except Exception as exc:
                log.warning("Telegram 명령 처리 오류: %s", exc)
