"""ProgressEye PC Agent 엔트리포인트.

영역 선택 → 바 탐지 → 전환점 분석 → 진행률 표시 파이프라인을 실행한다.
MVP 단계: Firebase 연동 없이 로컬 동작만 구현.
"""

# pyright: reportMissingImports=false, reportMissingModuleSource=false, reportMissingTypeArgument=false

import queue
import time
import threading
import os
from concurrent.futures import ThreadPoolExecutor
import pathlib
import sys
import uuid
import ctypes
import webbrowser
from typing import Callable


def _set_dpi_awareness() -> None:
    """Windows Per-Monitor DPI Awareness 설정.

    PyQt 초기화 전에 호출해야 모니터별 DPR이 올바르게 반영된다.
    """
    if sys.platform != "win32":
        return

    try:
        user32 = ctypes.windll.user32
        user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        user32.SetProcessDpiAwarenessContext.restype = ctypes.c_bool
        if user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return
    except (AttributeError, OSError):
        pass

    try:
        shcore = ctypes.windll.shcore
        shcore.SetProcessDpiAwareness.argtypes = [ctypes.c_int]
        shcore.SetProcessDpiAwareness.restype = ctypes.c_int
        shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
    except (AttributeError, OSError):
        pass


_set_dpi_awareness()

from core.ocr_reader import OcrReader, OcrResult  # pyright: ignore[reportImplicitRelativeImport]
from PIL import Image as PILImage
from PyQt6.QtCore import QAbstractNativeEventFilter, QEventLoop, QRect, Qt, QTimer
from PyQt6.QtGui import QGuiApplication, QImage, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

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
from core.system_monitor import collect_stats, warmup_cpu_percent, start_sampler, stop_sampler  # pyright: ignore[reportImplicitRelativeImport]
from ui.area_selector import AreaSelector  # pyright: ignore[reportImplicitRelativeImport]
from ui.color_picker import BarPreviewDialog  # pyright: ignore[reportImplicitRelativeImport]
from ui.ocr_preview import OcrPreviewDialog  # pyright: ignore[reportImplicitRelativeImport]
from ui.region_viewer import RegionViewer  # pyright: ignore[reportImplicitRelativeImport]
from ui.main_window import MainWindow  # pyright: ignore[reportImplicitRelativeImport]
from ui.system_notifier import SystemNotifier  # pyright: ignore[reportImplicitRelativeImport]

from utils.logger import log  # pyright: ignore[reportImplicitRelativeImport]
from utils.i18n import set_language, t  # pyright: ignore[reportImplicitRelativeImport]

_HEARTBEAT_INTERVAL_MS = 60_000
_STATS_SYNC_INTERVAL_MS = 60_000
_SAMPLER_START_DELAY_MS = 20_000


class _SilentAuthAbort(AuthError):
    """사용자 선택으로 로그인 흐름을 조용히 종료할 때 사용한다."""


class _PowerEventFilter(QAbstractNativeEventFilter):
    """Windows WM_POWERBROADCAST 메시지를 감지해 절전 진입/복귀를 콜백한다."""

    _WM_POWERBROADCAST = 0x0218
    _PBT_APMSUSPEND = 0x0004
    _PBT_APMRESUMEAUTOMATIC = 0x0012
    _PBT_APMRESUMESUSPEND = 0x0013

    def __init__(
        self,
        on_suspend: Callable[[], None],
        on_resume: Callable[[], None],
    ) -> None:
        super().__init__()
        self._on_suspend = on_suspend
        self._on_resume = on_resume

    def nativeEventFilter(self, event_type: bytes, message: object) -> tuple[bool, int]:
        if event_type == b"windows_generic_MSG":
            import ctypes.wintypes
            msg = ctypes.cast(int(message), ctypes.POINTER(ctypes.wintypes.MSG)).contents  # type: ignore[arg-type]
            if msg.message == self._WM_POWERBROADCAST:
                if msg.wParam == self._PBT_APMSUSPEND:
                    self._on_suspend()
                elif msg.wParam in (self._PBT_APMRESUMEAUTOMATIC, self._PBT_APMRESUMESUSPEND):
                    self._on_resume()
        return False, 0


class ProgressEyeApp:
    OCR_AREA_EXPAND_RATIO_X = 0.12
    OCR_AREA_EXPAND_RATIO_Y = 0.18
    OCR_AREA_EXPAND_MIN_PX = 8
    OCR_MAX_INTEGER_DIGITS = 3
    OCR_ASSUMED_DECIMAL_PLACES = 1

    """ProgressEye 메인 애플리케이션.

    모든 모듈을 연결하고 전체 파이프라인을 관리한다.
    """

    def __init__(self, debug_mode: bool = False) -> None:
        # Initialize OCR backend before QApplication to avoid Windows DLL
        # initialization conflicts between Qt runtime and onnxruntime.
        self._ocr_reader = OcrReader()
        self._app = QApplication(sys.argv)
        self._system_notifier = SystemNotifier(self._app)
        self._config = Config()
        self._capturer = ScreenCapturer()
        self._analyzer = BarAnalyzer()
        self._bar_finder = BarFinder()
        self._freeze_detector = FreezeDetector(
            timeout_minutes=self._config.get("freeze_detection.timeout_minutes", 5),
        )
        self._scheduler = CaptureScheduler(
            on_capture=self._on_capture_from_worker,
            capturer=self._capturer,
            on_cycle_complete=self._on_cycle_complete_from_worker,
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
        self._screenshot_cache_lock = threading.Lock()
        self._command_queue: queue.Queue[dict[str, object]] = queue.Queue()
        self._processed_command_ids: dict[str, float] = {}
        self._last_command_ts_by_type: dict[str, int] = {}
        self._silent_auth_abort: bool = False
        self._quitting: bool = False
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
            pathlib.Path.home() / "AppData" / "Local" / "ProgressEye" / "templates"
        )
        self._template_dir.mkdir(parents=True, exist_ok=True)

        # 언어 설정 (MainWindow 생성 전에 적용해야 t() 번역이 올바름)
        set_language(self._config.get("language", "en"))

        # UI
        self._debug_mode = debug_mode
        self._main_window = MainWindow(show_test_buttons=debug_mode)
        self._area_selector: AreaSelector | None = None
        self._region_viewer: RegionViewer | None = None
        self._region_editor = None  # RegionEditor | None
        self._task_counter = len(self._config.regions)
        self._selection_mode: str = "bar"  # "bar" 또는 "ocr"
        self._bar_selection_guide_shown = False

        # Windows 절전 이벤트 감지
        self._power_filter = _PowerEventFilter(
            on_suspend=self._on_system_suspend,
            on_resume=self._on_system_resume,
        )
        self._app.installNativeEventFilter(self._power_filter)

        # 크로스-스레드 액션 큐 (pystray/Timer → Qt 메인 스레드)
        self._action_queue: queue.Queue[Callable[[], None]] = queue.Queue()
        self._poll_timer = QTimer()
        # 백그라운드 분석 중인 영역 ID 집합 (중복 실행 방지)
        self._capturing_regions: set[str] = set()
        self._capturing_lock = threading.Lock()
        # 영역별 병렬 분석용 스레드 풀 (OCR 등 CPU/IO 병목을 영역 간 병렬화)
        # max_workers=None → Python 기본값: min(32, os.cpu_count() + 4)
        self._analysis_executor = ThreadPoolExecutor(max_workers=None, thread_name_prefix="pe-analysis")
        self._poll_timer.timeout.connect(self._process_queued_actions)
        self._poll_timer.start(50)

        # 모바일 명령 큐 폴링 (200ms)
        self._cmd_poll_timer = QTimer()
        self._cmd_poll_timer.timeout.connect(self._process_commands)
        self._cmd_poll_timer.start(200)

        # HW stats UI 갱신 (10초 주기, 샘플러와 동일 주기)
        self._hw_ui_timer = QTimer()
        self._hw_ui_timer.timeout.connect(self._update_hw_ui)
        self._hw_ui_timer.start(10_000)
        # 앱 시작 5초 후 HW 샘플러 시작 (로그인 여부와 무관하게 항상 실행)
        QTimer.singleShot(5_000, start_sampler)

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
        self._main_window.settings_delete_account_requested.connect(
            self._do_delete_account
        )
        self._main_window.settings_withdrawal_expired_test_requested.connect(
            self._on_test_withdrawal_expired
        )
        self._main_window.settings_rejoin_expired_test_requested.connect(
            self._on_test_rejoin_expired
        )
        self._main_window.settings_privacy_policy_requested.connect(
            self._open_privacy_policy
        )
        self._main_window.settings_third_party_licenses_requested.connect(
            self._open_third_party_licenses
        )
        self._main_window.settings_bar_guide_requested.connect(
            self._on_show_bar_guide
        )
        self._main_window.close_requested.connect(self._quit)
        self._main_window.region_threshold_changed.connect(self._on_threshold_changed)
        self._main_window.region_delay_changed.connect(self._on_delay_changed)
        self._main_window.test_stall_requested.connect(self._on_test_stall)
        self._main_window.test_complete_requested.connect(self._on_test_complete)
        # 기존 영역 복원
        self._restore_regions()

        # 모니터 DPI/구성 변경 감지
        self._connect_screen_signals()

    def _connect_screen_signals(self) -> None:
        """Qt 화면 DPI/해상도 변경 시그널을 연결한다."""
        app = QGuiApplication.instance()
        if app is not None:
            app.screenAdded.connect(self._on_screen_changed)  # type: ignore[union-attr]
            app.screenRemoved.connect(self._on_screen_changed)  # type: ignore[union-attr]
        for screen in QGuiApplication.screens():
            screen.logicalDotsPerInchChanged.connect(self._on_screen_changed)
            screen.geometryChanged.connect(self._on_screen_changed)
        # 모니터 DPR 정보 로깅
        for i, screen in enumerate(QGuiApplication.screens()):
            geo = screen.geometry()
            log.info(
                "모니터 %d: %s (%d,%d %dx%d) DPR=%.2f",
                i,
                screen.name(),
                geo.x(),
                geo.y(),
                geo.width(),
                geo.height(),
                screen.devicePixelRatio(),
            )

    def _on_screen_changed(self, *_args: object) -> None:
        """DPI/모니터 구성 변경 시 호출된다."""
        log.info("모니터 구성 변경 감지 — 열린 오버레이를 닫습니다")
        # 열려 있는 오버레이 닫기 (좌표계가 달라졌으므로)
        if self._area_selector is not None:
            self._area_selector.close()
            self._area_selector = None
        if self._region_viewer is not None:
            self._region_viewer.close()
            self._region_viewer = None

    def run(self) -> int:
        """애플리케이션을 실행한다."""
        log.info("ProgressEye 시작 (python=%s)", sys.executable)

        # 최소 버전 체크 (Firestore — 인증 불필요)
        min_ver = get_min_pc_version()
        if min_ver and self._is_outdated(APP_VERSION, min_ver):
            log.warning("업데이트 필요: 현재=%s 최소=%s", APP_VERSION, min_ver)
            self._show_update_required(min_ver)
            return 0

        is_first = not self._config.get("auth.uid", "")
        if not self._try_auto_login():
            self._main_window.show()
            self._main_window.set_login_mode(True)
            self._ensure_login()
            if self._silent_auth_abort:
                log.info("로그인 취소로 앱을 종료합니다")
                self._do_quit()
                return 0
        if is_first and self._config.get("auth.uid", ""):
            self._show_welcome()
        self._main_window.show()
        self._maybe_show_ocr_runtime_guide()
        return self._app.exec()

    def _maybe_show_ocr_runtime_guide(self) -> None:
        if self._ocr_reader.backend != "paddleocr":
            return
        if self._config.get("startup.ocr_runtime_guide_ack", False):
            return

        dialog = QMessageBox(self._main_window)
        dialog.setWindowTitle(t("ocr_runtime_guide_title"))
        dialog.setIcon(QMessageBox.Icon.Information)
        dialog.setText(t("ocr_runtime_guide_summary"))
        dialog.setInformativeText(t("ocr_runtime_guide_detail"))
        dialog.addButton(t("ocr_runtime_guide_ok"), QMessageBox.ButtonRole.AcceptRole)
        never_btn = dialog.addButton(
            t("ocr_runtime_guide_never"),
            QMessageBox.ButtonRole.ActionRole,
        )
        self._exec_foreground_dialog(dialog)
        if dialog.clickedButton() is never_btn:
            self._config.set("startup.ocr_runtime_guide_ack", True)

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
            if not self._handle_withdrawal_gate(
                uid,
                result["id_token"],
                str(result.get("email", "")),
            ):
                self._token_manager.clear()
                self._config.set("auth.uid", "")
                self._config.set("auth.email", "")
                return False
            self._init_firebase(uid, device_id, result["id_token"])
        log.info("자동 로그인 성공")
        return True

    def _ensure_login(self) -> None:
        """로그인 실패 시 사용자에게 재시도 기회를 제공한다."""
        while True:
            action = self._wait_login_action()
            if action != "login":
                log.info("로그인 시작 취소")
                self._silent_auth_abort = True
                return
            try:
                self._do_login()
                self._main_window.set_login_mode(False)
                return
            except _SilentAuthAbort:
                log.info("로그인 흐름 조용히 종료")
                self._do_quit()
                return
            except AuthError as exc:
                self._main_window.set_login_mode(True, str(exc))
            except Exception as exc:
                self._main_window.set_login_mode(
                    True,
                    t("login_unknown_error").format(error=exc),
                )

    def _wait_login_action(self) -> str:
        """메인 창 로그인 화면에서 사용자 선택을 대기한다."""
        result = {"action": "cancel"}
        loop = QEventLoop(self._app)

        def on_login() -> None:
            result["action"] = "login"
            loop.quit()

        def on_cancel() -> None:
            result["action"] = "cancel"
            loop.quit()

        self._main_window.login_start_requested.connect(on_login)
        self._main_window.login_cancel_requested.connect(on_cancel)
        try:
            loop.exec()
        finally:
            self._main_window.login_start_requested.disconnect(on_login)
            self._main_window.login_cancel_requested.disconnect(on_cancel)
        return result["action"]

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
        return self._exec_foreground_dialog(dialog) == QMessageBox.StandardButton.Retry

    def _exec_foreground_dialog(self, dialog: QMessageBox) -> int:
        """중요 다이얼로그를 화면 최상단/포커스로 실행한다."""
        self._prepare_foreground_window(dialog)
        return dialog.exec()

    def _prepare_foreground_window(
        self,
        window: QWidget,
        *,
        include_parent: bool = True,
    ) -> None:
        """창을 최상단/포커스로 표시한다."""
        window.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        window.setWindowFlag(Qt.WindowType.Window, True)
        window.setWindowModality(Qt.WindowModality.ApplicationModal)

        parent = self._main_window
        if include_parent and parent is not None:
            try:
                if parent.isMinimized():
                    parent.showNormal()
                parent.raise_()
                parent.activateWindow()
                self._force_foreground_win32(parent)
            except RuntimeError:
                pass

        if window.isMinimized():
            window.showNormal()
        window.show()
        window.raise_()
        window.activateWindow()
        self._force_foreground_win32(window)
        self._app.processEvents()

    def _force_foreground_win32(self, window: QWidget) -> None:
        """Windows에서 창을 전면으로 강제한다."""
        if sys.platform != "win32":
            return
        try:
            hwnd = int(window.winId())
        except Exception:
            return
        if hwnd <= 0:
            return

        try:
            user32 = ctypes.windll.user32
            sw_restore = 9
            hwnd_topmost = -1
            hwnd_notopmost = -2
            swp_nosize = 0x0001
            swp_nomove = 0x0002
            flags = swp_nosize | swp_nomove

            user32.ShowWindow(hwnd, sw_restore)
            user32.SetWindowPos(hwnd, hwnd_topmost, 0, 0, 0, 0, flags)
            user32.SetWindowPos(hwnd, hwnd_notopmost, 0, 0, 0, 0, flags)
            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
        except Exception:
            return

    def _handle_withdrawal_gate(self, uid: str, id_token: str, email: str = "") -> bool:
        """탈퇴 유예/재가입 제한 게이트를 처리한다.

        Returns:
            로그인 진행 가능하면 True, 차단하면 False.
        """
        if not uid or not id_token:
            return True

        # 임시 DB/DM으로 withdrawal 상태 조회 및 취소 처리
        temp_db = RealtimeDB(
            db_url="https://progresseye-49244-default-rtdb.firebaseio.com",
            get_id_token=lambda: id_token,
        )
        temp_dm = DeviceManager(
            temp_db, uid, str(self._config.get("auth.device_id", ""))
        )
        state = temp_dm.get_withdrawal_state(email=email)

        now = int(time.time() * 1000)
        pending = bool(state.get("pending", False))
        delete_at = int(state.get("deleteAt", 0))
        rejoin_at = int(state.get("rejoinAllowedAt", 0))

        # 유예기간(pending, deleteAt 전)에는 로그인 시 탈퇴 취소 안내
        if pending and delete_at > now:
            date_text = time.strftime("%Y-%m-%d", time.localtime(delete_at / 1000))
            dialog = QMessageBox(self._main_window)
            dialog.setWindowTitle(t("withdrawal_pending_title"))
            dialog.setIcon(QMessageBox.Icon.Warning)
            dialog.setText(t("withdrawal_pending_message").format(date=date_text))
            cancel_btn = dialog.addButton(
                t("withdrawal_cancel_yes"), QMessageBox.ButtonRole.AcceptRole
            )
            dialog.addButton(
                t("withdrawal_cancel_no"), QMessageBox.ButtonRole.RejectRole
            )
            self._exec_foreground_dialog(dialog)
            if dialog.clickedButton() == cancel_btn:
                try:
                    temp_dm.cancel_account_withdrawal(email=email)
                    self._notify(t("withdrawal_cancelled"))
                    return True
                except Exception as exc:
                    log.warning("탈퇴 취소 실패: %s", exc)
                    self._notify(t("withdrawal_cancel_failed").format(error=exc))
                    return False
            self._silent_auth_abort = True
            return False

        # 유예기간이 끝났거나 재가입 제한 tombstone만 남은 경우: 제한 유지
        if rejoin_at > now:
            dt = time.strftime("%Y-%m-%d", time.localtime(rejoin_at / 1000))
            dialog = QMessageBox(self._main_window)
            dialog.setWindowTitle(t("withdrawal_rejoin_blocked_title"))
            dialog.setIcon(QMessageBox.Icon.Warning)
            dialog.setText(t("withdrawal_rejoin_blocked").format(date=dt))
            dialog.addButton(QMessageBox.StandardButton.Ok)
            self._exec_foreground_dialog(dialog)
            self._notify(t("withdrawal_rejoin_blocked").format(date=dt))
            return False

        return True

    @staticmethod
    def _is_outdated(current: str, minimum: str) -> bool:
        """버전 문자열을 비교하여 현재 버전이 최소 버전 미만인지 확인한다."""

        def parse(v: str) -> tuple[int, ...]:
            import re

            return tuple(
                int(m.group()) for seg in v.split(".") if (m := re.match(r"\d+", seg))
            )

        return parse(current) < parse(minimum)

    def _show_update_required(self, min_version: str) -> None:
        """업데이트 필요 다이얼로그를 표시하고 앱을 종료한다."""
        dialog = QMessageBox(self._main_window)
        dialog.setWindowTitle(t("update_required_title"))
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setText(t("update_required_message"))
        dialog.setInformativeText(
            t("update_required_detail").format(current=APP_VERSION, minimum=min_version)
        )
        dialog.addButton(t("update_required_quit"), QMessageBox.ButtonRole.AcceptRole)
        self._exec_foreground_dialog(dialog)
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
        self._exec_foreground_dialog(dialog)
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
        self._silent_auth_abort = False

        # OAuth 서버는 브라우저 콜백을 기다리며 블로킹된다.
        # 메인 스레드를 막지 않도록 백그라운드 스레드에서 실행하고
        # QEventLoop으로 결과를 기다린다.
        _oauth_result: dict[str, str] = {}
        _oauth_errors: list[BaseException] = []
        _oauth_loop = QEventLoop(self._app)

        def _run_oauth() -> None:
            try:
                _oauth_result.update(self._google_oauth.sign_in())
            except BaseException as exc:
                _oauth_errors.append(exc)
            finally:
                QTimer.singleShot(0, _oauth_loop.quit)

        threading.Thread(target=_run_oauth, daemon=True).start()
        _oauth_loop.exec()

        if _oauth_errors:
            raise _oauth_errors[0]

        google_result = _oauth_result
        firebase_result = self._firebase_auth.sign_in_with_google(
            google_result["id_token"]
        )
        self._firebase_id_token = firebase_result["id_token"]
        self._token_expires_at = time.time() + 3600

        uid = firebase_result["uid"]
        email = firebase_result["email"]

        if not self._handle_withdrawal_gate(
            uid,
            firebase_result["id_token"],
            str(firebase_result.get("email", "")),
        ):
            if self._silent_auth_abort:
                raise _SilentAuthAbort("withdrawal gate closed by user")
            raise AuthError(t("withdrawal_gate_blocked"))

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

        # 플랜 확인 + Free 단일기기 강제 (워커 스레드에서 수행, UI 블로킹 방지)
        dm = self._device_manager
        d_id = device_id
        threading.Thread(
            target=self._check_plan_worker,
            args=(dm, d_id),
            daemon=True,
            name="plan-check",
        ).start()
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
        """하트비트 + stats 전송 (워커 스레드에서 수행, UI 블로킹 방지)."""
        dm = self._device_manager
        if not dm:
            return
        threading.Thread(
            target=self._heartbeat_worker,
            args=(dm,),
            daemon=True,
            name="heartbeat",
        ).start()

    def _heartbeat_worker(self, dm: DeviceManager) -> None:
        """워커 스레드: 하트비트 + stats RTDB 전송."""
        try:
            dm.heartbeat()
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

    def _check_plan_worker(self, dm: DeviceManager, device_id: str) -> None:
        """워커 스레드: Firestore 플랜 조회 + Free 단일기기 강제."""
        try:
            plan = dm.get_user_plan()
            self._config.set("plan", plan)
            log.info("유저 플랜: %s", plan)
            if plan == "free":
                # 최초 로그인/누락 케이스: Firestore users/{uid} free 문서 보정 생성
                dm.ensure_free_user_registered()
                active = dm.get_active_device()
                if active and active != device_id:
                    if dm.is_other_device_online(active):
                        log.warning("다른 PC에서 사용 중: %s", active)
                        self._action_queue.put(
                            lambda a=active: self._show_device_conflict(a)
                        )
                        return
                dm.set_active_device()
        except Exception as exc:
            log.debug("플랜/디바이스 확인 실패: %s", exc)

    def _notify(
        self,
        message: str,
        *,
        system: bool = False,
        title: str = "ProgressEye",
    ) -> None:
        """이벤트 알림을 로그/시스템 알림으로 표시한다."""
        log.info("[알림] %s", message)
        if system:
            self._system_notifier.notify(title, message)

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
            # 디바이스 대상 명령 필터링 (forceLogout은 전체 브로드캐스트)
            if cmd_type in ("screenshot", "monitor", "sleep", "shutdown"):
                cmd_data = cmd.get("data")
                target = (
                    cmd_data.get("targetDeviceId")
                    if isinstance(cmd_data, dict)
                    else None
                )
                my_device = str(self._config.get("auth.device_id", ""))
                # sleep/shutdown: targetDeviceId 반드시 일치해야 실행
                if cmd_type in ("sleep", "shutdown"):
                    if not isinstance(target, str) or target != my_device:
                        log.debug(
                            "[CMD] %s 명령 무시: targetDeviceId 불일치 (target=%s)",
                            cmd_type,
                            target,
                        )
                        continue
                elif isinstance(target, str) and target and target != my_device:
                    log.debug(
                        "[CMD] 다른 기기 대상 명령 무시: type=%s target=%s",
                        cmd_type,
                        target,
                    )
                    continue
            if cmd_type == "forceLogout" and bool(cmd.get("fromInitialSnapshot")):
                uid = str(self._config.get("auth.uid", ""))
                self._cleanup_force_logout_command(uid)
                log.info("[CMD] 초기 스냅샷 forceLogout 정리 후 무시")
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
            elif cmd_type == "sleep":
                log.info("[CMD] 원격 절전모드 명령 수신")
                uid = str(self._config.get("auth.uid", ""))
                self._cleanup_pc_command(uid, "sleep")
                self._handle_sleep_command()
            elif cmd_type == "shutdown":
                log.info("[CMD] 원격 종료 명령 수신")
                uid = str(self._config.get("auth.uid", ""))
                self._cleanup_pc_command(uid, "shutdown")
                self._handle_shutdown_command()
            elif cmd_type == "forceLogout":
                log.info("[CMD] 원격 강제 로그아웃 수신 — 앱을 종료합니다.")
                uid = str(self._config.get("auth.uid", ""))
                self._cleanup_force_logout_command(uid)
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
        """모바일 스크린샷 요청: 워커 스레드에서 캡처 + 업로드, RTDB는 메인 스레드."""
        if not self._firebase_storage or not self._realtime_db:
            log.warning("스크린샷 명령 무시: Firebase 미초기화")
            return

        threading.Thread(
            target=self._do_screenshot_upload,
            name="screenshot-upload",
            daemon=True,
        ).start()

    def _do_screenshot_upload(self) -> None:
        """워커 스레드: 스크린샷 캡처 → JPEG 인코딩 → Storage 업로드."""
        import hashlib
        import io
        import mss as mss_lib

        if not self._firebase_storage or not self._realtime_db:
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

            with self._screenshot_cache_lock:
                cached = self._screenshot_cache.get(device_id)
            if cached and cached[0] == jpeg_hash:
                download_url = cached[1]
                log.info("[SCREENSHOT] 화면 변경 없음, 업로드 스킵")
            else:
                storage_path = f"screenshots/{uid}/{device_id}/latest.jpg"
                download_url = self._firebase_storage.upload_jpeg(
                    storage_path, jpeg_bytes
                )
                with self._screenshot_cache_lock:
                    self._screenshot_cache[device_id] = (jpeg_hash, download_url)
                log.info("[SCREENSHOT] 업로드 완료: %s", storage_path)

            ts = int(time.time())
            # RTDB 기록 + 명령 정리를 메인 스레드로 마샬링
            self._action_queue.put(
                lambda _u=uid, _d=device_id, _url=download_url, _ts=ts: (
                    self._finish_screenshot(_u, _d, _url, _ts)
                )
            )
        except Exception as exc:
            log.warning("스크린샷 처리 실패: %s", exc)
            self._action_queue.put(lambda _u=uid: self._cleanup_screenshot_command(_u))

    def _finish_screenshot(
        self, uid: str, device_id: str, download_url: str, ts: int
    ) -> None:
        """메인 스레드: RTDB에 스크린샷 URL 기록 + 명령 정리."""
        try:
            if self._realtime_db and uid:
                self._realtime_db.patch(
                    f"users/{uid}/devices/{device_id}/screenshots",
                    {"latest": {"url": download_url, "ts": ts}},
                )
                log.info("스크린샷 처리 완료 (ts=%d)", ts)
        except Exception as exc:
            log.warning("스크린샷 RTDB 기록 실패: %s", exc)
        finally:
            self._cleanup_screenshot_command(uid)

    def _cleanup_screenshot_command(self, uid: str) -> None:
        """스크린샷 명령을 RTDB에서 삭제한다."""
        try:
            if self._realtime_db and uid:
                self._realtime_db.delete(f"users/{uid}/commands/screenshot")
        except Exception as exc:
            log.debug("스크린샷 명령 삭제 실패: %s", exc)

    def _cleanup_force_logout_command(self, uid: str) -> None:
        """강제 로그아웃 명령을 RTDB에서 삭제한다."""
        try:
            if self._realtime_db and uid:
                self._realtime_db.delete(f"users/{uid}/commands/forceLogout")
        except Exception as exc:
            log.debug("forceLogout 명령 삭제 실패: %s", exc)

    def _cleanup_pc_command(self, uid: str, cmd_name: str) -> None:
        """PC 제어 명령(sleep/shutdown)을 RTDB에서 삭제한다."""
        try:
            if self._realtime_db and uid:
                self._realtime_db.delete(f"users/{uid}/commands/{cmd_name}")
        except Exception as exc:
            log.debug("%s 명령 삭제 실패: %s", cmd_name, exc)

    def _handle_sleep_command(self) -> None:
        """PC를 절전모드로 전환한다."""
        import subprocess

        if self._device_manager:
            threading.Thread(
                target=self._device_manager.set_sleep, daemon=True
            ).start()
        try:
            subprocess.Popen(
                ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
                shell=False,
            )
            log.info("[CMD] 절전모드 명령 실행")
        except Exception as exc:
            log.warning("[CMD] 절전모드 실행 실패: %s", exc)

    def _handle_shutdown_command(self) -> None:
        """PC를 종료한다 (30초 후 강제 종료)."""
        import subprocess

        if self._scheduler.is_running:
            self._scheduler.stop()
            self._main_window.set_monitoring_state(False)
        if self._device_manager:
            threading.Thread(
                target=self._device_manager.set_offline, daemon=True
            ).start()
        try:
            subprocess.Popen(
                ["shutdown", "/s", "/t", "30"],
                shell=False,
            )
            log.info("[CMD] 종료 명령 실행 (30초 후 종료)")
        except Exception as exc:
            log.warning("[CMD] 종료 실행 실패: %s", exc)

    def _restore_regions(self) -> None:
        """설정에 저장된 영역을 복원한다."""
        for region in self._config.regions:
            enabled = region.get("enabled", True)
            progress_unit = "%"
            self._main_window.add_region_display(
                region["id"],
                region.get("label", region["id"]),
                region_type=region.get("type", "bar"),
                progress_unit=progress_unit,
                enabled=enabled,
                alert_threshold=region.get("alert_threshold", 100),
                alert_delay_minutes=region.get("alert_delay_minutes", 0),
                bar_mode=region.get("bar_mode", "auto"),
                target_color=region.get("target_color"),
            )
            # 로컬 템플릿 이미지 복원
            tpl = self._load_template(region["id"])
            if tpl is not None:
                self._template_images[region["id"]] = tpl

    def _start_area_selection(self) -> None:
        """프로그래스바 영역 선택을 시작한다."""
        self._selection_mode = "bar"
        self._show_bar_selection_guide_if_needed()
        QTimer.singleShot(0, self._do_start_area_selection)

    def _show_bar_selection_guide_if_needed(self) -> None:
        if self._bar_selection_guide_shown or self._editing_region_id is not None:
            return
        if self._config.get("startup.bar_selection_guide_ack", False):
            return

        from PyQt6.QtWidgets import QCheckBox  # pyright: ignore[reportImplicitRelativeImport]

        dialog = QDialog(self._main_window)
        dialog.setWindowTitle(t("bar_selection_guide_title"))

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        image_label = QLabel()
        image_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        image_label.setStyleSheet("background: transparent;")
        layout.addWidget(image_label)

        guide_label = QLabel(t("bar_selection_guide_text"))
        guide_label.setWordWrap(True)
        guide_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        layout.addWidget(guide_label)

        never_checkbox = QCheckBox(t("bar_selection_guide_never"))
        layout.addWidget(never_checkbox)

        confirm_btn = QPushButton(t("btn_confirm"))
        confirm_btn.clicked.connect(dialog.accept)
        layout.addWidget(confirm_btn, alignment=Qt.AlignmentFlag.AlignRight)

        sample_pixmaps = self._load_bar_selection_guide_pixmaps()
        if sample_pixmaps:
            image_label.setPixmap(sample_pixmaps[0])
        else:
            image_label.setVisible(False)

        if len(sample_pixmaps) > 1:
            current_index = 0
            rotate_timer = QTimer(dialog)
            rotate_timer.setInterval(4000)

            def _rotate_sample() -> None:
                nonlocal current_index
                current_index = (current_index + 1) % len(sample_pixmaps)
                image_label.setPixmap(sample_pixmaps[current_index])

            rotate_timer.timeout.connect(_rotate_sample)
            rotate_timer.start()

        self._prepare_foreground_window(dialog)
        dialog.exec()
        self._bar_selection_guide_shown = True
        if never_checkbox.isChecked():
            self._config.set("startup.bar_selection_guide_ack", True)

    def _load_bar_selection_guide_pixmaps(self) -> list[QPixmap]:
        base_dir = pathlib.Path(__file__).resolve().parent
        candidates: list[pathlib.Path] = []

        primary = base_dir / "resources" / "progress-bar-sample.png"
        if primary.exists():
            candidates.append(primary)

        sample_dir = base_dir / "sampleBar"
        if sample_dir.exists():
            candidates.extend(sorted(sample_dir.glob("image*.png")))

        pixmaps: list[QPixmap] = []
        seen_paths: set[pathlib.Path] = set()
        for image_path in candidates:
            resolved = image_path.resolve()
            if resolved in seen_paths:
                continue
            seen_paths.add(resolved)

            pixmap = QPixmap(str(image_path))
            if pixmap.isNull():
                continue
            pixmaps.append(
                pixmap.scaledToWidth(360, Qt.TransformationMode.SmoothTransformation)
            )

        if not pixmaps:
            log.warning("진행률 바 가이드 샘플 이미지를 찾지 못함")

        return pixmaps

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
            region: dict = {
                "id": region_id,
                "label": dialog.task_name
                or t("default_task_name").format(n=self._task_counter),
                "type": "bar",
                "monitor": area.get("monitor", 0),
                "x": area["x"],
                "y": area["y"],
                "width": area["width"],
                "height": area["height"],
                "abs_x": area.get("abs_x"),
                "abs_y": area.get("abs_y"),
                "direction": direction,
                "bar_mode": dialog.bar_mode,
                **bar_crop,
            }
            if dialog.target_color is not None:
                region["target_color"] = list(dialog.target_color)
            region_label = str(region["label"])
            self._config.add_region(region)
            self._main_window.add_region_display(
                region_id, region_label, region_type="bar",
                bar_mode=dialog.bar_mode,
                target_color=list(dialog.target_color) if dialog.target_color else None,
            )
            final_progress = dialog.progress
            self._main_window.update_progress(region_id, final_progress, region_label)
            if self._scheduler.is_running:
                self._scheduler.add_region(region)
            log.info("바 영역 등록: %s (%.1f%%)", region_id, final_progress)
            # 템플릿 이미지 저장 (원본 영역 전체 — 이미지 변경 감지용)
            self._save_template(region_id, image)
            # Firebase에 라벨 전송 (등록 시 1회)
            if self._device_manager:
                try:
                    self._device_manager.set_task_label(region_id, region_label)
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

        mode = "percent"
        target = 100.0
        prefer_percent = True
        ocr_results = self._ocr_reader.find_percentages(
            image,
            min_value=0.0,
            max_value=target,
        )
        detected_progress = None
        default_ocr_region = (0, 0, image.width, image.height)
        if ocr_results:
            best = self._ocr_reader.select_best_result(
                ocr_results,
                prefer_percent_sign=prefer_percent,
            )
            detected_progress = best.progress

        qimage = self._pil_to_qimage(image)
        dialog = OcrPreviewDialog(
            image=qimage,
            full_image=image,
            ocr_reader=self._ocr_reader,
            ocr_results=ocr_results,
            detected_progress=detected_progress,
            ocr_region=default_ocr_region,
            detection_mode=mode,
            target_value=target,
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
                "abs_x": area.get("abs_x"),
                "abs_y": area.get("abs_y"),
                "ocr_left": dialog.ocr_region[0],
                "ocr_top": dialog.ocr_region[1],
                "ocr_right": dialog.ocr_region[2],
                "ocr_bottom": dialog.ocr_region[3],
                "ocr_mode": dialog.detection_mode,
                "ocr_target": dialog.target_value,
            }
            region_label = str(region["label"])
            progress_unit = "%"
            self._config.add_region(region)
            self._main_window.add_region_display(
                region_id,
                region_label,
                region_type="ocr",
                progress_unit=progress_unit,
            )
            final_progress = dialog.progress
            self._main_window.update_progress(
                region_id,
                final_progress,
                region_label,
                progress_unit=progress_unit,
            )
            if self._scheduler.is_running:
                self._scheduler.add_region(region)
            log.info("OCR 영역 등록: %s (%.1f%%)", region_id, final_progress)
            # 템플릿 이미지 저장 (이미지 변경 감지용)
            self._save_template(
                region_id,
                self._template_image_for_region(image, region),
            )
            # Firebase에 라벨 전송 (등록 시 1회)
            if self._device_manager:
                try:
                    self._device_manager.set_task_label(region_id, region_label)
                except Exception:
                    pass
        elif dialog.reselect_requested:
            log.info("미리보기에서 재선택 요청")
            QTimer.singleShot(100, self._start_ocr_area_selection)

    def _expand_ocr_area(self, area: dict) -> dict:
        """OCR 영역에 여유 패딩을 추가해 숫자 폭 변화를 흡수한다."""
        expanded = dict(area)
        width = int(expanded.get("width", 0))
        height = int(expanded.get("height", 0))
        if width <= 0 or height <= 0:
            return expanded

        base_pad_x = max(
            self.OCR_AREA_EXPAND_MIN_PX, int(width * self.OCR_AREA_EXPAND_RATIO_X)
        )
        pad_y = max(
            self.OCR_AREA_EXPAND_MIN_PX, int(height * self.OCR_AREA_EXPAND_RATIO_Y)
        )

        # 소수점 1자리(예: 11.0)까지를 기준으로 오른쪽 여유를 추가한다.
        estimated_char_width = max(6, int(height * 0.55))
        decimal_extra_chars = 1 + self.OCR_ASSUMED_DECIMAL_PLACES  # '.' + 소수 자릿수
        extra_right_px = estimated_char_width * decimal_extra_chars
        pad_left = base_pad_x
        pad_right = base_pad_x + extra_right_px

        monitor_idx = int(expanded.get("monitor", 0))
        monitors = self._capturer.get_monitors()
        if monitor_idx < 0 or monitor_idx >= len(monitors):
            monitor_idx = 0
        mon = monitors[monitor_idx]

        if expanded.get("abs_x") is not None and expanded.get("abs_y") is not None:
            abs_left = int(expanded.get("abs_x", 0)) - pad_left
            abs_top = int(expanded.get("abs_y", 0)) - pad_y
            abs_right = int(expanded.get("abs_x", 0)) + width + pad_right
            abs_bottom = int(expanded.get("abs_y", 0)) + height + pad_y

            min_x = int(mon["left"])
            min_y = int(mon["top"])
            max_x = int(mon["left"] + mon["width"])
            max_y = int(mon["top"] + mon["height"])

            abs_left = max(min_x, abs_left)
            abs_top = max(min_y, abs_top)
            abs_right = min(max_x, abs_right)
            abs_bottom = min(max_y, abs_bottom)

            if abs_right <= abs_left:
                abs_right = min(max_x, abs_left + 1)
            if abs_bottom <= abs_top:
                abs_bottom = min(max_y, abs_top + 1)

            expanded["abs_x"] = abs_left
            expanded["abs_y"] = abs_top
            expanded["width"] = abs_right - abs_left
            expanded["height"] = abs_bottom - abs_top

            if monitor_idx > 0:
                expanded["x"] = abs_left - int(mon["left"])
                expanded["y"] = abs_top - int(mon["top"])
            else:
                expanded["x"] = abs_left
                expanded["y"] = abs_top
        else:
            x = int(expanded.get("x", 0))
            y = int(expanded.get("y", 0))

            if monitor_idx > 0:
                min_x = 0
                min_y = 0
                max_x = int(mon["width"])
                max_y = int(mon["height"])
            else:
                min_x = int(mon["left"])
                min_y = int(mon["top"])
                max_x = int(mon["left"] + mon["width"])
                max_y = int(mon["top"] + mon["height"])

            left = max(min_x, x - pad_left)
            top = max(min_y, y - pad_y)
            right = min(max_x, x + width + pad_right)
            bottom = min(max_y, y + height + pad_y)

            if right <= left:
                right = min(max_x, left + 1)
            if bottom <= top:
                bottom = min(max_y, top + 1)

            expanded["x"] = left
            expanded["y"] = top
            expanded["width"] = right - left
            expanded["height"] = bottom - top

            if monitor_idx > 0:
                expanded["abs_x"] = int(mon["left"]) + expanded["x"]
                expanded["abs_y"] = int(mon["top"]) + expanded["y"]

        log.info(
            "OCR 영역 자동 확장: (%d,%d,%d,%d) -> (%d,%d,%d,%d)",
            int(area.get("x", 0)),
            int(area.get("y", 0)),
            width,
            height,
            int(expanded.get("x", 0)),
            int(expanded.get("y", 0)),
            int(expanded.get("width", 0)),
            int(expanded.get("height", 0)),
        )
        return expanded

    def _build_default_ocr_region(
        self,
        image: PILImage.Image,
        ocr_results: list,
    ) -> tuple[int, int, int, int]:
        """Build default OCR focus region with 3-digit + 1-decimal width margin."""
        img_w, img_h = image.size
        full = (0, 0, img_w, img_h)
        if not ocr_results:
            return full

        best = self._ocr_reader.select_best_result(ocr_results)
        x, y, w, h = best.bbox
        if w <= 0 or h <= 0:
            return full

        estimated_char_width = max(6, int(h * 0.55))
        required_chars = (
            self.OCR_MAX_INTEGER_DIGITS + 1 + self.OCR_ASSUMED_DECIMAL_PLACES
        )
        required_w = max(w, estimated_char_width * required_chars)
        pad_x = max(self.OCR_AREA_EXPAND_MIN_PX, int(estimated_char_width * 0.8))
        pad_y = max(self.OCR_AREA_EXPAND_MIN_PX, int(h * 0.2))

        center_x = x + w // 2
        left = center_x - required_w // 2 - pad_x
        right = center_x + required_w // 2 + pad_x
        top = y - pad_y
        bottom = y + h + pad_y

        return self._normalize_ocr_region((left, top, right, bottom), img_w, img_h)

    @staticmethod
    def _normalize_ocr_region(
        region: tuple[int, int, int, int], img_w: int, img_h: int
    ) -> tuple[int, int, int, int]:
        left, top, right, bottom = region
        left = max(0, min(left, img_w - 1))
        top = max(0, min(top, img_h - 1))
        right = max(left + 1, min(right, img_w))
        bottom = max(top + 1, min(bottom, img_h))
        return left, top, right, bottom

    def _get_ocr_mode_settings(
        self, region_config: dict
    ) -> tuple[str, float, str, bool]:
        mode = "value" if region_config.get("ocr_mode") == "value" else "percent"
        target_raw = region_config.get("ocr_target", 100.0)
        try:
            target = float(target_raw)
        except (TypeError, ValueError):
            target = 100.0
        target = max(1.0, target)
        unit = "%"
        prefer_percent = mode == "percent"
        return mode, target, unit, prefer_percent

    @staticmethod
    def _normalize_ocr_progress(
        mode: str, detected_value: float, target: float
    ) -> float:
        if mode == "value":
            if target <= 0:
                return 0.0
            return max(0.0, min(100.0, (detected_value / target) * 100.0))
        return max(0.0, min(100.0, detected_value))

    def _crop_ocr_image_by_config(
        self,
        image: PILImage.Image,
        region_config: dict,
    ) -> PILImage.Image:
        left_raw = region_config.get("ocr_left")
        top_raw = region_config.get("ocr_top")
        right_raw = region_config.get("ocr_right")
        bottom_raw = region_config.get("ocr_bottom")
        if not isinstance(left_raw, (int, float)):
            return image
        if not isinstance(top_raw, (int, float)):
            return image
        if not isinstance(right_raw, (int, float)):
            return image
        if not isinstance(bottom_raw, (int, float)):
            return image
        l, t, r, b = self._normalize_ocr_region(
            (int(left_raw), int(top_raw), int(right_raw), int(bottom_raw)),
            image.width,
            image.height,
        )
        target_w = r - l
        target_h = b - t
        if image.width == target_w and image.height == target_h:
            return image
        return image.crop((l, t, r, b))

    def _template_image_for_region(
        self,
        image: PILImage.Image,
        region_config: dict,
    ) -> PILImage.Image:
        """Build template image for screen-change guard.

        Keep full region context so dynamic progress text/bar can be masked while
        surrounding UI still participates in similarity checks.
        """
        return image

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
                # 모든 영역이 비활성화되면 모니터링 자동 정지
                if self._scheduler.region_count == 0:
                    self._auto_stop_monitoring()
                # RTDB에 idle 상태 기록
                if self._device_manager:
                    self._device_manager.sync_tasks({region_id: {"s": "i"}})
        elif not enabled and self._device_manager:
            # 모니터링 미실행 중 비활성화 → RTDB에도 idle 기록
            self._device_manager.sync_tasks({region_id: {"s": "i"}})
        log.info("영역 토글: %s → %s", region_id, "활성" if enabled else "비활성")

    def _update_region_area(self, region_id: str, area: dict) -> None:
        """재선택된 영역으로 기존 작업의 좌표를 업데이트하고 프리뷰를 다시 열다."""
        current_region = next(
            (r for r in self._config.regions if r["id"] == region_id), None
        )
        if current_region is not None and current_region.get("type", "bar") == "ocr":
            area = dict(area)

        try:
            new_image = self._capturer.capture(area)
        except Exception as exc:
            log.warning("재선택 캡처 실패: %s", exc)
            self._do_edit_region(region_id)
            return

        # bar 타입만 bar_finder 오프셋 갱신
        bar_region = None
        if current_region is None or current_region.get("type", "bar") != "ocr":
            bar_region = self._bar_finder.find(new_image)
        updates: dict = {
            "monitor": area.get("monitor", 0),
            "x": area["x"],
            "y": area["y"],
            "width": area["width"],
            "height": area["height"],
            "abs_x": area.get("abs_x"),
            "abs_y": area.get("abs_y"),
        }
        if current_region is not None and current_region.get("type", "bar") == "ocr":
            updates.update(
                {
                    "ocr_left": None,
                    "ocr_top": None,
                    "ocr_right": None,
                    "ocr_bottom": None,
                }
            )
        if bar_region and bar_region.confidence > 0:
            updates["direction"] = bar_region.direction
            updates["bar_left"] = bar_region.left
            updates["bar_top"] = bar_region.top
            updates["bar_right"] = bar_region.right
            updates["bar_bottom"] = bar_region.bottom
        self._config.update_region(region_id, updates)
        # 템플릿 갱신 (영역 타입별 유효 캡처 기준)
        updated_region = next(
            (r for r in self._config.regions if r.get("id") == region_id),
            None,
        )
        self._save_template(
            region_id,
            self._template_image_for_region(
                new_image,
                updated_region if isinstance(updated_region, dict) else updates,
            ),
        )
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
            # 모든 영역이 삭제되면 모니터링 자동 정지
            if self._scheduler.region_count == 0:
                self._auto_stop_monitoring()
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
            app_version=APP_VERSION,
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
            self._freeze_detector.set_timeout_minutes(new_freeze)
            log.info("프리징 감지 시간 변경: %d분", new_freeze)

    def _do_logout(self) -> None:
        """로그아웃: 토큰 삭제 → 모니터링 중지 → Firebase 정리 → 로그인 화면 전환."""
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
        self._main_window.set_login_mode(True)
        log.info("로그아웃 완료 — 로그인 화면으로 전환")
        self._ensure_login()

    def _do_delete_account(self) -> None:
        """회원탈퇴 요청: 7일 유예 후 삭제, 30일 재가입 제한."""
        confirm = QMessageBox.question(
            self._main_window,
            t("delete_account_title"),
            t("delete_account_confirm"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        dm = self._device_manager

        try:
            if dm is None:
                raise RuntimeError("device manager unavailable")

            dm.request_account_withdrawal(
                grace_days=7,
                rejoin_days=30,
                email=str(self._config.get("auth.email", "")),
            )
            log.info("회원탈퇴 요청 접수: uid=%s", self._config.get("auth.uid", ""))
            self._notify(t("delete_account_requested"))

            # 로컬 로그아웃 + 로그인 화면 전환
            self._do_logout()
        except Exception as exc:
            log.warning("회원탈퇴 실패: %s", exc)
            self._notify(t("delete_account_failed").format(error=exc))

    def _on_test_withdrawal_expired(self) -> None:
        """디버그: 탈퇴 후 7일 경과 시나리오를 강제로 적용한다."""
        if not self._debug_mode:
            return
        dm = self._device_manager
        try:
            if dm is None:
                raise RuntimeError("device manager unavailable")
            dm.debug_mark_withdrawal_expired(
                grace_days=7,
                rejoin_days=30,
                email=str(self._config.get("auth.email", "")),
            )
            log.info(
                "디버그 탈퇴+7일 시나리오 적용: uid=%s",
                self._config.get("auth.uid", ""),
            )
            self._notify(t("withdrawal_scenario_applied"))
            # 테스트 시나리오 적용 후 즉시 로그아웃하여 추가 데이터 업데이트를 방지한다.
            self._do_logout()
        except Exception as exc:
            log.warning("디버그 탈퇴+7일 시나리오 적용 실패: %s", exc)
            self._notify(t("withdrawal_scenario_failed").format(error=exc))

    def _on_test_rejoin_expired(self) -> None:
        """디버그: 탈퇴 후 30일 경과 시나리오를 강제로 적용한다."""
        if not self._debug_mode:
            return
        dm = self._device_manager
        try:
            if dm is None:
                raise RuntimeError("device manager unavailable")
            dm.debug_mark_rejoin_expired(
                rejoin_days=30,
                email=str(self._config.get("auth.email", "")),
            )
            log.info(
                "디버그 탈퇴+30일 시나리오 적용: uid=%s",
                self._config.get("auth.uid", ""),
            )
            self._notify(t("rejoin_scenario_applied"))
            # 테스트 시나리오 적용 후 즉시 로그아웃하여 추가 데이터 업데이트를 방지한다.
            self._do_logout()
        except Exception as exc:
            log.warning("디버그 탈퇴+30일 시나리오 적용 실패: %s", exc)
            self._notify(t("rejoin_scenario_failed").format(error=exc))

    def _open_third_party_licenses(self) -> None:
        notice_candidates = [
            pathlib.Path(__file__).resolve().parent / "THIRD_PARTY_NOTICES.txt",
            pathlib.Path(__file__).resolve().parent.parent
            / "docs"
            / "pc-agent"
            / "topics"
            / "build-deploy.md",
        ]
        notice_path = next((p for p in notice_candidates if p.exists()), None)
        if notice_path is None:
            self._notify(t("third_party_licenses_not_found"))
            return

        try:
            webbrowser.open(notice_path.resolve().as_uri())
            self._notify(
                t("third_party_licenses_opened").format(path=str(notice_path.resolve()))
            )
        except Exception as exc:
            log.warning("서드파티 라이선스 파일 열기 실패: %s", exc)
            self._notify(t("third_party_licenses_open_failed").format(error=exc))

    def _on_show_bar_guide(self) -> None:
        """설정에서 '바 선택 안내 다시 보기' 버튼 클릭 시 안내 다이얼로그를 다시 표시한다."""
        self._config.set("startup.bar_selection_guide_ack", False)
        self._bar_selection_guide_shown = False
        self._show_bar_selection_guide_if_needed()

    def _open_privacy_policy(self) -> None:
        lang = str(self._config.get("language", "en")).lower()
        lang = "ko" if lang.startswith("ko") else "en"
        policy_url = f"https://progresseye-49244.web.app/?lang={lang}"
        try:
            webbrowser.open(policy_url)
            self._notify(t("privacy_policy_opened"))
        except Exception as exc:
            log.warning("개인정보처리방침 열기 실패: %s", exc)
            self._notify(t("privacy_policy_open_failed").format(error=exc))

    def _show_welcome(self) -> None:
        """최초 로그인 후 웰컴 설정 가이드를 표시한다."""
        self._main_window.show_settings(
            interval=self._config.get("capture.interval_seconds", 30),
            language=self._config.get("language", "en"),
            email=self._config.get("auth.email", ""),
            freeze_minutes=self._config.get("freeze_detection.timeout_minutes", 5),
            welcome_mode=True,
            app_version=APP_VERSION,
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

        progress_unit = "%"
        if region_type == "ocr":
            # OCR 타입: OcrPreviewDialog
            mode, target, progress_unit, prefer_percent = self._get_ocr_mode_settings(
                area
            )
            existing_region = None
            if all(
                isinstance(area.get(k), (int, float))
                for k in ("ocr_left", "ocr_top", "ocr_right", "ocr_bottom")
            ):
                existing_region = self._normalize_ocr_region(
                    (
                        int(area.get("ocr_left", 0)),
                        int(area.get("ocr_top", 0)),
                        int(area.get("ocr_right", image.width)),
                        int(area.get("ocr_bottom", image.height)),
                    ),
                    image.width,
                    image.height,
                )

            image_for_ocr = image.crop(existing_region) if existing_region else image
            ocr_results = self._ocr_reader.find_percentages(
                image_for_ocr,
                min_value=0.0,
                max_value=target,
            )
            if existing_region is not None:
                offset_x, offset_y = existing_region[0], existing_region[1]
                ocr_results = [
                    OcrResult(
                        text=r.text,
                        confidence=r.confidence,
                        bbox=(
                            r.bbox[0] + offset_x,
                            r.bbox[1] + offset_y,
                            r.bbox[2],
                            r.bbox[3],
                        ),
                        progress=r.progress,
                        has_percent_sign=r.has_percent_sign,
                    )
                    for r in ocr_results
                ]
            detected_progress = None
            default_ocr_region = (
                existing_region
                if existing_region
                else self._build_default_ocr_region(image, ocr_results)
            )
            if ocr_results:
                best = self._ocr_reader.select_best_result(
                    ocr_results,
                    prefer_percent_sign=prefer_percent,
                )
                detected_progress = best.progress
            else:
                last_state = self._last_firebase_state.get(region_id, {})
                fallback_progress = last_state.get("p")
                if isinstance(fallback_progress, (int, float)):
                    detected_progress = float(fallback_progress)

            qimage = self._pil_to_qimage(image)
            dialog = OcrPreviewDialog(
                image=qimage,
                full_image=image,
                ocr_reader=self._ocr_reader,
                ocr_results=ocr_results,
                detected_progress=detected_progress,
                ocr_region=default_ocr_region,
                detection_mode=mode,
                target_value=target,
            )
            dialog._task_name_input.setText(current_label)

            if dialog.exec():
                new_label = dialog.task_name or current_label
                self._config.update_region(
                    region_id,
                    {
                        "label": new_label,
                        "ocr_left": dialog.ocr_region[0],
                        "ocr_top": dialog.ocr_region[1],
                        "ocr_right": dialog.ocr_region[2],
                        "ocr_bottom": dialog.ocr_region[3],
                        "ocr_mode": dialog.detection_mode,
                        "ocr_target": dialog.target_value,
                    },
                )
                updated_unit = "%" if dialog.detection_mode == "percent" else ""
                self._main_window.update_progress(
                    region_id,
                    dialog.progress,
                    new_label,
                    progress_unit=updated_unit,
                )
                log.info("OCR 영역 수정: %s → %s", region_id, new_label)
                # 템플릿 이미지 갱신 (수정 시 재캡처된 이미지로)
                template_region = dict(area)
                template_region.update(
                    {
                        "ocr_left": dialog.ocr_region[0],
                        "ocr_top": dialog.ocr_region[1],
                        "ocr_right": dialog.ocr_region[2],
                        "ocr_bottom": dialog.ocr_region[3],
                        "type": "ocr",
                    }
                )
                self._save_template(
                    region_id,
                    self._template_image_for_region(image, template_region),
                )
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
            # Edit Task는 저장된 템플릿(최초 선택/재선택 기준)을 우선 사용한다.
            # 상단 공통 로직에서 템플릿 로드에 실패한 경우에만 실시간 캡처 fallback이 적용된다.

            # 저장된 바 오프셋이 있으면 사용, 없으면 자동 탐지
            saved_left = area.get("bar_left")
            saved_right = area.get("bar_right")
            if saved_left is not None and saved_right is not None:
                bar_region = BarRegion(
                    left=saved_left,
                    top=area.get("bar_top", 0),
                    right=saved_right,
                    bottom=area.get("bar_bottom", image.height),
                    confidence=1.0,
                    direction=area.get("direction", "horizontal"),
                )
                bar_image = image.crop(bar_region.bbox)
                result = self._analyzer.analyze(
                    bar_image, direction=bar_region.direction
                )
            else:
                bar_region, result = self._smart_bar_analyze(image)
                bar_image = image.crop(bar_region.bbox) if bar_region else image

            qimage = self._pil_to_qimage(image)
            # 저장된 bar_mode / target_color 복원
            saved_bar_mode = area.get("bar_mode", "auto")
            saved_target_color_raw = area.get("target_color")
            saved_target_color: tuple[int, int, int] | None = (
                tuple(int(c) for c in saved_target_color_raw[:3])  # type: ignore[assignment]
                if saved_target_color_raw
                else None
            )
            dialog = BarPreviewDialog(
                image=qimage,
                full_image=image,
                bar_image=bar_image,
                detected_progress=result.progress,
                bar_region=bar_region,
                debug_mode=self._debug_mode,
                initial_bar_mode=saved_bar_mode,
                initial_target_color=saved_target_color,
            )
            dialog._task_name_input.setText(current_label)

            if dialog.exec():
                new_label = dialog.task_name or current_label
                updates: dict = {"label": new_label, "bar_mode": dialog.bar_mode}
                if dialog.target_color is not None:
                    updates["target_color"] = list(dialog.target_color)
                else:
                    updates["target_color"] = None
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
                template_region = dict(area)
                template_region.update(updates)
                self._save_template(
                    region_id,
                    self._template_image_for_region(image, template_region),
                )
                # 스케줄러에 갱신된 영역 반영
                if self._scheduler.is_running:
                    self._scheduler.remove_region(region_id)
                    for r in self._config.regions:
                        if r["id"] == region_id:
                            self._scheduler.add_region(r)
                            break
                if self._device_manager:
                    try:
                        self._device_manager.set_task_label(region_id, new_label)
                    except Exception:
                        pass
            elif dialog.reselect_requested:
                # 재선택 — RegionEditor로 기존 영역 편집
                QTimer.singleShot(100, lambda: self._start_bar_area_edit(region_id, area))

    def _start_bar_area_edit(self, region_id: str, area: dict) -> None:
        """Bar 타입 영역을 RegionEditor로 편집 (바 탐지 미리보기 포함)."""
        if self._region_editor is not None:
            self._region_editor.close()
            self._region_editor = None
        QTimer.singleShot(200, lambda: self._create_region_editor(region_id, area))

    def _create_region_editor(self, region_id: str, area: dict) -> None:
        from ui.region_editor import RegionEditor  # pyright: ignore[reportImplicitRelativeImport]

        self._region_editor = RegionEditor(
            region_id=region_id,
            area=area,
            bar_detect_fn=self._bar_finder.find,
        )
        self._region_editor.area_edited.connect(self._on_region_editor_confirmed)
        self._region_editor.cancelled.connect(self._on_region_editor_cancelled)
        self._region_editor.show()

    def _on_region_editor_confirmed(self, region_id: str, new_area: dict) -> None:
        if self._region_editor is not None:
            self._region_editor.deleteLater()
            self._region_editor = None
        self._update_region_area(region_id, new_area)

    def _on_region_editor_cancelled(self) -> None:
        if self._region_editor is not None:
            self._region_editor.deleteLater()
            self._region_editor = None

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
        ocr_qt_rect = None
        if region_type == "ocr":
            # OCR: 숫자% 읽기
            mode, target, _, prefer_percent = self._get_ocr_mode_settings(area)
            detected_value = self._ocr_reader.read_progress(
                self._crop_ocr_image_by_config(image, area),
                min_value=0.0,
                max_value=target,
                prefer_percent_sign=prefer_percent,
                allow_percent_sign=prefer_percent,
            )
            if detected_value is None:
                last_state = self._last_firebase_state.get(region_id, {})
                progress_val = float(last_state.get("p", 0.0))
            else:
                progress_val = self._normalize_ocr_progress(
                    mode, detected_value, target
                )
            if all(
                isinstance(area.get(k), (int, float))
                for k in ("ocr_left", "ocr_top", "ocr_right", "ocr_bottom")
            ):
                ocr_area = {
                    "monitor": area.get("monitor", 0),
                    "x": area["x"] + int(area.get("ocr_left", 0)),
                    "y": area["y"] + int(area.get("ocr_top", 0)),
                    "width": int(area.get("ocr_right", area["width"]))
                    - int(area.get("ocr_left", 0)),
                    "height": int(area.get("ocr_bottom", area["height"]))
                    - int(area.get("ocr_top", 0)),
                }
                if area.get("abs_x") is not None and area.get("abs_y") is not None:
                    ocr_area["abs_x"] = int(area["abs_x"]) + int(
                        area.get("ocr_left", 0)
                    )
                    ocr_area["abs_y"] = int(area["abs_y"]) + int(area.get("ocr_top", 0))
                ocr_qt_rect = self._mss_to_qt_rect(ocr_area)
        else:
            # 바 — 원본 영역 내 bar 오프셋으로 크롭하여 분석
            bar_image = image.crop(
                (
                    area.get("bar_left", 0),
                    area.get("bar_top", 0),
                    area.get("bar_right", image.width),
                    area.get("bar_bottom", image.height),
                )
            )
            direction = area.get("direction", "horizontal")
            target_color_raw = area.get("target_color")
            if area.get("bar_mode") == "color" and target_color_raw:
                tc = tuple(int(c) for c in target_color_raw[:3])
                result = self._analyzer.analyze_by_color(
                    bar_image, tc, direction=direction  # type: ignore[arg-type]
                )
            else:
                result = self._analyzer.analyze(bar_image, direction=direction)

            progress_val = result.progress
            # 바 영역 사각형 (화면 좌표)
            bar_area = {
                "monitor": area.get("monitor", 0),
                "x": area["x"] + area.get("bar_left", 0),
                "y": area["y"] + area.get("bar_top", 0),
                "width": area.get("bar_right", area["width"]) - area.get("bar_left", 0),
                "height": area.get("bar_bottom", area["height"])
                - area.get("bar_top", 0),
            }
            if area.get("abs_x") is not None and area.get("abs_y") is not None:
                bar_area["abs_x"] = int(area["abs_x"]) + int(area.get("bar_left", 0))
                bar_area["abs_y"] = int(area["abs_y"]) + int(area.get("bar_top", 0))
            bar_qt_rect = self._mss_to_qt_rect(bar_area)
        # 4. 뷰어 생성 + 표시
        if self._region_viewer is not None:
            try:
                self._region_viewer.close()
            except RuntimeError:
                pass

        self._region_viewer = RegionViewer(
            region_rect,
            bar_qt_rect,
            progress_val,
            ocr_qt_rect,
            region_type,
        )
        self._region_viewer.closed.connect(self._on_region_viewer_closed)
        self._region_viewer.show()

    def _mss_to_qt_rect(self, area: dict) -> QRect:
        """mss 좌표를 Qt 위젯 좌표로 변환한다."""
        from ui.screen_mapper import mss_to_qt_widget  # pyright: ignore[reportImplicitRelativeImport]

        return mss_to_qt_widget(area)

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

    def _update_hw_ui(self) -> None:
        """CPU/GPU/RAM 사용량을 읽어 메인 윈도우에 반영한다."""
        stats = collect_stats()
        if stats:
            self._main_window.update_hw_stats(stats)

    def _on_system_suspend(self) -> None:
        """PC 절전 진입 시 호출된다."""
        log.info("시스템 절전 진입 감지")
        if self._device_manager:
            threading.Thread(
                target=self._device_manager.set_sleep, daemon=True
            ).start()

    def _on_system_resume(self) -> None:
        """PC 절전 복귀 시 호출된다."""
        log.info("시스템 절전 복귀 감지")
        if self._device_manager:
            is_monitoring = self._scheduler.is_running
            threading.Thread(
                target=self._device_manager.set_monitoring,
                args=(is_monitoring,),
                daemon=True,
            ).start()

    def _set_display_required(self, required: bool) -> None:
        """시스템 절전 방지를 설정/해제한다.

        모니터링 중에는 ES_SYSTEM_REQUIRED | ES_CONTINUOUS를 설정하여
        Windows가 시스템 절전모드로 전환하지 않도록 한다.
        모니터 절전은 허용한다(화면 캡처는 모니터 꺼진 상태에서도 가능).
        모니터링 정지 시 ES_CONTINUOUS만 설정하여 정상 절전으로 복귀한다.
        """
        try:
            if required:
                # ES_CONTINUOUS | ES_SYSTEM_REQUIRED
                ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)
                log.info("시스템 절전 방지 설정")
            else:
                # ES_CONTINUOUS only — 정상 절전 복귀
                ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
                log.info("시스템 절전 방지 해제")
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
            for r in regions:
                if r.get("type", "bar") == "ocr":
                    self._ocr_reader.reset_cache(r["id"])
            self._scheduler.start(regions, interval)
            self._main_window.set_monitoring_state(True, interval)
            # 미체크(비활성) 영역 카드는 idle 상태로 표시
            disabled = [
                r for r in self._config.regions if not r.get("enabled", True)
            ]
            for r in disabled:
                self._main_window.set_region_task_status(r["id"], "idle")
            self._set_runtime_hint("ProgressEye - 모니터링 중")
            log.info("모니터링 시작 (%d개 영역, %d초 주기)", len(regions), interval)
            self._set_display_required(True)
            if self._device_manager:
                self._device_manager.set_monitoring(True)
                # 미체크(비활성) 작업을 idle 상태로 RTDB에 기록
                if disabled:
                    idle_batch = {r["id"]: {"s": "i"} for r in disabled}
                    self._device_manager.sync_tasks(idle_batch)
            # 템플릿 이미지가 없는 영역은 현재 화면으로 템플릿 생성 (앱 재시작 후 복원된 영역)
            for r in regions:
                rid = r["id"]
                if rid not in self._template_images:
                    try:
                        tpl_image = self._capturer.capture(r)
                        self._save_template(
                            rid,
                            self._template_image_for_region(tpl_image, r),
                        )
                        log.debug("[모니터링 시작] %s 템플릿 이미지 생성", rid)
                    except Exception as exc:
                        log.debug("[모니터링 시작] %s 템플릿 생성 실패: %s", rid, exc)

    def _on_capture_from_worker(self, region_id: str, image: PILImage.Image) -> None:
        """Timer 스레드에서 호출 — ThreadPoolExecutor로 병렬 분석 제출.

        각 영역의 분석(OCR/바)을 독립 스레드에서 병렬 실행한다.
        이전 분석이 아직 진행 중인 영역은 스킵하여 큐 쌓임을 방지한다.
        UI 업데이트는 _on_capture 내부에서 action_queue를 통해 메인 스레드로 전달된다.
        """
        with self._capturing_lock:
            if region_id in self._capturing_regions:
                log.debug("[%s] 이전 분석 진행 중 — 캡처 스킵", region_id)
                return
            self._capturing_regions.add(region_id)

        def _run() -> None:
            try:
                self._on_capture(region_id, image)
            except Exception as exc:
                log.error("[%s] 분석 스레드 오류: %s", region_id, exc)
            finally:
                with self._capturing_lock:
                    self._capturing_regions.discard(region_id)

        self._analysis_executor.submit(_run)

    def _on_cycle_complete_from_worker(self) -> None:
        """Timer 스레드에서 호출 — 메인 스레드로 마샬링."""
        self._action_queue.put(self._on_cycle_complete)

    def _on_capture(self, region_id: str, image: PILImage.Image) -> None:
        """캡처 콜백 — 분석은 백그라운드 스레드, UI 업데이트는 action_queue로 메인 스레드 전달."""
        if not self._scheduler.is_running:
            return
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
        progress_unit = "%"
        apply_image_change_guard = region_type in {"bar", "ocr"}

        # ── 이미지 변경 감지 ──
        IMAGE_CHANGE_THRESHOLD_BAR = 0.85
        IMAGE_CHANGE_THRESHOLD_OCR = 0.85
        image_change_threshold = (
            IMAGE_CHANGE_THRESHOLD_OCR
            if region_type == "ocr"
            else IMAGE_CHANGE_THRESHOLD_BAR
        )
        if apply_image_change_guard and region_id not in self._template_images:
            # 템플릿 없음 (영역 등록 전 복원된 경우) — 유사도 검사 생략
            log.debug("[%s] 템플릿 이미지 없음 — 유사도 검사 생략", region_id)
        elif apply_image_change_guard:
            try:
                # 동적 진행 영역은 마스킹해서 화면 변경 감지 오탐을 줄인다.
                bar_bbox = None
                if region_type == "bar":
                    bl = region_config.get("bar_left")
                    br = region_config.get("bar_right")
                    if bl is not None and br is not None:
                        # 탐지된 바 경계가 게이지 내부를 가리킬 수 있으므로
                        # 바깥쪽으로 확장해 border 픽셀이 UI 프레임 위에 오도록 한다.
                        _EXPAND = 6
                        _bbox = (
                            max(0, bl - _EXPAND),
                            max(0, region_config.get("bar_top", 0) - _EXPAND),
                            min(image.width, br + _EXPAND),
                            min(image.height, region_config.get("bar_bottom", image.height) + _EXPAND),
                        )
                        # bar_bbox가 캡처 이미지의 70% 이상을 덮으면 마스킹 생략
                        # (전체가 바 영역이면 마스킹 후 양쪽 다 회색 → 유사도 항상 높음)
                        _img_area = image.width * image.height
                        _bbox_area = (_bbox[2] - _bbox[0]) * (_bbox[3] - _bbox[1])
                        if _img_area > 0 and _bbox_area / _img_area < 0.70:
                            bar_bbox = _bbox
                elif region_type == "ocr":
                    left_raw = region_config.get("ocr_left")
                    top_raw = region_config.get("ocr_top")
                    right_raw = region_config.get("ocr_right")
                    bottom_raw = region_config.get("ocr_bottom")
                    if (
                        isinstance(left_raw, (int, float))
                        and isinstance(top_raw, (int, float))
                        and isinstance(right_raw, (int, float))
                        and isinstance(bottom_raw, (int, float))
                    ):
                        left_n, top_n, right_n, bottom_n = self._normalize_ocr_region(
                            (
                                int(left_raw),
                                int(top_raw),
                                int(right_raw),
                                int(bottom_raw),
                            ),
                            image.width,
                            image.height,
                        )
                        bar_bbox = (left_n, top_n, right_n, bottom_n)
                similarity = self._check_image_similarity(
                    self._template_images[region_id],
                    image,
                    bar_bbox=bar_bbox,
                    similarity_mode=region_type,
                )
            except Exception as exc:
                log.warning("[%s] 이미지 유사도 계산 실패: %s", region_id, exc)
                similarity = 1.0  # 실패 시 유사하다고 간주하고 모니터링 계속
            log.info(
                "[%s] 이미지 유사도: %.4f (threshold: %.1f)",
                region_id,
                similarity,
                image_change_threshold,
            )
            if similarity < image_change_threshold:
                last_progress = self._last_firebase_state.get(region_id, {}).get("p", 0)
                threshold = region_config.get("alert_threshold", 100)
                # color 모드는 대상 색상 특성상 100%에 못 미치는 값이 최대일 수 있으므로
                # 진행률이 0보다 크면 완료로 간주한다.
                # auto 모드는 캡처 주기 공백을 고려해 30% 버퍼를 준다 (기존 10%→30%).
                bar_mode = region_config.get("bar_mode", "auto")
                if bar_mode == "color":
                    near_completion = last_progress > 0
                else:
                    near_completion = last_progress >= threshold - 30
                if near_completion:
                    # 완료 처리
                    log.info(
                        "[이미지 변경] %s — 화면 소멸 (%.1f%%, mode=%s) → 완료 처리 (유사도: %.2f)",
                        label,
                        last_progress,
                        bar_mode,
                        similarity,
                    )
                    self._alerted_regions[region_id] = last_progress
                    self._last_firebase_state[region_id] = {"p": round(last_progress, 1), "s": "c"}
                    self._pending_firebase_batch[region_id] = self._last_firebase_state[region_id]
                    complete_msg = t("image_changed_completed").format(
                        label=label, progress=last_progress
                    )
                    self._action_queue.put(
                        lambda _msg=complete_msg: self._notify(
                            _msg,
                            system=True,
                        )
                    )
                    if self._device_manager:
                        self._device_manager.push_alert(
                            "image_change", "ProgressEye", complete_msg
                        )
                    # 완료 처리된 작업은 스케줄러에서 제거 (반복 알림 방지)
                    self._scheduler.remove_region(region_id)
                    self._action_queue.put(
                        lambda _id=region_id: self._main_window.set_region_task_status(_id, "completed")
                    )
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
                    self._action_queue.put(
                        lambda _msg=warn_msg, _title=stopped_msg: self._notify(
                            _msg,
                            system=True,
                            title=_title,
                        )
                    )
                    if self._device_manager:
                        self._device_manager.push_alert(
                            "image_change", "ProgressEye", warn_msg
                        )
                    # UI에 작업 중지 상태 표시, Firebase에 stopped 상태 기록
                    _stopped_p = round(last_progress, 1)
                    self._last_firebase_state[region_id] = {"p": _stopped_p, "s": "s"}
                    self._pending_firebase_batch[region_id] = {"p": _stopped_p, "s": "s"}
                    self._action_queue.put(
                        lambda _id=region_id: self._main_window.set_region_task_status(_id, "stopped")
                    )
                    self._scheduler.remove_region(region_id)
                    # 모든 영역이 제외되면 모니터링 자동 정지
                    if self._scheduler.region_count == 0:
                        log.info("모든 영역이 모니터링에서 제외됨 — 자동 정지")
                        self._action_queue.put(self._auto_stop_monitoring)
                # 템플릿은 작업 삭제 시에만 삭제 — 여기서는 유지
                return

        progress: float | None = None
        if region_type == "ocr":
            # OCR로 숫자% 읽기
            mode, target, progress_unit, prefer_percent = self._get_ocr_mode_settings(
                region_config
            )
            _ocr_crop = self._crop_ocr_image_by_config(image, region_config)
            detected_value = self._ocr_reader.read_progress(
                _ocr_crop,
                region_id=region_id,
                min_value=0.0,
                max_value=target,
                prefer_percent_sign=prefer_percent,
                allow_percent_sign=prefer_percent,
            )
            if detected_value is None:
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
                    last_state = self._last_firebase_state.get(region_id, {})
                    fallback_progress = last_state.get("p")
                    if isinstance(fallback_progress, (int, float)):
                        progress = float(fallback_progress)
                        log.debug(
                            "[%s] OCR miss fallback to last progress: %.1f%%",
                            region_id,
                            progress,
                        )
                    else:
                        log.warning("[%s] OCR 숫자 인식 실패", region_id)
                        return
            else:
                progress = self._normalize_ocr_progress(mode, detected_value, target)
            if self._debug_mode:
                self._debug_save_ocr(region_id, _ocr_crop, detected_value, progress)
        else:
            # 바 — 원본 영역에서 bar 오프셋으로 크롭하여 분석 (bar_finder 불필요)
            bar_image = image.crop(
                (
                    region_config.get("bar_left", 0),
                    region_config.get("bar_top", 0),
                    region_config.get("bar_right", image.width),
                    region_config.get("bar_bottom", image.height),
                )
            )
            direction = region_config.get("direction", "horizontal")
            target_color_raw = region_config.get("target_color")
            if region_config.get("bar_mode") == "color" and target_color_raw:
                tc: tuple[int, int, int] = tuple(int(c) for c in target_color_raw[:3])  # type: ignore[assignment]
                result = self._analyzer.analyze_by_color(bar_image, tc, direction=direction)
            else:
                result = self._analyzer.analyze(bar_image, direction=direction)
            progress = result.progress

            if self._debug_mode:
                self._debug_save_bar(
                    region_id, bar_image, progress,
                    region_config.get("bar_mode", "auto"),
                    target_color_raw,
                )

        if progress is None:
            return

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
            self._action_queue.put(
                lambda _id=region_id: self._main_window.set_region_task_status(_id, "running")
            )

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
        self._set_runtime_hint(f"ProgressEye - {label}: {progress:.1f}{progress_unit}")
        # UI 업데이트 — 큐로 메인 스레드 전달
        self._action_queue.put(
            lambda _id=region_id, _p=progress, _l=label, _u=progress_unit: (
                self._main_window.update_progress(_id, _p, _l, progress_unit=_u)
            )
        )

        # ── 완료 후 시나리오 감지 ──
        threshold = region_config.get("alert_threshold", 100)
        try:
            threshold_value = float(threshold)
        except (TypeError, ValueError):
            threshold_value = 100.0
        if threshold_value >= 100.0:
            reached_completion = progress >= 100.0
            below_completion = progress < 100.0
        else:
            reached_completion = progress >= threshold_value
            below_completion = progress < threshold_value
        if region_id in self._alerted_regions:
            alert_progress = self._alerted_regions[region_id]
            self._post_completion_fails.pop(
                region_id, None
            )  # OCR 성공 → 실패 카운터 리셋
            if below_completion:
                # 임계값 아래로 하락 → 재알람 허용 (알림 없이 해제만)
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
            int(threshold_value),
            region_id in self._alerted_regions,
        )
        if region_id not in self._alerted_regions and reached_completion:
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
                region_id,
                progress,
                int(threshold_value),
                elapsed_min,
                delay_minutes,
            )
            if elapsed_min >= delay_minutes:
                self._alerted_regions[region_id] = progress
                self._completion_first_reached.pop(region_id, None)
                alert_msg = t("alert_triggered").format(
                    label=label,
                    progress=progress,
                )
                log.info("[완료 알람] %s", alert_msg)
                self._action_queue.put(
                    lambda _msg=alert_msg: self._notify(
                        _msg,
                        system=True,
                    )
                )
                if self._device_manager:
                    self._device_manager.push_alert(
                        "completion", "ProgressEye", alert_msg
                    )
                # 완료 확정 → 해당 영역 모니터링 체크 해제
                self._action_queue.put(
                    lambda _id=region_id: self._config.update_region(_id, {"enabled": False})
                )
                self._scheduler.remove_region(region_id)
                self._action_queue.put(
                    lambda _id=region_id: self._main_window.set_region_task_status(_id, "completed")
                )
                if self._scheduler.region_count == 0:
                    log.info("모든 영역 완료 — 자동 정지")
                    self._action_queue.put(self._auto_stop_monitoring)
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
                # 프리징 시작 시점 — 카드 상태 + 트레이 알림 + RTDB 알림
                self._action_queue.put(
                    lambda _id=region_id: self._main_window.set_region_task_status(_id, "frozen")
                )
                stall_msg = t("stall_detected").format(
                    label=label, minutes=freeze_state.frozen_minutes
                )
                self._action_queue.put(
                    lambda _msg=stall_msg: self._notify(
                        _msg,
                        system=True,
                    )
                )
                if self._device_manager:
                    self._device_manager.push_alert("stall", "ProgressEye", stall_msg)

    def _on_cycle_complete(self) -> None:
        """캐프쳐 사이클 완료 — 배치 Firebase 전송을 워커 스레드에서 수행."""
        dm = self._device_manager
        if not dm:
            return
        # 메인 스레드에서 배치 스냅샷 후 클리어 (UI 불록킹 방지)
        batch = dict(self._pending_firebase_batch)
        self._pending_firebase_batch.clear()
        threading.Thread(
            target=self._sync_firebase_worker,
            args=(dm, batch),
            daemon=True,
            name="firebase-sync",
        ).start()

    def _sync_firebase_worker(self, dm: DeviceManager, batch: dict) -> None:
        """워커 스레드: Firebase RTDB 전송 (UI 스레드 외부)."""
        try:
            if batch:
                dm.sync_tasks(batch)
            self._sync_stats_if_due()
        except Exception as exc:
            log.debug("Firebase 배치 전송 실패: %s", exc)

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
        if self._quitting:
            return
        log.info("ProgressEye 종료")
        self._scheduler.stop()
        self._analysis_executor.shutdown(wait=False, cancel_futures=True)
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
        self._do_quit()

    def _do_quit(self) -> None:
        """앱 종료 (메인 스레드)."""
        if self._quitting:
            return
        self._quitting = True

        if self._poll_timer.isActive():
            self._poll_timer.stop()
        if self._cmd_poll_timer.isActive():
            self._cmd_poll_timer.stop()
        setattr(self._main_window, "_really_quit", True)
        self._main_window.hide()
        self._main_window.close()
        self._app.processEvents()
        self._app.exit(0)
        self._app.quit()

    def _debug_save_bar(
        self,
        region_id: str,
        bar_image: "PILImage.Image",
        progress: float,
        bar_mode: str,
        target_color: "list | None",
    ) -> None:
        """디버그 모드: bar 이미지를 순차적으로 temp/debug_capture/ 에 저장한다."""
        import numpy as _np

        debug_dir = pathlib.Path(__file__).parent / "temp" / "debug_capture"
        debug_dir.mkdir(parents=True, exist_ok=True)

        counter_attr = f"_debug_counter_{region_id}"
        n = getattr(self, counter_attr, 0) + 1
        setattr(self, counter_attr, n)

        fname = f"{region_id}_{n:04d}_p{progress:.1f}.png"
        bar_image.save(str(debug_dir / fname))

        arr = _np.array(bar_image.convert("RGB"), dtype=_np.uint8)
        unique, counts = _np.unique(arr.reshape(-1, 3), axis=0, return_counts=True)
        top5 = sorted(zip(counts.tolist(), [tuple(int(c) for c in u) for u in unique]), reverse=True)[:5]
        tc_str = f"RGB{tuple(target_color[:3])}" if target_color else "None"
        log.info(
            "[디버그 캡처] %s #%d — progress=%.1f%% mode=%s target=%s top_pixels=%s → %s",
            region_id, n, progress, bar_mode, tc_str,
            [(rgb, cnt) for cnt, rgb in top5],
            fname,
        )

    def _debug_save_ocr(
        self,
        region_id: str,
        ocr_image: "PILImage.Image",
        detected_value: "float | None",
        progress: "float | None",
    ) -> None:
        """디버그 모드: OCR 크롭 이미지를 순차적으로 temp/debug_capture/ 에 저장한다."""
        debug_dir = pathlib.Path(__file__).parent / "temp" / "debug_capture"
        debug_dir.mkdir(parents=True, exist_ok=True)

        counter_attr = f"_debug_counter_{region_id}"
        n = getattr(self, counter_attr, 0) + 1
        setattr(self, counter_attr, n)

        det_str = f"{detected_value:.1f}" if detected_value is not None else "miss"
        prog_str = f"{progress:.1f}" if progress is not None else "none"
        fname = f"{region_id}_{n:04d}_det{det_str}_p{prog_str}.png"
        ocr_image.save(str(debug_dir / fname))

        log.info(
            "[디버그 OCR] %s #%d — detected=%s progress=%s%% size=%dx%d → %s",
            region_id, n, det_str, prog_str,
            ocr_image.width, ocr_image.height,
            fname,
        )

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
        self,
        img1: PILImage.Image,
        img2: PILImage.Image,
        bar_bbox: tuple[int, int, int, int] | None = None,
        similarity_mode: str | None = None,
    ) -> float:
        """두 이미지의 유사도를 반환한다 (0.0~1.0).

        bar_bbox가 주어지면 해당 영역을 동일 상수로 마스킹하여
        게이지 변화가 유사도에 영향을 주지 않도록 한다.
        64x64 grayscale 다운스케일 후 numpy 상관계수로 비교.
        """
        import cv2
        import numpy as np

        # 진행률 바/OCR의 동적 영역을 마스킹해 오탐을 줄인다.
        if bar_bbox is not None:
            left, top, right, bottom = bar_bbox
            img1 = img1.copy()
            img2 = img2.copy()
            from PIL import ImageDraw

            width, height = img1.size
            left = max(0, min(width, int(left)))
            top = max(0, min(height, int(top)))
            right = max(0, min(width, int(right)))
            bottom = max(0, min(height, int(bottom)))

            bar_w = right - left
            bar_h = bottom - top
            if bar_w > 0 and bar_h > 0:
                # bar/ocr 모두: 동적 영역(게이지 바 전체 또는 숫자)을 회색으로 마스킹하고
                # 주변 UI를 비교해 실제 화면 변경 여부를 판단한다.
                draw1 = ImageDraw.Draw(img1)
                draw2 = ImageDraw.Draw(img2)
                draw1.rectangle([left, top, right, bottom], fill=(128, 128, 128))
                draw2.rectangle([left, top, right, bottom], fill=(128, 128, 128))

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
        qimg = QImage(
            data,
            pil_image.width,
            pil_image.height,
            pil_image.width * 3,
            QImage.Format.Format_RGB888,
        )
        return qimg.copy()  # deep copy — Python buffer 수명과 분리


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
