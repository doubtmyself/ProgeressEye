"""Firebase Authentication REST API 모듈.

Google id_token과 Firebase 세션 간 토큰 교환 및 갱신을 담당한다.
firebase-admin SDK를 사용하지 않는다.
"""

# pyright: reportMissingImports=false, reportMissingModuleSource=false

from __future__ import annotations

import os
from typing import Any

import requests

from . import AuthError
from utils.i18n import t  # pyright: ignore[reportImplicitRelativeImport]

# 출처: 사용자 제공 Firebase credentials
FIREBASE_API_KEY = os.environ.get(
    "PROGRESSEYE_FIREBASE_API_KEY",
    "AIzaSyDXe_l0KKLf4Tnufs2n5AmDF93bZUuuLm4",
)
SIGN_IN_URL = (
    "https://identitytoolkit.googleapis.com/v1/accounts:signInWithIdp"
    f"?key={FIREBASE_API_KEY}"
)
REFRESH_URL = f"https://securetoken.googleapis.com/v1/token?key={FIREBASE_API_KEY}"
DELETE_ACCOUNT_URL = (
    f"https://identitytoolkit.googleapis.com/v1/accounts:delete?key={FIREBASE_API_KEY}"
)


class FirebaseAuth:
    """Firebase Authentication REST API 클라이언트."""

    def sign_in_with_google(self, google_id_token: str) -> dict[str, str]:
        """Google id_token으로 Firebase 로그인한다.

        Returns:
            {
                "id_token": str,
                "refresh_token": str,
                "uid": str,
                "email": str,
                "display_name": str,
            }

        Raises:
            AuthError: 인증 실패 또는 네트워크 오류.
        """
        payload = {
            "postBody": f"id_token={google_id_token}&providerId=google.com",
            "requestUri": "http://localhost",
            "returnIdpCredential": True,
            "returnSecureToken": True,
        }

        data = self._post_json(SIGN_IN_URL, payload)
        try:
            return {
                "id_token": str(data["idToken"]),
                "refresh_token": str(data["refreshToken"]),
                "uid": str(data["localId"]),
                "email": str(data.get("email", "")),
                "display_name": str(data.get("displayName", "")),
            }
        except KeyError as exc:
            raise AuthError(t("firebase_login_bad_response")) from exc

    def refresh_token(self, refresh_token: str) -> dict[str, str]:
        """refresh_token으로 Firebase id_token을 갱신한다.

        Returns:
            {"id_token": str, "refresh_token": str}

        Raises:
            AuthError: 토큰 갱신 실패 또는 네트워크 오류.
        """
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }

        data = self._post_form(REFRESH_URL, payload)
        try:
            return {
                "id_token": str(data["id_token"]),
                "refresh_token": str(data["refresh_token"]),
            }
        except KeyError as exc:
            raise AuthError(t("firebase_refresh_bad_response")) from exc

    def delete_account(self, id_token: str) -> None:
        """현재 Firebase 계정을 삭제한다.

        Args:
            id_token: 삭제 대상 계정의 유효 Firebase id_token.

        Raises:
            AuthError: 계정 삭제 실패 또는 네트워크 오류.
        """
        payload = {"idToken": id_token}
        self._post_json(DELETE_ACCOUNT_URL, payload)

    def _post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        """JSON POST 요청을 보내고 JSON 응답을 반환한다."""
        try:
            response = requests.post(url, json=payload, timeout=10)
        except requests.Timeout as exc:
            raise AuthError(t("firebase_timeout")) from exc
        except requests.RequestException as exc:
            raise AuthError(t("firebase_network_error").format(error=exc)) from exc

        return self._parse_response(response)

    def _post_form(self, url: str, payload: dict[str, str]) -> dict[str, Any]:
        """Form POST 요청을 보내고 JSON 응답을 반환한다."""
        try:
            response = requests.post(url, data=payload, timeout=10)
        except requests.Timeout as exc:
            raise AuthError(t("firebase_timeout")) from exc
        except requests.RequestException as exc:
            raise AuthError(t("firebase_network_error").format(error=exc)) from exc

        return self._parse_response(response)

    @staticmethod
    def _parse_response(response: requests.Response) -> dict[str, Any]:
        """Firebase 응답을 파싱하고 오류를 AuthError로 변환한다."""
        try:
            data = response.json()
        except ValueError:
            data = {}

        if not response.ok:
            message = FirebaseAuth._extract_error_message(data)
            raise AuthError(t("firebase_auth_failed").format(message=message))

        if not isinstance(data, dict):
            raise AuthError(t("firebase_parse_error"))
        return data

    @staticmethod
    def _extract_error_message(data: dict[str, Any]) -> str:
        """Firebase 오류 메시지를 추출한다."""
        try:
            error = data.get("error", {})
            if isinstance(error, dict):
                return str(error.get("message", t("unknown_error")))
        except AttributeError:
            pass
        return t("unknown_error")
