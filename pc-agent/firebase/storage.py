# pyright: reportMissingImports=false, reportMissingModuleSource=false

"""Firebase Storage REST API 업로드 모듈."""

from __future__ import annotations

from typing import Callable, cast
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry  # pyright: ignore[reportUnknownVariableType]

from utils.logger import log  # pyright: ignore[reportImplicitRelativeImport]


class FirebaseStorageError(Exception):
    """Firebase Storage 통신 오류."""


class FirebaseStorage:
    """Firebase Storage REST API 클라이언트."""

    def __init__(self, bucket: str, get_id_token: Callable[[], str]) -> None:
        self._bucket: str = bucket.strip()
        self._get_id_token: Callable[[], str] = get_id_token

        retry = Retry(  # pyright: ignore[reportUnknownVariableType]
            total=3,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["POST", "DELETE"],
        )
        self._session: requests.Session = requests.Session()
        self._session.mount(
            "https://",
            HTTPAdapter(max_retries=retry),  # pyright: ignore[reportUnknownArgumentType]
        )

    def upload_jpeg(self, path: str, data: bytes) -> str:
        """JPEG 바이트를 업로드하고 공개 다운로드 URL을 반환한다."""
        normalized_path = path.strip("/")
        if not normalized_path:
            raise FirebaseStorageError("업로드 경로가 비어 있습니다.")
        if not data:
            raise FirebaseStorageError("업로드 데이터가 비어 있습니다.")
        if not self._bucket:
            raise FirebaseStorageError("Firebase Storage bucket이 비어 있습니다.")

        encoded_path = quote(normalized_path, safe="")
        url = (
            f"https://firebasestorage.googleapis.com/v0/b/{self._bucket}/o"
            f"?uploadType=media&name={encoded_path}"
        )

        last_exc: requests.RequestException | None = None
        response: requests.Response | None = None
        for attempt in range(2):
            token = self._get_id_token()
            if not token:
                raise FirebaseStorageError("Firebase id_token이 비어 있습니다.")

            try:
                response = self._session.post(
                    url,
                    data=data,
                    headers={
                        "Authorization": f"Firebase {token}",
                        "Content-Type": "image/jpeg",
                    },
                    timeout=15,
                )

                if response.status_code == 401 and attempt == 0:
                    log.warning(
                        "Firebase Storage 토큰 만료 의심으로 재시도 [POST %s]",
                        normalized_path,
                    )
                    continue

                response.raise_for_status()
                break
            except requests.RequestException as exc:
                last_exc = exc
                response_obj = exc.response
                detail = str(exc)
                if response_obj is not None:
                    try:
                        error_body = cast(object, response_obj.json())
                    except ValueError:
                        error_body = response_obj.text
                    detail = f"{detail} | response={error_body}"

                if (
                    attempt == 0
                    and response_obj is not None
                    and response_obj.status_code == 401
                ):
                    log.warning(
                        "Firebase Storage 업로드 401 재시도 [POST %s]: %s",
                        normalized_path,
                        detail,
                    )
                    continue

                log.warning(
                    "Firebase Storage 업로드 실패 [POST %s]: %s",
                    normalized_path,
                    detail,
                )
                raise FirebaseStorageError(
                    f"Firebase Storage 업로드 실패: {detail}"
                ) from exc

        if response is None:
            if last_exc is not None:
                raise FirebaseStorageError(
                    f"Firebase Storage 업로드 실패: {last_exc}"
                ) from last_exc
            raise FirebaseStorageError("Firebase Storage 업로드 실패")

        try:
            body = cast(object, response.json())
        except ValueError as exc:
            log.warning(
                "Firebase Storage 응답 JSON 파싱 실패 [POST %s]: %s",
                normalized_path,
                exc,
            )
            raise FirebaseStorageError("Firebase Storage 응답 파싱 실패") from exc

        if not isinstance(body, dict):
            raise FirebaseStorageError(
                "Firebase Storage 응답 형식이 올바르지 않습니다."
            )

        body_dict = cast(dict[str, object], body)
        raw_tokens: object | None = body_dict.get("downloadTokens")
        if not isinstance(raw_tokens, str) or not raw_tokens.strip():
            log.warning(
                "Firebase Storage downloadTokens 누락 [POST %s]: %s",
                normalized_path,
                body_dict,
            )
            raise FirebaseStorageError("Firebase Storage download token 누락")

        download_token = raw_tokens.split(",", maxsplit=1)[0].strip()
        if not download_token:
            raise FirebaseStorageError(
                "Firebase Storage download token이 비어 있습니다."
            )

        return (
            f"https://firebasestorage.googleapis.com/v0/b/{self._bucket}/o/{encoded_path}"
            f"?alt=media&token={download_token}"
        )

    def delete(self, path: str) -> None:
        """스토리지 경로의 파일을 삭제한다."""
        normalized_path = path.strip("/")
        if not normalized_path:
            raise FirebaseStorageError("삭제 경로가 비어 있습니다.")
        if not self._bucket:
            raise FirebaseStorageError("Firebase Storage bucket이 비어 있습니다.")

        encoded_path = quote(normalized_path, safe="")
        url = f"https://firebasestorage.googleapis.com/v0/b/{self._bucket}/o/{encoded_path}"

        last_exc: requests.RequestException | None = None
        for attempt in range(2):
            token = self._get_id_token()
            if not token:
                raise FirebaseStorageError("Firebase id_token이 비어 있습니다.")

            try:
                response = self._session.delete(
                    url,
                    headers={"Authorization": f"Firebase {token}"},
                    timeout=10,
                )

                if response.status_code == 401 and attempt == 0:
                    log.warning(
                        "Firebase Storage 토큰 만료 의심으로 재시도 [DELETE %s]",
                        normalized_path,
                    )
                    continue

                response.raise_for_status()
                return
            except requests.RequestException as exc:
                last_exc = exc
                response_obj = exc.response
                detail = str(exc)
                if response_obj is not None:
                    try:
                        error_body = cast(object, response_obj.json())
                    except ValueError:
                        error_body = response_obj.text
                    detail = f"{detail} | response={error_body}"

                if (
                    attempt == 0
                    and response_obj is not None
                    and response_obj.status_code == 401
                ):
                    log.warning(
                        "Firebase Storage 삭제 401 재시도 [DELETE %s]: %s",
                        normalized_path,
                        detail,
                    )
                    continue

                log.warning(
                    "Firebase Storage 삭제 실패 [DELETE %s]: %s",
                    normalized_path,
                    detail,
                )
                raise FirebaseStorageError(
                    f"Firebase Storage 삭제 실패: {detail}"
                ) from exc

        if last_exc is not None:
            raise FirebaseStorageError(
                f"Firebase Storage 삭제 실패: {last_exc}"
            ) from last_exc
        raise FirebaseStorageError("Firebase Storage 삭제 실패")
