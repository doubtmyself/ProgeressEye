"""Firebase Realtime Database REST API 래퍼."""

# pyright: reportMissingImports=false, reportMissingModuleSource=false

from __future__ import annotations

from typing import Any, Callable

import requests

from utils.logger import log  # pyright: ignore[reportImplicitRelativeImport]


class FirebaseDBError(Exception):
    """Firebase Realtime Database 통신 오류."""


class RealtimeDB:
    """Firebase Realtime Database REST API 클라이언트."""

    def __init__(self, db_url: str, get_id_token: Callable[[], str]) -> None:
        self._db_url = db_url.rstrip("/")
        self._get_id_token = get_id_token

    def get(self, path: str) -> Any:
        """경로 데이터를 조회한다."""
        return self._request("GET", path)

    def put(self, path: str, data: Any) -> Any:
        """경로 데이터를 전체 덮어쓴다."""
        return self._request("PUT", path, data=data)

    def patch(self, path: str, data: dict[str, Any]) -> Any:
        """경로 데이터를 부분 갱신한다."""
        return self._request("PATCH", path, data=data)

    def delete(self, path: str) -> None:
        """경로 데이터를 삭제한다."""
        self._request("DELETE", path)

    def _request(self, method: str, path: str, data: Any = None) -> Any:
        """공통 REST 요청을 실행한다."""
        normalized_path = path.strip("/")
        token = self._get_id_token()
        if not token:
            raise FirebaseDBError("Firebase id_token이 비어 있습니다.")

        url = f"{self._db_url}/{normalized_path}.json"

        try:
            response = requests.request(
                method,
                url,
                params={"auth": token},
                json=data,
                timeout=10,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            detail = str(exc)
            response_obj = exc.response
            if response_obj is not None:
                try:
                    error_body = response_obj.json()
                except ValueError:
                    error_body = response_obj.text
                detail = f"{detail} | response={error_body}"
            log.warning(
                "Firebase DB 요청 실패 [%s %s]: %s", method, normalized_path, detail
            )
            raise FirebaseDBError(f"Firebase DB 요청 실패: {detail}") from exc

        if method == "DELETE":
            return None

        try:
            return response.json()
        except ValueError as exc:
            log.warning(
                "Firebase DB 응답 JSON 파싱 실패 [%s %s]: %s",
                method,
                normalized_path,
                exc,
            )
            raise FirebaseDBError("Firebase DB 응답 파싱 실패") from exc
