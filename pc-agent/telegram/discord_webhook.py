"""Discord Webhook — 알림 발송 전용 (단방향).

Discord Webhook URL로 텍스트 메시지와 이미지를 전송한다.
명령 수신은 지원하지 않는다 (webhook은 단방향).
"""

# pyright: reportMissingImports=false, reportMissingModuleSource=false

from __future__ import annotations

import io
from typing import Any

import requests

from utils.logger import log  # pyright: ignore[reportImplicitRelativeImport]


class DiscordWebhook:
    """Discord Webhook 경량 클라이언트."""

    def __init__(self, webhook_url: str) -> None:
        self._webhook_url = webhook_url
        self._session = requests.Session()

    @property
    def is_configured(self) -> bool:
        """Webhook URL이 설정되어 있는지 확인."""
        return bool(self._webhook_url)

    def update_url(self, webhook_url: str) -> None:
        """Webhook URL을 런타임에 변경한다."""
        self._webhook_url = webhook_url

    def send_message(self, text: str) -> bool:
        """텍스트 메시지를 전송한다."""
        if not self.is_configured:
            return False
        return self._post(json={"content": text})

    def send_photo(self, image_bytes: bytes, caption: str = "") -> bool:
        """이미지(바이트)를 전송한다."""
        if not self.is_configured:
            return False
        try:
            payload: dict[str, Any] = {}
            if caption:
                payload["content"] = caption
            resp = self._session.post(
                self._webhook_url,
                data=payload if payload else None,
                files={
                    "file": ("screenshot.png", io.BytesIO(image_bytes), "image/png")
                },
                timeout=30,
            )
            if not resp.ok:
                log.warning("Discord sendPhoto 실패: %s", resp.text)
                return False
            return True
        except requests.RequestException as exc:
            log.warning("Discord sendPhoto 네트워크 오류: %s", exc)
            return False

    def _post(self, **kwargs: Any) -> bool:
        """Discord Webhook POST 요청."""
        try:
            resp = self._session.post(
                self._webhook_url,
                timeout=10,
                **kwargs,
            )
            if not resp.ok:
                log.warning("Discord Webhook 실패: %s", resp.text)
                return False
            return True
        except requests.RequestException as exc:
            log.warning("Discord Webhook 네트워크 오류: %s", exc)
            return False
