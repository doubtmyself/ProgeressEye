"""토큰 생명주기 관리 모듈.

keyring을 사용하여 Windows 자격증명 저장소에 토큰을 보관하고,
필요 시 refresh_token으로 자동 갱신한다.
"""

# pyright: reportMissingImports=false

from __future__ import annotations

from typing import TYPE_CHECKING

import keyring
from keyring.errors import KeyringError, PasswordDeleteError

from . import AuthError
from utils.logger import log  # pyright: ignore[reportImplicitRelativeImport]

if TYPE_CHECKING:
    from .firebase_auth import FirebaseAuth

SERVICE_NAME = "ProgressEye"


class TokenManager:
    """토큰 저장/복원/삭제 및 자동 갱신 유틸리티."""

    def save_tokens(
        self,
        uid: str,
        email: str,
        display_name: str,
        refresh_token: str,
        id_token: str,
    ) -> None:
        """인증 정보를 keyring에 저장한다."""
        try:
            keyring.set_password(SERVICE_NAME, "uid", uid)
            keyring.set_password(SERVICE_NAME, "email", email)
            keyring.set_password(SERVICE_NAME, "display_name", display_name)
            keyring.set_password(SERVICE_NAME, "refresh_token", refresh_token)
            keyring.set_password(SERVICE_NAME, "id_token", id_token)
        except KeyringError as exc:
            raise AuthError(f"토큰 저장소 접근 실패: {exc}") from exc

    def load_tokens(self, firebase_auth: "FirebaseAuth") -> dict[str, str] | None:
        """저장된 refresh_token으로 Firebase 토큰 자동 갱신을 시도한다."""
        refresh = self.load_refresh_token()
        if not refresh:
            return None

        result = firebase_auth.refresh_token(refresh)
        uid = self.load_uid() or ""
        email = self.load_email() or ""
        display_name = self.load_display_name() or ""

        self.save_tokens(
            uid=uid,
            email=email,
            display_name=display_name,
            refresh_token=result["refresh_token"],
            id_token=result["id_token"],
        )
        log.info("저장된 refresh_token으로 자동 로그인 성공")
        return {
            "uid": uid,
            "email": email,
            "display_name": display_name,
            "id_token": result["id_token"],
            "refresh_token": result["refresh_token"],
        }

    def load_refresh_token(self) -> str | None:
        """저장된 refresh_token을 반환한다."""
        return self._get_secret("refresh_token")

    def load_uid(self) -> str | None:
        """저장된 uid를 반환한다."""
        return self._get_secret("uid")

    def load_email(self) -> str | None:
        """저장된 이메일을 반환한다."""
        return self._get_secret("email")

    def load_display_name(self) -> str | None:
        """저장된 display_name을 반환한다."""
        return self._get_secret("display_name")

    def clear(self) -> None:
        """모든 저장된 토큰을 삭제한다."""
        for key in ("uid", "email", "display_name", "refresh_token", "id_token"):
            try:
                keyring.delete_password(SERVICE_NAME, key)
            except PasswordDeleteError:
                continue
            except KeyringError as exc:
                raise AuthError(f"토큰 삭제 실패: {exc}") from exc

    def _get_secret(self, key: str) -> str | None:
        """keyring에서 값을 읽는다."""
        try:
            return keyring.get_password(SERVICE_NAME, key)
        except KeyringError as exc:
            raise AuthError(f"토큰 조회 실패: {exc}") from exc
