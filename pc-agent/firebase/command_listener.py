# pyright: reportMissingImports=false, reportMissingModuleSource=false, reportUnknownVariableType=false

from __future__ import annotations

import json
import queue
import threading
from collections.abc import Iterable
from typing import Callable, cast

import requests

from utils.logger import log  # pyright: ignore[reportImplicitRelativeImport]


class CommandListener:
    """Firebase RTDB SSE 명령 리스너."""

    def __init__(
        self,
        db_url: str,
        get_id_token: Callable[[], str],
        command_queue: queue.Queue[dict[str, object]],
    ) -> None:
        self._db_url: str = db_url.rstrip("/")
        self._get_id_token: Callable[[], str] = get_id_token
        self._command_queue: queue.Queue[dict[str, object]] = command_queue

        self._uid: str = ""
        self._thread: threading.Thread | None = None
        self._stop_event: threading.Event = threading.Event()
        self._response_lock: threading.Lock = threading.Lock()
        self._response: requests.Response | None = None

    def start(self, uid: str) -> None:
        """users/{uid}/commands 경로 SSE 리스닝을 시작한다."""
        if self._thread and self._thread.is_alive():
            log.warning("CommandListener가 이미 실행 중입니다.")
            return

        self._uid = uid.strip()
        if not self._uid:
            log.warning("CommandListener 시작 실패: uid가 비어 있습니다.")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._listen_loop,
            name="sse-command-listener",
            daemon=True,
        )
        self._thread.start()
        log.info("CommandListener 시작: users/%s/commands", self._uid)

    def stop_nowait(self) -> None:
        """비블로킹 종료 — 메인 스레드에서 안전하게 호출 가능."""
        self._stop_event.set()
        self._thread = None
        self._uid = ""
        # response.close()는 Windows에서 SSE 소켓 대기로 블로킹될 수 있으므로
        # daemon 스레드에서 처리 — _app.quit() 시 자동 종료됨
        import threading as _threading
        _threading.Thread(target=self._close_response, daemon=True).start()
        log.info("CommandListener 비블로킹 중지")
    def stop(self) -> None:
        """SSE 리스너를 종료한다."""
        self._stop_event.set()
        self._close_response()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

        self._thread = None
        self._uid = ""
        log.info("CommandListener 중지")

    def _listen_loop(self) -> None:
        """SSE 연결/재연결 루프."""
        backoff_seconds = 1

        while not self._stop_event.is_set():
            token = self._get_id_token()
            if not token:
                log.warning("SSE 연결 실패: Firebase id_token이 비어 있습니다.")
                if self._wait_before_retry(backoff_seconds):
                    break
                backoff_seconds = min(backoff_seconds * 2, 30)
                continue

            url = f"{self._db_url}/users/{self._uid}/commands.json"
            params = {"auth": token}
            headers = {
                "Accept": "text/event-stream",
                "Cache-Control": "no-cache",
            }

            try:
                with requests.get(
                    url,
                    params=params,
                    headers=headers,
                    stream=True,
                    timeout=(10, 60),
                ) as response:
                    response.raise_for_status()
                    backoff_seconds = 1
                    self._set_response(response)
                    self._consume_stream(response)
            except requests.RequestException as exc:
                if self._stop_event.is_set():
                    break
                log.warning("SSE 연결 오류, 재시도 예정: %s", exc)
                if self._wait_before_retry(backoff_seconds):
                    break
                backoff_seconds = min(backoff_seconds * 2, 30)
            except Exception as exc:
                if self._stop_event.is_set():
                    break
                log.warning("SSE 처리 오류, 재시도 예정: %s", exc)
                if self._wait_before_retry(backoff_seconds):
                    break
                backoff_seconds = min(backoff_seconds * 2, 30)
            finally:
                self._clear_response()

    def _consume_stream(self, response: requests.Response) -> None:
        """SSE 스트림을 파싱해 명령 큐에 전달한다."""
        current_event_type = ""
        current_data_lines: list[str] = []
        initial_snapshot_skipped = False
        log.info("SSE 스트림 수신 시작")

        raw_lines = cast(Iterable[object], response.iter_lines(chunk_size=1, decode_unicode=True))
        for raw_line_obj in raw_lines:
            if self._stop_event.is_set():
                return

            raw_line = raw_line_obj if isinstance(raw_line_obj, str) else ""

            line = (raw_line or "").strip()

            if line.startswith("event:"):
                current_event_type = line[6:].strip()
                continue

            if line.startswith("data:"):
                current_data_lines.append(line[5:].strip())
                continue

            if line != "":
                continue

            if not current_event_type:
                current_data_lines.clear()
                continue

            data_text = "\n".join(current_data_lines)
            event_type = current_event_type
            current_event_type = ""
            current_data_lines.clear()

            if not data_text:
                continue

            if event_type == "keep-alive":
                continue

            if event_type in {"cancel", "auth_revoked"}:
                log.warning("SSE 이벤트 수신(%s), 재연결합니다.", event_type)
                return

            if event_type not in {"put", "patch"}:
                continue

            try:
                payload_obj = cast(object, json.loads(data_text))
            except json.JSONDecodeError as exc:
                log.warning("SSE data JSON 파싱 실패: %s", exc)
                continue

            if not isinstance(payload_obj, dict):
                continue

            payload: dict[str, object] = {}
            for key, value in payload_obj.items():
                if isinstance(key, str):
                    payload[key] = value

            path = payload.get("path")
            log.debug("SSE event: type=%s path=%s", event_type, path)
            if event_type == "put" and path == "/" and not initial_snapshot_skipped:
                initial_snapshot_skipped = True
                # 초기 스냅샷에 미처리 명령이 있으면 큐에 추가
                for command in self._extract_commands(payload):
                    try:
                        self._command_queue.put_nowait(command)
                        log.info("초기 스냅샷 미처리 명령 발견: %s", command.get("type"))
                    except queue.Full:
                        log.warning("명령 큐가 가득 차 초기 명령을 버립니다: %s", command)
                continue

            for command in self._extract_commands(payload):
                try:
                    self._command_queue.put_nowait(command)
                    log.info("SSE 명령 큐 추가: %s", command.get("type"))
                except queue.Full:
                    log.warning("명령 큐가 가득 차 명령을 버립니다: %s", command)

    def _extract_commands(self, payload: dict[str, object]) -> list[dict[str, object]]:
        """SSE payload에서 screenshot/monitor 명령을 추출한다."""
        path = payload.get("path")
        data = payload.get("data")

        if not isinstance(path, str):
            return []

        if path == "/":
            if not isinstance(data, dict):
                return []

            data_map: dict[str, object] = {}
            for key, value in data.items():
                if isinstance(key, str):
                    data_map[key] = value

            commands: list[dict[str, object]] = []
            for key in ("screenshot", "monitor", "forceLogout"):
                item = data_map.get(key)
                if item is not None:
                    commands.append(
                        {
                            "type": key,
                            "data": item if isinstance(item, dict) else {"value": item},
                        }
                    )
            return commands

        segments = [segment for segment in path.strip("/").split("/") if segment]
        if not segments:
            return []

        command_type = segments[0]
        if command_type not in {"screenshot", "monitor", "forceLogout"}:
            return []

        if len(segments) == 1:
            if data is None:
                return []
            if isinstance(data, dict):
                command_data: dict[str, object] = {}
                for key, value in data.items():
                    if isinstance(key, str):
                        command_data[key] = value
            else:
                command_data = {"value": data}
            return [{"type": command_type, "data": command_data}]

        if data is None:
            return []

        nested_data: object = data
        for key in reversed(segments[1:]):
            nested_data = {key: nested_data}
        return [{"type": command_type, "data": nested_data}]

    def _set_response(self, response: requests.Response) -> None:
        with self._response_lock:
            self._response = response

    def _clear_response(self) -> None:
        with self._response_lock:
            self._response = None

    def _close_response(self) -> None:
        with self._response_lock:
            response = self._response
            self._response = None

        if response is not None:
            try:
                response.close()
            except Exception:
                pass

    def _wait_before_retry(self, seconds: int) -> bool:
        """재시도 대기. 중지 요청 시 True 반환."""
        if seconds <= 0:
            return self._stop_event.is_set()
        return self._stop_event.wait(timeout=seconds)
