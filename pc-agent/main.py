"""ProgressEye PC Agent 엔트리포인트.

영역 선택 → 바 탐지 → 전환점 분석 → 진행률 표시 파이프라인을 실행한다.
MVP 단계: Firebase 연동 없이 로컬 동작만 구현.
"""

# pyright: reportMissingImports=false, reportMissingModuleSource=false, reportMissingTypeArgument=false

import queue
import time
import threading
import os
import pathlib
import sys
import uuid
import ctypes
from typing import Callable

from PIL import Image as PILImage
from PyQt6.QtCore import QRect, QTimer
from PyQt6.QtGui import QGuiApplication, QImage
from PyQt6.QtWidgets import QApplication, QMessageBox

from auth import AuthError  # pyright: ignore[reportImplicitRelativeImport]
from auth.firebase_auth import FirebaseAuth  # pyright: ignore[reportImplicitRelativeImport]
from auth.google_oauth import GoogleOAuth  # pyright: ignore[reportImplicitRelativeImport]
from auth.token_manager import TokenManager  # pyright: ignore[reportImplicitRelativeImport]
from config import Config  # pyright: ignore[reportImplicitRelativeImport]
from firebase import RealtimeDB, DeviceManager  # pyright: ignore[reportImplicitRelativeImport]
from firebase.device_manager import APP_VERSION, get_min_pc_version  # pyright: ignore[reportImplicitRelativeImport]
from firebase.storage import FirebaseStorage  # pyright: ignore[reportImplicitRelativeImport]
from firebase.command_listener import CommandListener  # pyright: ignore[reportImplicitRelativeImport]
from core.bar_analyzer import AnalysisResult, BarAnalyzer  # pyright: ignore[reportImplicitRelativeImport]
from core.bar_finder import BarFinder, BarRegion  # pyright: ignore[reportImplicitRelativeImport]
from core.capturer import ScreenCapturer  # pyright: ignore[reportImplicitRelativeImport]
from core.freeze_detector import FreezeDetector  # pyright: ignore[reportImplicitRelativeImport]
from core.scheduler import CaptureScheduler  # pyright: ignore[reportImplicitRelativeImport]
from core.system_monitor import collect_stats, warmup_cpu_percent, stop_sampler  # pyright: ignore[reportImplicitRelativeImport]
from ui.area_selector import AreaSelector  # pyright: ignore[reportImplicitRelativeImport]
from ui.color_picker import BarPreviewDialog  # pyright: ignore[reportImplicitRelativeImport]
from core.ocr_reader import OcrReader  # pyright: ignore[reportImplicitRelativeImport]
from ui.ocr_preview import OcrPreviewDialog  # pyright: ignore[reportImplicitRelativeImport]
from ui.region_viewer import RegionViewer  # pyright: ignore[reportImplicitRelativeImport]
from ui.main_window import MainWindow  # pyright: ignore[reportImplicitRelativeImport]

from utils.logger import log  # pyright: ignore[reportImplicitRelativeImport]
from utils.i18n import set_language, t  # pyright: ignore[reportImplicitRelativeImport]

_HEARTBEAT_INTERVAL_MS = 60_000
_STATS_SYNC_INTERVAL_MS = 60_000
_SAMPLER_START_DELAY_MS = 20_000


class ProgressEyeApp:
    """ProgressEye 메인 애플리케이션.

    모든 모듈을 연결하고 전체 파이프라인을 관리한다.
    """

    def __init__(self, debug_mode: bool = False) -> None:
        self._app = QApplication(sys.argv)
        self._config = Config()
        self._capturer = ScreenCapturer()
        self._analyzer = BarAnalyzer()
        self._bar_finder = BarFinder()
        self._ocr_reader = OcrReader()
        self._freeze_detector = FreezeDetector(
            timeout_minutes=self._config.get("freeze_detection.timeout_minutes", 5),
        )
        self._scheduler = CaptureScheduler(
            on_capture=self._on_capture,
            capturer=self._capturer,
            on_cycle_complete=self._on_cycle_complete,
        )
        self._google_oauth = GoogleOAuth()
        self._firebase_auth = FirebaseAuth()
        self._token_manager = TokenManager()
        self._firebase_id_token: str | None = None
        self._token_expires_at: float = 0.0  # epoch seconds
        self._realtime_db: RealtimeDB | None = None
        self._device_manager: DeviceManager | None = None
        self._heartbeat_timer: QTimer | None = None
        self._command_listener: CommandListener | None = None
        self._firebase_storage: FirebaseStorage | None = None
        self._screenshot_cache: dict[
            str, tuple[str, str]
        ] = {}  # device_id -> (jpeg_hash, download_url)
        self._command_queue: queue.Queue[dict[str, object]] = queue.Queue()
        self._processed_command_ids: dict[str, float] = {}
        self._last_command_ts_by_type: dict[str, int] = {}
        self._editing_region_id: str | None = None  # 작업 수정 중인 영역 ID

        self._alerted_regions: dict[str, float] = {}  # region_id -> alert progress
        self._post_completion_fails: dict[str, int] = {}  # 완료 후 연속 캡쳐 실패 횟수
        self._pending_firebase_batch: dict[str, dict] = {}  # 사이클별 Firebase 배치
        self._last_firebase_state: dict[
            str, dict
        ] = {}  # region_id -> {p, s} 마지막 분석값
        self._last_synced_firebase_state: dict[
            str, dict
        ] = {}  # region_id -> {p, s} 마지막 전송값
        self._last_stats_synced_at_ms: int = 0
        self._completion_first_reached: dict[
            str, float
        ] = {}  # region_id -> threshold 최초 도달 timestamp (time.time())
        self._template_images: dict[
            str, PILImage.Image
        ] = {}  # 이미지 변경 감지용 메모리 캐시
        self._template_dir = (
            pathlib.Path(os.path.dirname(os.path.abspath(__file__))) / "templates"
        )
        self._template_dir.mkdir(exist_ok=True)

        # 언어 설정 (MainWindow 생성 전에 적용해야 t() 번역이 올바름)
        set_language(self._config.get("language", "en"))

        # UI
        self._debug_mode = debug_mode
        self._main_window = MainWindow(show_test_buttons=debug_mode)
        self._area_selector: AreaSelector | None = None
        self._region_viewer: RegionViewer | None = None
        self._task_counter = len(self._config.regions)
        self._selection_mode: str = "bar"  # "bar" 또는 "ocr"

        # 크로스-스레드 액션 큐 (pystray/Timer → Qt 메인 스레드)
        self._action_queue: queue.Queue[Callable[[], None]] = queue.Queue()
        self._poll_timer = QTimer()
        self._poll_timer.timeout.connect(self._process_queued_actions)
        self._poll_timer.start(50)

        # 모바일 명령 큐 폴링 (200ms)
        self._cmd_poll_timer = QTimer()
        self._cmd_poll_timer.timeout.connect(self._process_commands)
        self._cmd_poll_timer.start(200)

        # 시그널 연결
        self._main_window.select_area_requested.connect(self._start_area_selection)
        self._main_window.toggle_monitoring_requested.connect(self._toggle_monitoring)

        self._main_window.select_ocr_area_requested.connect(
            self._start_ocr_area_selection
        )
        self._main_window.region_toggled.connect(self._on_region_toggled)
        self._main_window.region_delete_requested.connect(self._on_region_deleted)
        self._main_window.region_view_requested.connect(self._show_region_view)
        self._main_window.region_edit_requested.connect(self._on_edit_region)
        self._main_window.settings_requested.connect(self._open_settings)
        self._main_window.settings_saved.connect(self._on_settings_saved)
        self._main_window.settings_logout_requested.connect(self._do_logout)
        self._main_window.region_threshold_changed.connect(self._on_threshold_changed)
        self._main_window.region_delay_changed.connect(self._on_delay_changed)
        self._main_window.test_stall_requested.connect(self._on_test_stall)
        self._main_window.test_complete_requested.connect(self._on_test_complete)
        # 기존 영역 복원
        self._restore_regions()

    def run(self) -> int:
        """애플리케이션을 실행한다."""
        log.info("ProgressEye 시작")

        # 최소 버전 체크 (Firestore — 인증 불필요)
        min_ver = get_min_pc_version()
        if min_ver and self._is_outdated(APP_VERSION, min_ver):
            log.warning("업데이트 필요: 현재=%s 최소=%s", APP_VERSION, min_ver)
            self._show_update_required(min_ver)
            return 0

        is_first = not self._config.get("auth.uid", "")
        if not self._try_auto_login():
            self._ensure_login()
        if is_first and self._config.get("auth.uid", ""):
            self._show_welcome()
        self._main_window.show()
        return self._app.exec()

    def _try_auto_login(self) -> bool:
        """저장된 refresh_token으로 자동 로그인을 시도한다."""
        try:
            result = self._token_manager.load_tokens(self._firebase_auth)
        except AuthError as exc:
            log.warning("자동 로그인 실패: %s", exc)
            return False
        except Exception as exc:
            log.warning("자동 로그인 중 알 수 없는 오류: %s", exc)
            return False

        if result is None:
            return False

        self._firebase_id_token = result["id_token"]
        self._token_expires_at = time.time() + 3600
        uid = result.get("uid", "")
        email = result.get("email", "")
        if uid:
            self._config.set("auth.uid", uid)
        if email:
            self._config.set("auth.email", email)
        device_id = str(self._config.get("auth.device_id", ""))
        if uid and device_id:
            self._init_firebase(uid, device_id, result["id_token"])
        log.info("자동 로그인 성공")
        return True

    def _ensure_login(self) -> None:
        """로그인 실패 시 사용자에게 재시도 기회를 제공한다."""
        while True:
            try:
                self._do_login()
                return
            except AuthError as exc:
                retry = self._show_login_error(str(exc))
                if not retry:
                    log.warning("로그인 취소 - 비로그인 모드로 계속 진행")
                    return
            except Exception as exc:
                retry = self._show_login_error(
                    t("login_unknown_error").format(error=exc)
                )
                if not retry:
                    log.warning("로그인 취소 - 비로그인 모드로 계속 진행")
                    return

    def _show_login_error(self, message: str) -> bool:
        """로그인 에러 다이얼로그를 표시하고 재시도 여부를 반환한다."""
        dialog = QMessageBox(self._main_window)
        dialog.setWindowTitle(t("login_failed_title"))
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setText(t("login_failed_message"))
        dialog.setInformativeText(message)
        dialog.setStandardButtons(
            QMessageBox.StandardButton.Retry | QMessageBox.StandardButton.Cancel
        )
        dialog.setDefaultButton(QMessageBox.StandardButton.Retry)
        return dialog.exec() == QMessageBox.StandardButton.Retry

    @staticmethod
    def _is_outdated(current: str, minimum: str) -> bool:
        """버전 문자열을 비교하여 현재 버전이 최소 버전 미만인지 확인한다."""
        def parse(v: str) -> tuple[int, ...]:
            return tuple(int(x) for x in v.split(".") if x.isdigit())
        return parse(current) < parse(minimum)

    def _show_update_required(self, min_version: str) -> None:
        """업데이트 필요 다이얼로그를 표시하고 앱을 종료한다."""
        dialog = QMessageBox(self._main_window)
        dialog.setWindowTitle(t("update_required_title"))
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setText(t("update_required_message"))
        dialog.setInformativeText(
            t("update_required_detail").format(
                current=APP_VERSION, minimum=min_version
            )
        )
        dialog.addButton(t("update_required_quit"), QMessageBox.ButtonRole.AcceptRole)
        dialog.exec()
        self._do_quit()

    def _show_device_conflict(self, other_device_id: str) -> None:
        """다른 PC에서 사용 중인 경우 안내 다이얼로그를 표시한다."""
        dialog = QMessageBox(self._main_window)
        dialog.setWindowTitle(t("device_conflict_title"))
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setText(t("device_conflict_message"))
        dialog.setInformativeText(
            t("device_conflict_detail").format(device=other_device_id)
        )
        take_over = dialog.addButton(
            t("device_conflict_takeover"), QMessageBox.ButtonRole.AcceptRole
        )
        dialog.addButton(t("device_conflict_cancel"), QMessageBox.ButtonRole.RejectRole)
        dialog.exec()
        if dialog.clickedButton() == take_over:
            log.info(
                "디바이스 강제 전환: %s → %s",
                other_device_id,
                self._config.get("auth.device_id"),
            )
            if self._device_manager:
                self._device_manager.set_active_device()

    def _do_login(self) -> None:
        """Google OAuth와 Firebase Auth를 통해 로그인한다."""
        google_result = self._google_oauth.sign_in()
        firebase_result = self._firebase_auth.sign_in_with_google(
            google_result["id_token"]
        )
        self._firebase_id_token = firebase_result["id_token"]
        self._token_expires_at = time.time() + 3600

        uid = firebase_result["uid"]
        email = firebase_result["email"]

        device_id = str(self._config.get("auth.device_id", ""))
        if not device_id:
            device_id = f"pc_{uuid.uuid4().hex[:8]}"
            self._config.set("auth.device_id", device_id)
        self._config.set("auth.uid", uid)
        self._config.set("auth.email", email)

        self._token_manager.save_tokens(
            uid=uid,
            email=email,
            display_name=firebase_result.get("display_name", ""),
            refresh_token=firebase_result["refresh_token"],
            id_token=firebase_result["id_token"],
        )
        self._init_firebase(uid, device_id, firebase_result["id_token"])
        log.info("로그인 완료: %s (%s)", email, uid)

    def _init_firebase(self, uid: str, device_id: str, id_token: str) -> None:
        """Firebase 서비스를 초기화하고 기기를 등록한다."""

        def get_token() -> str:
            """만료 임박 시 자동 갱신하여 유효한 토큰을 반환한다."""
            if self._firebase_id_token and time.time() < self._token_expires_at - 300:
                return self._firebase_id_token
            # 만료 5분 전 또는 이미 만료 → refresh
            try:
                refresh = self._token_manager.load_refresh_token()
                if refresh:
                    result = self._firebase_auth.refresh_token(refresh)
                    self._firebase_id_token = result["id_token"]
                    self._token_expires_at = time.time() + 3600
                    self._token_manager.save_tokens(
                        uid=self._config.get("auth.uid", ""),
                        email=self._config.get("auth.email", ""),
                        display_name=self._token_manager.load_display_name() or "",
                        refresh_token=result["refresh_token"],
                        id_token=result["id_token"],
                    )
                    log.info("Firebase 토큰 자동 갱신 완료")
                    return self._firebase_id_token
            except Exception as exc:
                log.warning("Firebase 토큰 자동 갱신 실패: %s", exc)
            return self._firebase_id_token or id_token

        self._realtime_db = RealtimeDB(
            db_url="https://progresseye-49244-default-rtdb.firebaseio.com",
            get_id_token=get_token,
        )
        self._device_manager = DeviceManager(self._realtime_db, uid, device_id)
        try:
            self._device_manager.register()
            log.info("Firebase 기기 등록 완료: %s", device_id)
        except Exception as exc:
            log.warning("Firebase 기기 등록 실패: %s", exc)

        # 플랜 확인 + Free 단일기기 강제
        try:
            plan = self._device_manager.get_user_plan()
            self._config.set("plan", plan)
            log.info("유저 플랜: %s", plan)
            if plan == "free":
                active = self._device_manager.get_active_device()
                if active and active != device_id:
                    if self._device_manager.is_other_device_online(active):
                        log.warning("다른 PC에서 사용 중: %s", active)
                        self._show_device_conflict(active)
                        return
                self._device_manager.set_active_device()
        except Exception as exc:
            log.debug("플랜/디바이스 확인 실패: %s", exc)

        # 프로필 저장
        try:
            profile_data = {
                "email": self._config.get("auth.email", ""),
                "displayName": self._token_manager.load_display_name() or "",
                "lastLoginAt": int(time.time() * 1000),
            }
            self._realtime_db.patch(f"users/{uid}/profile", profile_data)
        except Exception as exc:
            log.debug("프로필 저장 실패: %s", exc)

        # 하트비트 타이머 (60초)
        if self._heartbeat_timer:
            self._heartbeat_timer.stop()
        heartbeat_timer = QTimer()
        heartbeat_timer.timeout.connect(self._send_heartbeat)
        heartbeat_timer.start(_HEARTBEAT_INTERVAL_MS)
        self._heartbeat_timer = heartbeat_timer

        # 시작 직후 로그인/Firebase 초기화 부하가 크므로 샘플러 시작을 지연한다.
        QTimer.singleShot(_SAMPLER_START_DELAY_MS, warmup_cpu_percent)

        # Firebase Storage 초기화
        self._firebase_storage = FirebaseStorage(
            bucket="progresseye-49244.firebasestorage.app",
            get_id_token=get_token,
        )

        # 명령 리스너 초기화
        if self._command_listener:
            self._command_listener.stop()
        self._command_listener = CommandListener(
            db_url="https://progresseye-49244-default-rtdb.firebaseio.com",
            get_id_token=get_token,
            command_queue=self._command_queue,
        )
        self._command_listener.start(uid)

    def _send_heartbeat(self) -> None:
        """하트비트 전송 (모니터링 비활성 시에만 동작)."""
        if self._scheduler.is_running:
            return  # 모니터링 중이면 batch sync가 lastSeen 갱신
        if self._device_manager:
            try:
                self._device_manager.heartbeat()
                self._sync_stats_if_due()
            except Exception as exc:
                log.debug("하트비트 전송 실패: %s", exc)

    def _sync_stats_if_due(self) -> None:
        """하드웨어 stats를 최소 1분 간격으로만 RTDB에 전송한다."""
        if not self._device_manager:
            return
        now_ms = int(time.time() * 1000)
        if now_ms - self._last_stats_synced_at_ms < _STATS_SYNC_INTERVAL_MS:
            return
        stats = collect_stats()
        if stats:
            self._device_manager.sync_stats(stats)
            self._last_stats_synced_at_ms = now_ms

    def _notify(self, message: str) -> None:
        """트레이 제거 버전: 알림은 로그로 대체한다."""
        log.info("[알림] %s", message)

    def _set_runtime_hint(self, text: str) -> None:
        """트레이 툴팁 제거 버전: 상태 힌트를 로그로 남긴다."""
        log.debug("[상태] %s", text)

    def _process_queued_actions(self) -> None:
        """큐에 쌍인 액션을 메인 스레드에서 실행한다.

        pystray/threading.Timer 등 비-Qt 스레드에서 큐에 넣은 작업을
        50ms 주기로 폴링하여 Qt 메인 스레드에서 실행한다.
        """
        while not self._action_queue.empty():
            try:
                action = self._action_queue.get_nowait()
                action()
            except queue.Empty:
                break

    def _process_commands(self) -> None:
        """모바일 명령 큐를 폴링하여 처리한다."""
        while not self._command_queue.empty():
            try:
                cmd = self._command_queue.get_nowait()
            except queue.Empty:
                break
            cmd_type = cmd.get("type")
            if not isinstance(cmd_type, str):
                continue
            if not self._is_fresh_command(cmd_type, cmd.get("data")):
                continue
            log.info("[CMD] mobile command received: type=%s", cmd_type)
            if cmd_type == "screenshot":
                self._handle_screenshot_command()
            elif cmd_type == "monitor":
                data = cmd.get("data", {})
                action = data.get("action") if isinstance(data, dict) else None
                if action in ("start", "stop"):
                    # 모니터링 토글 (시작/정지)
                    if action == "start" and not self._scheduler.is_running:
                        self._toggle_monitoring()
                    elif action == "stop" and self._scheduler.is_running:
                        self._toggle_monitoring()
            elif cmd_type == "forceLogout":
                log.info("[CMD] 원격 강제 로그아웃 수신 — 앱을 종료합니다.")
                self._do_logout()

    def _is_fresh_command(self, cmd_type: str, data_obj: object) -> bool:
        """재전송/재연결 중복 명령과 오래된 명령을 필터링한다."""
        if not isinstance(data_obj, dict):
            log.warning("[CMD] invalid payload type, dropped: %s", cmd_type)
            return False

        ts_raw = data_obj.get("ts")
        cmd_id_raw = data_obj.get("cmdId")

        cmd_ts: int | None = None
        if isinstance(ts_raw, (int, float)):
            cmd_ts = int(ts_raw)
        elif isinstance(ts_raw, str) and ts_raw.isdigit():
            cmd_ts = int(ts_raw)

        if cmd_ts is not None and cmd_ts > 1_000_000_000_000:
            cmd_ts //= 1000

        now_sec = int(time.time())
        if cmd_ts is not None:
            if cmd_ts < now_sec - 3600 or cmd_ts > now_sec + 120:
                log.warning(
                    "[CMD] stale command dropped: type=%s ts=%s", cmd_type, cmd_ts
                )
                return False

        cmd_id = cmd_id_raw.strip() if isinstance(cmd_id_raw, str) else ""
        if cmd_id:
            seen_at = self._processed_command_ids.get(cmd_id)
            if seen_at is not None and (time.time() - seen_at) < 3600:
                log.info(
                    "[CMD] duplicate cmdId dropped: type=%s cmdId=%s", cmd_type, cmd_id
                )
                return False
            self._processed_command_ids[cmd_id] = time.time()

            if len(self._processed_command_ids) > 512:
                cutoff = time.time() - 3600
                self._processed_command_ids = {
                    key: seen
                    for key, seen in self._processed_command_ids.items()
                    if seen >= cutoff
                }
            return True

        if cmd_ts is None:
            log.warning("[CMD] missing ts/cmdId dropped: type=%s", cmd_type)
            return False

        last_ts = self._last_command_ts_by_type.get(cmd_type)
        if last_ts is not None and cmd_ts <= last_ts:
            log.info("[CMD] replayed ts dropped: type=%s ts=%s", cmd_type, cmd_ts)
            return False

        self._last_command_ts_by_type[cmd_type] = cmd_ts
        return True

    def _handle_screenshot_command(self) -> None:
        """모바일 스크린샷 요청: 전체 화면 캡처 → JPEG → Storage 업로드 → RTDB URL 기록."""
        import hashlib
        import io
        import mss as mss_lib

        if not self._firebase_storage or not self._realtime_db:
            log.warning("스크린샷 명령 무시: Firebase 미초기화")
            return

        uid = str(self._config.get("auth.uid", ""))
        device_id = str(self._config.get("auth.device_id", ""))
        try:
            log.info("[SCREENSHOT] capture start")
            with mss_lib.mss() as sct:
                monitor = sct.monitors[0]
                shot = sct.grab(monitor)
                img = PILImage.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")

            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=70)
            jpeg_bytes = buf.getvalue()
            jpeg_hash = hashlib.md5(jpeg_bytes).hexdigest()

            ts = int(time.time())
            cached = self._screenshot_cache.get(device_id)

            if cached and cached[0] == jpeg_hash:
                # 화면 변경 없음 — 업로드 스킵, 기존 URL 재사용
                download_url = cached[1]
                log.info("[SCREENSHOT] 화면 변경 없음, 업로드 스킵")
            else:
                # 화면 변경됨 — 업로드
                storage_path = f"screenshots/{uid}/{device_id}/latest.jpg"
                download_url = self._firebase_storage.upload_jpeg(
                    storage_path, jpeg_bytes
                )
                self._screenshot_cache[device_id] = (jpeg_hash, download_url)
                log.info("[SCREENSHOT] 업로드 완료: %s", storage_path)

            self._realtime_db.patch(
                f"users/{uid}/devices/{device_id}/screenshots",
                {"latest": {"url": download_url, "ts": ts}},
            )
            log.info("스크린샷 처리 완료 (ts=%d)", ts)
        except Exception as exc:
            log.warning("스크린샷 처리 실패: %s", exc)
        finally:
            try:
                if self._realtime_db and uid:
                    self._realtime_db.delete(f"users/{uid}/commands/screenshot")
            except Exception:
                pass

    def _restore_regions(self) -> None:
        """설정에 저장된 영역을 복원한다."""
        for region in self._config.regions:
            enabled = region.get("enabled", True)
            self._main_window.add_region_display(
                region["id"],
                region.get("label", region["id"]),
                region_type=region.get("type", "bar"),
                enabled=enabled,
                alert_threshold=region.get("alert_threshold", 100),
                alert_delay_minutes=region.get("alert_delay_minutes", 0),
            )
            # 로컬 템플릿 이미지 복원
            tpl = self._load_template(region["id"])
            if tpl is not None:
                self._template_images[region["id"]] = tpl

    def _start_area_selection(self) -> None:
        """프로그래스바 영역 선택을 시작한다."""
        self._selection_mode = "bar"
        QTimer.singleShot(0, self._do_start_area_selection)

    def _start_ocr_area_selection(self) -> None:
        """숫자(OCR) 영역 선택을 시작한다."""
        self._selection_mode = "ocr"
        QTimer.singleShot(0, self._do_start_area_selection)

    def _do_start_area_selection(self) -> None:
        """실제 영역 선택 시작 (메인 스레드)."""
        log.info("영역 선택 시작 (mode=%s)", self._selection_mode)
        if self._area_selector is not None:
            try:
                self._area_selector.hide()
            except RuntimeError:
                pass
            try:
                self._area_selector.deleteLater()
            except RuntimeError:
                pass
            self._area_selector = None
        QTimer.singleShot(200, self._create_area_selector)

    def _create_area_selector(self) -> None:
        """AreaSelector를 생성하고 표시한다."""
        self._area_selector = AreaSelector()
        self._area_selector.area_selected.connect(self._on_area_selected)
        self._area_selector.cancelled.connect(self._on_area_cancelled)
        self._area_selector.show()

    def _on_area_selected(self, area: dict) -> None:
        """영역 선택 완료 — 모드에 따라 바/OCR 플로우 분기."""
        log.info("영역 선택됨 (mode=%s): %s", self._selection_mode, area)

        # 작업 수정 중이면 기존 영역 업데이트
        if self._editing_region_id is not None:
            editing_id = self._editing_region_id
            self._editing_region_id = None
            self._update_region_area(editing_id, area)
            return

        if self._selection_mode == "ocr":
            self._on_ocr_area_selected(area)
        else:
            self._on_bar_area_selected(area)

    def _on_bar_area_selected(self, area: dict) -> None:
        """프로그래스바 영역 — 바 탐지 → 프리뷰 → 등록."""
        try:
            image = self._capturer.capture(area)
        except Exception as e:
            log.error("영역 캐처 실패: %s", e)
            return
        bar_region, result = self._smart_bar_analyze(image)
        bar_image = image.crop(bar_region.bbox) if bar_region else image
        qimage = self._pil_to_qimage(image)
        dialog = BarPreviewDialog(
            image=qimage,
            full_image=image,
            bar_image=bar_image,
            detected_progress=result.progress,
            bar_region=bar_region,
            debug_mode=self._debug_mode,
        )

        if dialog.exec():
            self._task_counter += 1
            region_id = f"task_{self._task_counter:03d}"
            # bar_region 오프셋 저장 (원본 영역 내 바 위치)
            final_br = dialog.bar_region
            if final_br:
                direction = final_br.direction
                bar_crop = {
                    "bar_left": final_br.left,
                    "bar_top": final_br.top,
                    "bar_right": final_br.right,
                    "bar_bottom": final_br.bottom,
                }
            else:
                direction = "horizontal"
                bar_crop = {}
            region = {
                "id": region_id,
                "label": dialog.task_name
                or t("default_task_name").format(n=self._task_counter),
                "type": "bar",
                "monitor": area.get("monitor", 0),
                "x": area["x"],
                "y": area["y"],
                "width": area["width"],
                "height": area["height"],
                "direction": direction,
                **bar_crop,
            }
            self._config.add_region(region)
            self._main_window.add_region_display(
                region_id, region["label"], region_type="bar"
            )
            final_progress = dialog.progress
            self._main_window.update_progress(
                region_id, final_progress, region["label"]
            )
            if self._scheduler.is_running:
                self._scheduler.add_region(region)
            log.info("바 영역 등록: %s (%.1f%%)", region_id, final_progress)
            # 템플릿 이미지 저장 (원본 영역 전체 — 이미지 변경 감지용)
            self._save_template(region_id, image)
            # Firebase에 라벨 전송 (등록 시 1회)
            if self._device_manager:
                try:
                    self._device_manager.set_task_label(region_id, region["label"])
                except Exception:
                    pass
        elif dialog.reselect_requested:
            log.info("미리보기에서 재선택 요청")
            QTimer.singleShot(100, self._start_area_selection)

    def _on_ocr_area_selected(self, area: dict) -> None:
        """OCR 숫자 영역 — OCR 탐지 → 프리뷰 → 등록."""
        try:
            image = self._capturer.capture(area)
        except Exception as e:
            log.error("영역 캐처 실패: %s", e)
            return

        ocr_results = self._ocr_reader.find_percentages(image)
        detected_progress = None
        if ocr_results:
            best = max(ocr_results, key=lambda r: r.confidence)
            detected_progress = best.progress

        qimage = self._pil_to_qimage(image)
        dialog = OcrPreviewDialog(
            image=qimage,
            ocr_results=ocr_results,
            detected_progress=detected_progress,
        )

        if dialog.exec():
            self._task_counter += 1
            region_id = f"task_{self._task_counter:03d}"
            region = {
                "id": region_id,
                "label": dialog.task_name
                or t("default_task_name").format(n=self._task_counter),
                "type": "ocr",
                "monitor": area.get("monitor", 0),
                "x": area["x"],
                "y": area["y"],
                "width": area["width"],
                "height": area["height"],
            }
            self._config.add_region(region)
            self._main_window.add_region_display(
                region_id, region["label"], region_type="ocr"
            )
            final_progress = dialog.progress
            self._main_window.update_progress(
                region_id, final_progress, region["label"]
            )
            if self._scheduler.is_running:
                self._scheduler.add_region(region)
            log.info("OCR 영역 등록: %s (%.1f%%)", region_id, final_progress)
            # 템플릿 이미지 저장 (이미지 변경 감지용)
            self._save_template(region_id, image)
            # Firebase에 라벨 전송 (등록 시 1회)
            if self._device_manager:
                try:
                    self._device_manager.set_task_label(region_id, region["label"])
                except Exception:
                    pass
        elif dialog.reselect_requested:
            log.info("미리보기에서 재선택 요청")
            QTimer.singleShot(100, self._start_ocr_area_selection)

    def _on_area_cancelled(self) -> None:
        """영역 선택 취소."""
        log.info("영역 선택 취소됨")
        if self._area_selector is not None:
            self._area_selector.deleteLater()
            self._area_selector = None

    def _on_region_toggled(self, region_id: str, enabled: bool) -> None:
        """영역 체크박스 토글 시 호출."""
        self._config.update_region(region_id, {"enabled": enabled})
        if self._scheduler.is_running:
            if enabled:
                # 활성화 — 스케줄러에 영역 추가
                for r in self._config.regions:
                    if r["id"] == region_id:
                        self._scheduler.add_region(r)
                        break
            else:
                # 비활성화 — 스케줄러에서 영역 제거
                self._scheduler.remove_region(region_id)
                # RTDB에 idle 상태 기록
                if self._device_manager:
                    self._device_manager.sync_tasks({region_id: {"s": "i"}})
        elif not enabled and self._device_manager:
            # 모니터링 미실행 중 비활성화 → RTDB에도 idle 기록
            self._device_manager.sync_tasks({region_id: {"s": "i"}})
        log.info("영역 토글: %s → %s", region_id, "활성" if enabled else "비활성")

    def _update_region_area(self, region_id: str, area: dict) -> None:
        """재선택된 영역으로 기존 작업의 좌표를 업데이트하고 프리뷰를 다시 열다."""
        try:
            new_image = self._capturer.capture(area)
        except Exception as exc:
            log.warning("재선택 캡처 실패: %s", exc)
            self._do_edit_region(region_id)
            return
        # bar_finder로 바 오프셋 초기 탐지
        bar_region = self._bar_finder.find(new_image)
        updates: dict = {
            "monitor": area.get("monitor", 0),
            "x": area["x"],
            "y": area["y"],
            "width": area["width"],
            "height": area["height"],
        }
        if bar_region and bar_region.confidence > 0:
            updates["direction"] = bar_region.direction
            updates["bar_left"] = bar_region.left
            updates["bar_top"] = bar_region.top
            updates["bar_right"] = bar_region.right
            updates["bar_bottom"] = bar_region.bottom
        self._config.update_region(region_id, updates)
        # 템플릿 = 원본 영역 전체
        self._save_template(region_id, new_image)
        # 스케줄러 영역도 갱신
        if self._scheduler.is_running:
            self._scheduler.remove_region(region_id)
            for r in self._config.regions:
                if r["id"] == region_id:
                    self._scheduler.add_region(r)
                    break
        log.info("영역 좌표 업데이트: %s", region_id)
        # 업데이트된 영역으로 편집 다이얼로그 다시 열기
        self._do_edit_region(region_id)

    def _on_region_deleted(self, region_id: str) -> None:
        """영역 삭제 요청 시 호출."""
        # 스케줄러에서 제거
        if self._scheduler.is_running:
            self._scheduler.remove_region(region_id)
        # config에서 제거
        self._config.remove_region(region_id)
        # UI에서 제거
        self._main_window.remove_region_display(region_id)
        # Firebase DB에서 제거
        if self._device_manager:
            try:
                self._device_manager.delete_task(region_id)
                log.info("Firebase DB 삭제: %s", region_id)
            except Exception as exc:
                log.warning("Firebase DB 삭제 실패 [%s]: %s", region_id, exc)
        # 배치에서도 제거
        self._pending_firebase_batch.pop(region_id, None)
        self._last_firebase_state.pop(region_id, None)
        self._last_synced_firebase_state.pop(region_id, None)
        self._completion_first_reached.pop(region_id, None)
        self._delete_template(region_id)
        log.info("영역 삭제: %s", region_id)

    def _open_settings(self) -> None:
        """설정 오버레이를 표시한다."""
        self._main_window.show_settings(
            interval=self._config.get("capture.interval_seconds", 30),
            language=self._config.get("language", "en"),
            email=self._config.get("auth.email", ""),
            freeze_minutes=self._config.get("freeze_detection.timeout_minutes", 5),
        )

    def _on_settings_saved(
        self,
        new_interval: int,
        new_lang: str,
        new_freeze: int,
    ) -> None:
        """설정 저장 시 반영한다."""
        current_interval = self._config.get("capture.interval_seconds", 30)
        current_lang = self._config.get("language", "en")
        current_freeze = self._config.get("freeze_detection.timeout_minutes", 5)
        if new_interval != current_interval:
            self._config.set("capture.interval_seconds", new_interval)
            self._scheduler.update_interval(new_interval)
            log.info("모니터링 간격 변경: %d초", new_interval)
        if new_lang != current_lang:
            self._config.set("language", new_lang)
            set_language(new_lang)
            self._main_window.refresh_texts()
            log.info("언어 변경: %s", new_lang)
        if new_freeze != current_freeze:
            self._config.set("freeze_detection.timeout_minutes", new_freeze)
            self._freeze_detector._timeout_seconds = new_freeze * 60
            log.info("프리징 감지 시간 변경: %d분", new_freeze)

    def _do_logout(self) -> None:
        """로그아웃: 토큰 삭제 → 모니터링 중지 → Firebase 정리 → 앱 종료."""
        log.info("로그아웃 시작")
        if self._scheduler.is_running:
            self._scheduler.stop()
            self._main_window.set_monitoring_state(False)
            self._set_display_required(False)
        if self._heartbeat_timer is not None:
            self._heartbeat_timer.stop()
            self._heartbeat_timer = None
        if self._command_listener:
            self._command_listener.stop_nowait()
            self._command_listener = None

        # Firebase 정리를 별도 스레드에서 수행 (메인 스레드 블로킹 방지)
        dm = self._device_manager
        self._device_manager = None
        self._realtime_db = None
        self._firebase_id_token = None

        def _cleanup_firebase() -> None:
            if dm is not None:
                try:
                    if self._config.get("plan", "free") == "free":
                        dm.clear_active_device()
                    dm.set_offline()
                except Exception:
                    pass

        threading.Thread(target=_cleanup_firebase, daemon=True).start()

        try:
            self._token_manager.clear()
        except Exception as exc:
            log.warning("토큰 삭제 실패: %s", exc)
        self._config.set("auth.uid", "")
        self._config.set("auth.email", "")
        log.info("로그아웃 완료 — 앱 종료")
        # tray는 daemon 스레드 — _app.quit() 시 자동 종료
        self._do_quit()

    def _show_welcome(self) -> None:
        """최초 로그인 후 웰컴 설정 가이드를 표시한다."""
        self._main_window.show_settings(
            interval=self._config.get("capture.interval_seconds", 30),
            language=self._config.get("language", "en"),
            email=self._config.get("auth.email", ""),
            freeze_minutes=self._config.get("freeze_detection.timeout_minutes", 5),
            welcome_mode=True,
        )

    def _on_edit_region(self, region_id: str) -> None:
        """작업 수정 요청 — 기존 영역 데이터로 프리뷰 다이얼로그를 연다."""
        QTimer.singleShot(0, lambda: self._do_edit_region(region_id))

    def _do_edit_region(self, region_id: str) -> None:
        """실제 작업 수정 (메인 스레드)."""
        # 1. config에서 영역 정보 조회
        area = None
        for r in self._config.regions:
            if r["id"] == region_id:
                area = r
                break
        if area is None:
            return

        # 2. 템플릿 이미지 사용 (없으면 현재 화면 캡처 fallback)
        image = self._template_images.get(region_id) or self._load_template(region_id)
        if image is None:
            try:
                image = self._capturer.capture(area)
            except Exception as e:
                log.error("영역 캡처 실패: %s", e)
                return
        else:
            image = image.copy()  # 원본 템플릿 보호

        region_type = area.get("type", "bar")
        current_label = area.get("label", "")

        if region_type == "ocr":
            # OCR 타입: OcrPreviewDialog
            ocr_results = self._ocr_reader.find_percentages(image)
            detected_progress = None
            if ocr_results:
                best = max(ocr_results, key=lambda r: r.confidence)
                detected_progress = best.progress

            qimage = self._pil_to_qimage(image)
            dialog = OcrPreviewDialog(
                image=qimage,
                ocr_results=ocr_results,
                detected_progress=detected_progress,
            )
            dialog._task_name_input.setText(current_label)

            if dialog.exec():
                new_label = dialog.task_name or current_label
                self._config.update_region(region_id, {"label": new_label})
                self._main_window.update_progress(region_id, dialog.progress, new_label)
                log.info("OCR 영역 수정: %s → %s", region_id, new_label)
                # 템플릿 이미지 갱신 (수정 시 재캡처된 이미지로)
                self._save_template(region_id, image)
                if self._device_manager:
                    try:
                        self._device_manager.set_task_label(region_id, new_label)
                    except Exception:
                        pass
            elif dialog.reselect_requested:
                # 재선택 — 영역 선택 후 기존 작업 업데이트
                self._editing_region_id = region_id
                QTimer.singleShot(100, self._start_ocr_area_selection)
        else:
            # 바 타입: BarPreviewDialog
            bar_region, result = self._smart_bar_analyze(image)
            bar_image = image.crop(bar_region.bbox) if bar_region else image

            qimage = self._pil_to_qimage(image)
            dialog = BarPreviewDialog(
                image=qimage,
                full_image=image,
                bar_image=bar_image,
                detected_progress=result.progress,
                bar_region=bar_region,
                debug_mode=self._debug_mode,
            )
            dialog._task_name_input.setText(current_label)

            if dialog.exec():
                new_label = dialog.task_name or current_label
                updates: dict = {"label": new_label}
                final_br = dialog.bar_region
                if final_br:
                    updates["direction"] = final_br.direction
                    updates["bar_left"] = final_br.left
                    updates["bar_top"] = final_br.top
                    updates["bar_right"] = final_br.right
                    updates["bar_bottom"] = final_br.bottom
                self._config.update_region(region_id, updates)
                self._main_window.update_progress(region_id, dialog.progress, new_label)
                log.info("바 영역 수정: %s → %s", region_id, new_label)
                # 템플릿은 변경하지 않음 (원본 영역 유지)
                if self._device_manager:
                    try:
                        self._device_manager.set_task_label(region_id, new_label)
                    except Exception:
                        pass
            elif dialog.reselect_requested:
                # 재선택 — 영역 선택 후 기존 작업 업데이트
                self._editing_region_id = region_id
                QTimer.singleShot(100, self._start_area_selection)

    def _show_region_view(self, region_id: str) -> None:
        """영역의 바 탐지 결과를 전체 화면에 표시한다."""
        QTimer.singleShot(0, lambda: self._do_show_region_view(region_id))

    def _do_show_region_view(self, region_id: str) -> None:
        """실제 뷰어 표시 (메인 스레드)."""
        # 1. config에서 영역 정보 조회
        area = None
        for r in self._config.regions:
            if r["id"] == region_id:
                area = r
                break
        if area is None:
            return

        # 2. 영역 캕처
        try:
            image = self._capturer.capture(area)
        except Exception as e:
            log.error("영역 캕처 실패: %s", e)
            return

        # 3. 영역 타입에 따라 분석 분기
        region_type = area.get("type", "bar")
        region_rect = self._mss_to_qt_rect(area)
        bar_qt_rect = None
        if region_type == "ocr":
            # OCR: 숫자% 읽기
            progress_val = self._ocr_reader.read_progress(image)
            if progress_val is None:
                progress_val = 0.0
        else:
            # 바 — 원본 영역 내 bar 오프셋으로 크롭하여 분석
            bar_image = image.crop((
                area.get("bar_left", 0),
                area.get("bar_top", 0),
                area.get("bar_right", image.width),
                area.get("bar_bottom", image.height),
            ))
            direction = area.get("direction", "horizontal")
            result = self._analyzer.analyze(bar_image, direction=direction)
            progress_val = result.progress
            # 바 영역 사각형 (화면 좌표)
            bar_area = {
                "monitor": area.get("monitor", 0),
                "x": area["x"] + area.get("bar_left", 0),
                "y": area["y"] + area.get("bar_top", 0),
                "width": area.get("bar_right", area["width"]) - area.get("bar_left", 0),
                "height": area.get("bar_bottom", area["height"]) - area.get("bar_top", 0),
            }
            bar_qt_rect = self._mss_to_qt_rect(bar_area)
        # 4. 뷰어 생성 + 표시
        if self._region_viewer is not None:
            try:
                self._region_viewer.close()
            except RuntimeError:
                pass

        self._region_viewer = RegionViewer(
            region_rect, bar_qt_rect, progress_val, region_type=region_type
        )
        self._region_viewer.closed.connect(self._on_region_viewer_closed)
        self._region_viewer.show()

    def _mss_to_qt_rect(self, area: dict) -> QRect:
        """mss 좌표를 Qt 위젯 좌표로 변환한다."""
        import mss as mss_lib

        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return QRect(area["x"], area["y"], area["width"], area["height"])

        virtual_geo = screen.virtualGeometry()

        try:
            with mss_lib.mss() as sct:
                full = sct.monitors[0]
                mon_idx = area.get("monitor", 0)

                if mon_idx > 0 and mon_idx < len(sct.monitors):
                    mon = sct.monitors[mon_idx]
                    mss_global_x = area["x"] + mon["left"]
                    mss_global_y = area["y"] + mon["top"]
                else:
                    mss_global_x = area["x"]
                    mss_global_y = area["y"]

                scale_x = virtual_geo.width() / full["width"]
                scale_y = virtual_geo.height() / full["height"]
                qt_x = int((mss_global_x - full["left"]) * scale_x)
                qt_y = int((mss_global_y - full["top"]) * scale_y)
                qt_w = int(area["width"] * scale_x)
                qt_h = int(area["height"] * scale_y)
                return QRect(qt_x, qt_y, qt_w, qt_h)
        except Exception:
            return QRect(area["x"], area["y"], area["width"], area["height"])

    def _on_region_viewer_closed(self) -> None:
        """뷰어 닫힘."""
        if self._region_viewer is not None:
            self._region_viewer.deleteLater()
            self._region_viewer = None

    def _toggle_monitoring(self) -> None:
        """모니터링 시작/정지 토글."""
        QTimer.singleShot(0, self._do_toggle_monitoring)

    def _auto_stop_monitoring(self) -> None:
        """모든 영역이 제외되어 모니터링을 자동 정지한다 (메인 스레드)."""
        if self._scheduler.is_running:
            self._scheduler.stop()
            self._main_window.set_monitoring_state(False)
            self._set_runtime_hint("ProgressEye - 대기 중")
            self._set_display_required(False)
            log.info("모니터링 자동 정지 (활성 영역 없음)")
            if self._device_manager:
                self._device_manager.set_monitoring(False)

    def _set_display_required(self, required: bool) -> None:
        """모니터 절전 방지를 설정/해제한다.

        모니터링 중에는 ES_DISPLAY_REQUIRED | ES_CONTINUOUS를 설정하여
        Windows가 모니터를 절전모드로 전환하지 않도록 한다.
        모니터링 정지 시 ES_CONTINUOUS만 설정하여 정상 절전으로 복귀한다.
        """
        try:
            if required:
                # ES_CONTINUOUS | ES_DISPLAY_REQUIRED | ES_SYSTEM_REQUIRED
                ctypes.windll.kernel32.SetThreadExecutionState(0x80000002 | 0x00000001)
                log.info("모니터 절전 방지 설정")
            else:
                # ES_CONTINUOUS only — 정상 절전 복귀
                ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
                log.info("모니터 절전 방지 해제")
        except Exception as exc:
            log.warning("SetThreadExecutionState 실패: %s", exc)

    def _do_toggle_monitoring(self) -> None:
        """실제 모니터링 토글 (메인 스레드)."""
        if self._scheduler.is_running:
            self._scheduler.stop()
            self._main_window.set_monitoring_state(False)
            self._set_display_required(False)
            self._set_runtime_hint("ProgressEye - 대기 중")
            log.info("모니터링 정지")
            if self._device_manager:
                self._device_manager.set_monitoring(False)
            # 모니터링 정지 시 템플릿 유지 (등록 시점 기준)
        else:
            regions = [r for r in self._config.regions if r.get("enabled", True)]
            if not regions:
                self._notify(t("no_checked_regions"))
                return
            interval = self._config.get("capture.interval_seconds", 30)
            self._freeze_detector.reset_all()
            self._alerted_regions.clear()
            self._post_completion_fails.clear()
            self._completion_first_reached.clear()
            self._last_firebase_state.clear()
            self._last_synced_firebase_state.clear()
            self._pending_firebase_batch.clear()
            self._scheduler.start(regions, interval)
            self._main_window.set_monitoring_state(True, interval)
            self._set_runtime_hint("ProgressEye - 모니터링 중")
            log.info("모니터링 시작 (%d개 영역, %d초 주기)", len(regions), interval)
            self._set_display_required(True)
            if self._device_manager:
                self._device_manager.set_monitoring(True)
                # 미체크(비활성) 작업을 idle 상태로 RTDB에 기록
                disabled = [
                    r for r in self._config.regions if not r.get("enabled", True)
                ]
                if disabled:
                    idle_batch = {r["id"]: {"s": "i"} for r in disabled}
                    self._device_manager.sync_tasks(idle_batch)
            # 템플릿 이미지가 없는 영역은 현재 화면으로 템플릿 생성 (앱 재시작 후 복원된 영역)
            for r in regions:
                rid = r["id"]
                if rid not in self._template_images:
                    try:
                        tpl_image = self._capturer.capture(r)
                        self._save_template(rid, tpl_image)
                        log.debug("[모니터링 시작] %s 템플릿 이미지 생성", rid)
                    except Exception as exc:
                        log.debug("[모니터링 시작] %s 템플릿 생성 실패: %s", rid, exc)

    def _on_capture(self, region_id: str, image: PILImage.Image) -> None:
        """캐처 콜백 — 분석 + UI 업데이트.

        Timer 스레드에서 호출되므로 Queue로 메인 스레드 UI 업데이트를 보장한다.
        """
        # 영역 설정 찾기
        region_config = None
        for r in self._config.regions:
            if r["id"] == region_id:
                region_config = r
                break
        if region_config is None:
            log.warning("영역 설정을 찾을 수 없음: %s", region_id)
            return
        label = region_config.get("label", region_id)
        # 영역 타입에 따라 분석 분기
        region_type = region_config.get("type", "bar")

        # ── 이미지 변경 감지 ──
        IMAGE_CHANGE_THRESHOLD = 0.3
        if region_id not in self._template_images:
            # 템플릿 없음 (영역 등록 전 복원된 경우) — 유사도 검사 생략
            log.debug("[%s] 템플릿 이미지 없음 — 유사도 검사 생략", region_id)
        else:
            try:
                similarity = self._check_image_similarity(
                    self._template_images[region_id], image
                )
            except Exception as exc:
                log.warning("[%s] 이미지 유사도 계산 실패: %s", region_id, exc)
                similarity = 1.0  # 실패 시 유사하다고 간주하고 모니터링 계속
            log.info(
                "[%s] 이미지 유사도: %.4f (threshold: %.1f)",
                region_id,
                similarity,
                IMAGE_CHANGE_THRESHOLD,
            )
            if similarity < IMAGE_CHANGE_THRESHOLD:
                last_progress = self._last_firebase_state.get(region_id, {}).get("p", 0)
                threshold = region_config.get("alert_threshold", 100)
                if last_progress >= threshold - 10:
                    # 완료 근접 → 완료 처리
                    log.info(
                        "[이미지 변경] %s — 완료 근접 (%.1f%%) → 완료 처리 (유사도: %.2f)",
                        label,
                        last_progress,
                        similarity,
                    )
                    self._alerted_regions[region_id] = last_progress
                    complete_msg = t("image_changed_completed").format(
                        label=label, progress=last_progress
                    )
                    self._action_queue.put(lambda _msg=complete_msg: self._notify(_msg))
                    if self._device_manager:
                        self._device_manager.push_alert(
                            "image_change", "ProgressEye", complete_msg
                        )
                    # 완료 처리된 작업은 모니터링 중지 (반복 알림 방지)
                    self._scheduler.remove_region(region_id)
                    if self._scheduler.region_count == 0:
                        log.info("모든 영역이 모니터링에서 제외됨 — 자동 정지")
                        self._action_queue.put(self._auto_stop_monitoring)
                else:
                    # 경고 + 해당 영역 모니터링 중지
                    log.warning(
                        "[이미지 변경] %s — 화면 크게 변경 (유사도: %.2f, 진행률: %.1f%%) → 모니터링 중지",
                        label,
                        similarity,
                        last_progress,
                    )
                    warn_msg = t("image_changed_warning").format(label=label)
                    stopped_msg = t("image_changed_stopped")
                    self._action_queue.put(lambda _msg=warn_msg: self._notify(_msg))
                    if self._device_manager:
                        self._device_manager.push_alert(
                            "image_change", "ProgressEye", warn_msg
                        )
                    # UI에 경고 표시 + 체크 해제
                    self._action_queue.put(
                        lambda _id=region_id, _m=stopped_msg: (
                            self._main_window.set_region_warning(_id, _m)
                        )
                    )
                    self._config.update_region(region_id, {"enabled": False})
                    self._scheduler.remove_region(region_id)
                    # 모든 영역이 제외되면 모니터링 자동 정지
                    if self._scheduler.region_count == 0:
                        log.info("모든 영역이 모니터링에서 제외됨 — 자동 정지")
                        self._action_queue.put(self._auto_stop_monitoring)
                # 템플릿은 작업 삭제 시에만 삭제 — 여기서는 유지
                return

        if region_type == "ocr":
            # OCR로 숫자% 읽기
            progress = self._ocr_reader.read_progress(image, region_id=region_id)
            if progress is None:
                if region_id in self._alerted_regions:
                    # 완료 후 OCR 실패 → 창 닫힘 감지 (시나리오 2)
                    fails = self._post_completion_fails.get(region_id, 0)
                    if fails < 0:
                        return  # 이미 창 닫힘 알림 발송됨
                    fails += 1
                    self._post_completion_fails[region_id] = fails
                    log.debug("[%s] 완료 후 OCR 실패 (%d/3)", region_id, fails)
                    if fails >= 3:
                        alert_progress = self._alerted_regions[region_id]
                        log.info(
                            "[완료 시나리오] %s — 창 닫힘 감지 (%.1f%% 완료 후 OCR 실패 %d회)",
                            label,
                            alert_progress,
                            fails,
                        )
                        self._post_completion_fails[region_id] = -1  # 중복 알림 방지
                        closed_msg = t("completion_closed").format(label=label)
                        self._action_queue.put(
                            lambda _msg=closed_msg: self._notify(_msg)
                        )
                        if self._device_manager:
                            self._device_manager.push_alert(
                                "completion", "ProgressEye", closed_msg
                            )
                else:
                    log.warning("[%s] OCR 숫자 인식 실패", region_id)
                return
        else:
            # 바 — 원본 영역에서 bar 오프셋으로 크롭하여 분석 (bar_finder 불필요)
            bar_image = image.crop((
                region_config.get("bar_left", 0),
                region_config.get("bar_top", 0),
                region_config.get("bar_right", image.width),
                region_config.get("bar_bottom", image.height),
            ))
            direction = region_config.get("direction", "horizontal")
            result = self._analyzer.analyze(bar_image, direction=direction)
            progress = result.progress

        log.info("[%s] 진행률: %.1f%% (%s)", region_id, progress, region_type)

        # 멈춤 감지
        prev_frozen = False
        prev_state = self._freeze_detector.get_state(region_id)
        if prev_state is not None:
            prev_frozen = prev_state.is_frozen
        freeze_state = self._freeze_detector.update(region_id, progress)
        log.debug(
            "[%s] 프리징 체크 — progress=%.1f%%, prev_frozen=%s, is_frozen=%s, elapsed=%dm",
            region_id,
            progress,
            prev_frozen,
            freeze_state.is_frozen,
            freeze_state.frozen_minutes,
        )
        if prev_frozen and not freeze_state.is_frozen:
            log.info("[%s] 프리징 해제 — 진행률 변화 감지: %.1f%%", region_id, progress)

        # Firebase 배치 수집 (변화 있을 때만)
        status_code = (
            "c"
            if region_id in self._alerted_regions
            else ("f" if freeze_state.is_frozen else "r")
        )
        new_state = {"p": round(progress, 1), "s": status_code}
        prev_analyzed = self._last_firebase_state.get(region_id)
        self._last_firebase_state[region_id] = new_state
        prev_synced = self._last_synced_firebase_state.get(region_id)
        if self._should_sync_firebase_state(new_state, prev_synced, prev_analyzed):
            self._pending_firebase_batch[region_id] = new_state
            self._last_synced_firebase_state[region_id] = new_state
        self._set_runtime_hint(f"ProgressEye - {label}: {progress:.1f}%")
        # UI 업데이트 — 큐로 메인 스레드 전달
        self._action_queue.put(
            lambda _id=region_id, _p=progress, _l=label: (
                self._main_window.update_progress(_id, _p, _l)
            )
        )

        # ── 완료 후 시나리오 감지 ──
        threshold = region_config.get("alert_threshold", 100)
        if region_id in self._alerted_regions:
            alert_progress = self._alerted_regions[region_id]
            self._post_completion_fails.pop(
                region_id, None
            )  # OCR 성공 → 실패 카운터 리셋
            if alert_progress - progress >= 30.0:
                # 시나리오 1: 게이지 초기화 (큰 폭 하락)
                log.info(
                    "[완료 시나리오] %s — 게이지 초기화 (%.1f%% → %.1f%%)",
                    label,
                    alert_progress,
                    progress,
                )
                self._alerted_regions.pop(region_id, None)
                reset_msg = t("completion_reset").format(
                    label=label,
                    old=alert_progress,
                    new=progress,
                )
                self._action_queue.put(lambda _msg=reset_msg: self._notify(_msg))
                if self._device_manager:
                    self._device_manager.push_alert(
                        "completion", "ProgressEye", reset_msg
                    )
            elif progress >= threshold:
                # 시나리오 3: 완료 상태 유지
                log.debug("[완료 시나리오] %s — 완료 유지 (%.1f%%)", label, progress)
            else:
                # 임계값 아래 소폭 하락 → 재알람 허용
                log.info(
                    "[완료 시나리오] %s — 진행률 하락 (%.1f%% → %.1f%%), 재알람 대기",
                    label,
                    alert_progress,
                    progress,
                )
                self._alerted_regions.pop(region_id, None)

        # 완료 알람 체크
        log.debug(
            "[%s] 완료 체크 — progress=%.1f%%, threshold=%d%%, alerted=%s",
            region_id,
            progress,
            threshold,
            region_id in self._alerted_regions,
        )
        if region_id not in self._alerted_regions and progress >= threshold:
            # 타임스탬프 기반 완료 판정: delay분 동안 threshold 이상 유지 시 완료
            delay_minutes = region_config.get("alert_delay_minutes", 0)
            now = time.time()
            first = self._completion_first_reached.get(region_id)
            if first is None:
                self._completion_first_reached[region_id] = now
                first = now
                log.debug("[%s] 완료 기준 최초 도달 (%.1f%%)", region_id, progress)
            elapsed_min = (now - first) / 60.0
            log.debug(
                "[%s] 완료 확인 — %.1f%% >= %d%%, %.1f/%.0f분 경과",
                region_id, progress, threshold, elapsed_min, delay_minutes,
            )
            if elapsed_min >= delay_minutes:
                self._alerted_regions[region_id] = progress
                self._completion_first_reached.pop(region_id, None)
                alert_msg = t("alert_triggered").format(label=label, progress=progress)
                log.info("[완료 알람] %s", alert_msg)
                self._action_queue.put(
                    lambda _msg=alert_msg, _l=label: self._notify(_msg)
                )
                if self._device_manager:
                    self._device_manager.push_alert(
                        "completion", "ProgressEye", alert_msg
                    )
        else:
            # threshold 미달 또는 이미 완료 → 타이머 리셋
            self._completion_first_reached.pop(region_id, None)

        if freeze_state.is_frozen:
            log.warning(
                "[%s] 프리징 지속: %.1f%%에서 %d분째 멈춤",
                region_id,
                progress,
                freeze_state.frozen_minutes,
            )
            if not prev_frozen:
                # 프리징 시작 시점 — 트레이 알림 + RTDB 알림
                stall_msg = t("stall_detected").format(
                    label=label, minutes=freeze_state.frozen_minutes
                )
                self._action_queue.put(lambda _msg=stall_msg: self._notify(_msg))
                if self._device_manager:
                    self._device_manager.push_alert("stall", "ProgressEye", stall_msg)

    def _on_cycle_complete(self) -> None:
        """캡처 사이클 완료 — 배치 Firebase 전송 + 하드웨어 stats."""
        if not self._device_manager:
            return
        try:
            if self._pending_firebase_batch:
                self._device_manager.sync_tasks(dict(self._pending_firebase_batch))
            self._sync_stats_if_due()
        except Exception as exc:
            log.debug("Firebase 배치 전송 실패: %s", exc)
        self._pending_firebase_batch.clear()

    def _should_sync_firebase_state(
        self,
        new_state: dict,
        prev_synced: dict | None,
        prev_analyzed: dict | None,
    ) -> bool:
        """RTDB 전송량 절감을 위해 작은 진행률 흔들림은 배치 전송에서 제외한다.

        - 상태 코드(s) 변화는 항상 전송
        - 진행률(p)은 0.5% 이상 변할 때만 전송
        - 첫 샘플은 항상 전송
        """
        if prev_synced is None:
            return True

        new_status = str(new_state.get("s", "r"))
        prev_status = str(prev_synced.get("s", "r"))
        if new_status != prev_status:
            return True

        try:
            new_progress = float(new_state.get("p", 0.0))
            prev_progress = float(prev_synced.get("p", 0.0))
        except (TypeError, ValueError):
            return True

        if abs(new_progress - prev_progress) >= 0.5:
            return True

        # 분석값이 처음 생기는 시점에서는 전송 보장
        if prev_analyzed is None:
            return True

        return False

    def _on_threshold_changed(self, region_id: str, threshold: int) -> None:
        """완료 알람 임계값 변경 — config에 저장한다."""
        self._config.update_region(region_id, {"alert_threshold": threshold})
        # 임계값 변경시 알람 상태 초기화 (재알람 가능)
        self._alerted_regions.pop(region_id, None)
        log.info("[완료 알람] %s 임계값 변경: %d%%", region_id, threshold)

    def _on_delay_changed(self, region_id: str, minutes: int) -> None:
        """완료 확인 지연 시간 변경 — config에 저장한다."""
        self._config.update_region(region_id, {"alert_delay_minutes": minutes})
        # 지연 변경 시 타이머 리셋 (재측정)
        self._completion_first_reached.pop(region_id, None)
        log.info("[완료 알람] %s 지연 변경: %d분", region_id, minutes)

    def _on_test_stall(self, region_id: str) -> None:
        """프리징 테스트 — RTDB에 stall 알림을 기록한다 (FCM 파이프라인 검증용)."""
        if not self._device_manager:
            self._notify("Firebase not connected")
            return
        label = region_id
        for r in self._config.regions:
            if r["id"] == region_id:
                label = r.get("label", region_id)
                break
        stall_msg = t("stall_detected").format(label=label, minutes=5)
        self._device_manager.push_alert("stall", "ProgressEye", stall_msg)
        self._notify(f"[TEST] {stall_msg}")
        log.info("[TEST] 프리징 알림 전송: %s", region_id)

    def _on_test_complete(self, region_id: str) -> None:
        """완료 테스트 — RTDB에 completion 알림을 기록한다 (FCM 파이프라인 검증용)."""
        if not self._device_manager:
            self._notify("Firebase not connected")
            return
        label = region_id
        for r in self._config.regions:
            if r["id"] == region_id:
                label = r.get("label", region_id)
                break
        alert_msg = t("alert_triggered").format(label=label, progress=100.0)
        self._device_manager.push_alert("completion", "ProgressEye", alert_msg)
        self._notify(f"[TEST] {alert_msg}")
        log.info("[TEST] 완료 알림 전송: %s", region_id)

    def _quit(self) -> None:
        """애플리케이션을 종료한다."""
        log.info("ProgressEye 종료")
        self._scheduler.stop()
        self._set_display_required(False)
        self._capturer.close()
        stop_sampler()
        if self._heartbeat_timer:
            self._heartbeat_timer.stop()
        if self._command_listener:
            self._command_listener.stop_nowait()
            self._command_listener = None
        if self._device_manager:
            try:
                if self._config.get("plan", "free") == "free":
                    self._device_manager.clear_active_device()
                self._device_manager.set_offline()
            except Exception:
                pass
        self._action_queue.put(self._do_quit)

    def _do_quit(self) -> None:
        """앱 종료 (메인 스레드)."""
        self._poll_timer.stop()
        self._cmd_poll_timer.stop()
        setattr(self._main_window, "_really_quit", True)
        self._main_window.close()
        self._app.quit()

    def _save_template(self, region_id: str, image: PILImage.Image) -> None:
        """템플릿 이미지를 메모리 캐시 + 로컬 파일에 저장한다."""
        self._template_images[region_id] = image.copy()
        try:
            path = self._template_dir / f"{region_id}.png"
            image.save(str(path), "PNG")
            log.debug("템플릿 저장: %s", path)
        except Exception as exc:
            log.warning("템플릿 저장 실패 [%s]: %s", region_id, exc)

    def _load_template(self, region_id: str) -> PILImage.Image | None:
        """로컬 파일에서 템플릿 이미지를 로드한다."""
        path = self._template_dir / f"{region_id}.png"
        if not path.exists():
            return None
        try:
            img = PILImage.open(str(path))
            img.load()  # lazy loading 방지
            if img.mode != "RGB":
                img = img.convert("RGB")
            log.debug("템플릿 로드: %s", path)
            return img
        except Exception as exc:
            log.warning("템플릿 로드 실패 [%s]: %s", region_id, exc)
            return None

    def _delete_template(self, region_id: str) -> None:
        """템플릿 이미지를 메모리 캐시 + 로컬 파일에서 삭제한다."""
        self._template_images.pop(region_id, None)
        path = self._template_dir / f"{region_id}.png"
        try:
            if path.exists():
                path.unlink()
                log.debug("템플릿 삭제: %s", path)
        except Exception as exc:
            log.warning("템플릿 삭제 실패 [%s]: %s", region_id, exc)

    def _check_image_similarity(
        self, img1: PILImage.Image, img2: PILImage.Image
    ) -> float:
        """두 이미지의 유사도를 반환한다 (0.0~1.0).

        64x64 grayscale 다운스케일 후 numpy 상관계수로 비교.
        """
        import cv2
        import numpy as np

        size = (64, 64)
        arr1 = cv2.cvtColor(np.array(img1.resize(size)), cv2.COLOR_RGB2GRAY)
        arr2 = cv2.cvtColor(np.array(img2.resize(size)), cv2.COLOR_RGB2GRAY)
        flat1 = arr1.astype(np.float32).flatten()
        flat2 = arr2.astype(np.float32).flatten()
        # 표준편차가 0이면 동일 이미지 (단색)
        if np.std(flat1) < 1e-6 and np.std(flat2) < 1e-6:
            return 1.0
        # 한쪽만 표준편차 0이면 완전히 다른 이미지
        if np.std(flat1) < 1e-6 or np.std(flat2) < 1e-6:
            return 0.0
        corr = np.corrcoef(flat1, flat2)[0, 1]
        # NaN 방어 (corrcoef가 NaN 반환 시 0.0 처리)
        import math

        if math.isnan(corr):
            return 0.0
        return max(0.0, float(corr))

    def _smart_bar_analyze(
        self,
        image: PILImage.Image,
    ) -> tuple[BarRegion | None, AnalysisResult]:
        """바 분석: 원본 해상도로 분석.

        Returns:
            (bar_region, analysis_result) 튜플.
        """
        bar_region = self._bar_finder.find(image)
        bar_image = image.crop(bar_region.bbox) if bar_region else image
        direction = bar_region.direction if bar_region else "horizontal"
        result = self._analyzer.analyze(bar_image, direction=direction)

        return bar_region, result

    @staticmethod
    def _pil_to_qimage(pil_image: PILImage.Image) -> QImage:
        """PIL Image를 QImage로 변환한다."""
        if pil_image.mode != "RGB":
            pil_image = pil_image.convert("RGB")

        data = pil_image.tobytes("raw", "RGB")
        return QImage(
            data,
            pil_image.width,
            pil_image.height,
            pil_image.width * 3,
            QImage.Format.Format_RGB888,
        )


def main() -> None:
    """메인 함수. -d 옵션으로 디버그 로그 활성화."""
    debug_cli = "-d" in sys.argv or "--debug" in sys.argv
    is_packaged = bool(getattr(sys, "frozen", False)) or "__compiled__" in globals()
    debug_mode = debug_cli and not is_packaged
    if debug_cli and is_packaged:
        from utils.logger import log  # pyright: ignore[reportImplicitRelativeImport]

        log.info("패키징 빌드에서는 디버그 UI 옵션(-d/--debug)이 비활성화됩니다.")
    if debug_mode:
        import logging
        from utils.logger import log  # pyright: ignore[reportImplicitRelativeImport]

        log.setLevel(logging.DEBUG)
        for handler in log.handlers:
            handler.setLevel(logging.DEBUG)
        log.debug("디버그 모드 활성화")
    app = ProgressEyeApp(debug_mode=debug_mode)
    sys.exit(app.run())


if __name__ == "__main__":
    main()
