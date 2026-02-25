"""ProgressEye PC Agent 엔트리포인트.

영역 선택 → 바 탐지 → 전환점 분석 → 진행률 표시 파이프라인을 실행한다.
MVP 단계: Firebase 연동 없이 로컬 동작만 구현.
"""

# pyright: reportMissingImports=false, reportMissingModuleSource=false, reportMissingTypeArgument=false

import queue
import sys
import uuid
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
from core.bar_analyzer import BarAnalyzer  # pyright: ignore[reportImplicitRelativeImport]
from core.bar_finder import BarFinder  # pyright: ignore[reportImplicitRelativeImport]
from core.capturer import ScreenCapturer  # pyright: ignore[reportImplicitRelativeImport]
from core.freeze_detector import FreezeDetector  # pyright: ignore[reportImplicitRelativeImport]
from core.scheduler import CaptureScheduler  # pyright: ignore[reportImplicitRelativeImport]
from ui.area_selector import AreaSelector  # pyright: ignore[reportImplicitRelativeImport]
from ui.color_picker import BarPreviewDialog  # pyright: ignore[reportImplicitRelativeImport]
from core.ocr_reader import OcrReader  # pyright: ignore[reportImplicitRelativeImport]
from ui.ocr_preview import OcrPreviewDialog  # pyright: ignore[reportImplicitRelativeImport]
from ui.region_viewer import RegionViewer  # pyright: ignore[reportImplicitRelativeImport]
from ui.main_window import MainWindow  # pyright: ignore[reportImplicitRelativeImport]
from ui.tray_icon import TrayIcon  # pyright: ignore[reportImplicitRelativeImport]
from ui.settings_dialog import SettingsDialog  # pyright: ignore[reportImplicitRelativeImport]
from utils.logger import log  # pyright: ignore[reportImplicitRelativeImport]
from utils.i18n import set_language  # pyright: ignore[reportImplicitRelativeImport]


class ProgressEyeApp:
    """ProgressEye 메인 애플리케이션.

    모든 모듈을 연결하고 전체 파이프라인을 관리한다.
    """

    def __init__(self) -> None:
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
        )
        self._google_oauth = GoogleOAuth()
        self._firebase_auth = FirebaseAuth()
        self._token_manager = TokenManager()
        self._firebase_id_token: str | None = None
        self._realtime_db: RealtimeDB | None = None
        self._device_manager: DeviceManager | None = None
        self._heartbeat_timer: QTimer | None = None
        self._editing_region_id: str | None = None  # 작업 수정 중인 영역 ID

        # UI
        self._main_window = MainWindow()
        self._tray = TrayIcon(
            on_show_window=self._show_main_window,
            on_quit=self._quit,
        )
        self._area_selector: AreaSelector | None = None
        self._region_viewer: RegionViewer | None = None
        self._task_counter = len(self._config.regions)
        self._selection_mode: str = "bar"  # "bar" 또는 "ocr"

        # 크로스-스레드 액션 큐 (pystray/Timer → Qt 메인 스레드)
        self._action_queue: queue.Queue[Callable[[], None]] = queue.Queue()
        self._poll_timer = QTimer()
        self._poll_timer.timeout.connect(self._process_queued_actions)
        self._poll_timer.start(50)

        # 초기 언어 설정
        set_language(self._config.get("language", "ko"))

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
        # 기존 영역 복원
        self._restore_regions()

    def run(self) -> int:
        """애플리케이션을 실행한다."""
        log.info("ProgressEye 시작")
        if not self._try_auto_login():
            self._ensure_login()
        self._tray.start()
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
                retry = self._show_login_error(f"알 수 없는 로그인 오류: {exc}")
                if not retry:
                    log.warning("로그인 취소 - 비로그인 모드로 계속 진행")
                    return

    def _show_login_error(self, message: str) -> bool:
        """로그인 에러 다이얼로그를 표시하고 재시도 여부를 반환한다."""
        dialog = QMessageBox(self._main_window)
        dialog.setWindowTitle("로그인 실패")
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setText("Google/Firebase 인증에 실패했습니다.")
        dialog.setInformativeText(message)
        dialog.setStandardButtons(
            QMessageBox.StandardButton.Retry | QMessageBox.StandardButton.Cancel
        )
        dialog.setDefaultButton(QMessageBox.StandardButton.Retry)
        return dialog.exec() == QMessageBox.StandardButton.Retry

    def _do_login(self) -> None:
        """Google OAuth와 Firebase Auth를 통해 로그인한다."""
        google_result = self._google_oauth.sign_in()
        firebase_result = self._firebase_auth.sign_in_with_google(
            google_result["id_token"]
        )
        self._firebase_id_token = firebase_result["id_token"]

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

        # 프로필 저장
        try:
            import time

            profile_data = {
                "email": self._config.get("auth.email", ""),
                "displayName": self._token_manager.load_display_name() or "",
                "lastLoginAt": int(time.time() * 1000),
            }
            self._realtime_db.patch(f"users/{uid}/profile", profile_data)
        except Exception as exc:
            log.debug("프로필 저장 실패: %s", exc)

        # 하트비트 타이머 (30초)
        if self._heartbeat_timer:
            self._heartbeat_timer.stop()
        heartbeat_timer = QTimer()
        heartbeat_timer.timeout.connect(self._send_heartbeat)
        heartbeat_timer.start(30_000)
        self._heartbeat_timer = heartbeat_timer

    def _send_heartbeat(self) -> None:
        if self._device_manager:
            try:
                self._device_manager.heartbeat()
            except Exception as exc:
                log.debug("하트비트 전송 실패: %s", exc)

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

    def _restore_regions(self) -> None:
        """설정에 저장된 영역을 복원한다."""
        for region in self._config.regions:
            enabled = region.get("enabled", True)
            self._main_window.add_region_display(
                region["id"],
                region.get("label", region["id"]),
                region_type=region.get("type", "bar"),
                enabled=enabled,
            )

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
        bar_region = self._bar_finder.find(image)
        bar_image = image.crop(bar_region.bbox) if bar_region else image
        direction = bar_region.direction if bar_region else "horizontal"
        result = self._analyzer.analyze(bar_image, direction=direction)
        qimage = self._pil_to_qimage(image)
        dialog = BarPreviewDialog(
            image=qimage,
            full_image=image,
            bar_image=bar_image,
            detected_progress=result.progress,
            bar_region=bar_region,
        )

        if dialog.exec():
            self._task_counter += 1
            region_id = f"task_{self._task_counter:03d}"
            region = {
                "id": region_id,
                "label": dialog.task_name or f"작업 {self._task_counter}",
                "type": "bar",
                "monitor": area.get("monitor", 0),
                "x": area["x"],
                "y": area["y"],
                "width": area["width"],
                "height": area["height"],
                "direction": dialog.bar_region.direction
                if dialog.bar_region
                else direction,
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
        else:
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
                "label": dialog.task_name or f"작업 {self._task_counter}",
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
        else:
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
        log.info("영역 토글: %s → %s", region_id, "활성" if enabled else "비활성")

    def _update_region_area(self, region_id: str, area: dict) -> None:
        """재선택된 영역으로 기존 작업의 좌표를 업데이트하고 프리뷰를 다시 열다."""
        updates = {
            "monitor": area.get("monitor", 0),
            "x": area["x"],
            "y": area["y"],
            "width": area["width"],
            "height": area["height"],
        }
        self._config.update_region(region_id, updates)
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
        log.info("영역 삭제: %s", region_id)

    def _open_settings(self) -> None:
        """설정 다이얼로그를 열고 저장 시 반영한다."""
        current_interval = self._config.get("capture.interval_seconds", 30)
        current_lang = self._config.get("language", "ko")
        dialog = SettingsDialog(
            interval_seconds=current_interval,
            language=current_lang,
            parent=self._main_window,
        )
        if dialog.exec():
            new_interval = dialog.interval_seconds
            new_lang = dialog.language
            # 모니터링 간격 반영
            if new_interval != current_interval:
                self._config.set("capture.interval_seconds", new_interval)
                self._scheduler.update_interval(new_interval)
                log.info("모니터링 간격 변경: %d초", new_interval)
            # 언어 반영
            if new_lang != current_lang:
                self._config.set("language", new_lang)
                set_language(new_lang)
                self._main_window.refresh_texts()
                log.info("언어 변경: %s", new_lang)

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

        # 2. 영역 캡처
        try:
            image = self._capturer.capture(area)
        except Exception as e:
            log.error("영역 캡처 실패: %s", e)
            return

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
                self._main_window.update_progress(
                    region_id, dialog.progress, new_label
                )
                log.info("OCR 영역 수정: %s → %s", region_id, new_label)
            else:
                # 재선택 — 영역 선택 후 기존 작업 업데이트
                self._editing_region_id = region_id
                QTimer.singleShot(100, self._start_ocr_area_selection)
        else:
            # 바 타입: BarPreviewDialog
            bar_region = self._bar_finder.find(image)
            bar_image = image.crop(bar_region.bbox) if bar_region else image
            direction = bar_region.direction if bar_region else "horizontal"
            result = self._analyzer.analyze(bar_image, direction=direction)

            qimage = self._pil_to_qimage(image)
            dialog = BarPreviewDialog(
                image=qimage,
                full_image=image,
                bar_image=bar_image,
                detected_progress=result.progress,
                bar_region=bar_region,
            )
            dialog._task_name_input.setText(current_label)

            if dialog.exec():
                new_label = dialog.task_name or current_label
                updates: dict = {"label": new_label}
                if dialog.bar_region:
                    updates["direction"] = dialog.bar_region.direction
                self._config.update_region(region_id, updates)
                self._main_window.update_progress(
                    region_id, dialog.progress, new_label
                )
                log.info("바 영역 수정: %s → %s", region_id, new_label)
            else:
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
            # 바: 기존 로직 유지
            bar_region = self._bar_finder.find(image)
            bar_image = image.crop(bar_region.bbox) if bar_region else image
            direction = bar_region.direction if bar_region else "horizontal"
            result = self._analyzer.analyze(bar_image, direction=direction)
            progress_val = result.progress
            if bar_region is not None:
                bar_area = {
                    "monitor": area.get("monitor", 0),
                    "x": area["x"] + bar_region.left,
                    "y": area["y"] + bar_region.top,
                    "width": bar_region.width,
                    "height": bar_region.height,
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

    def _do_toggle_monitoring(self) -> None:
        """실제 모니터링 토글 (메인 스레드)."""
        if self._scheduler.is_running:
            self._scheduler.stop()
            self._main_window.set_monitoring_state(False)
            self._tray.update_tooltip("ProgressEye - 대기 중")
            log.info("모니터링 정지")
        else:
            regions = [r for r in self._config.regions if r.get("enabled", True)]
            if not regions:
                log.warning("활성화된 영역 없음 — 영역을 추가하거나 체크하세요")
                return
            interval = self._config.get("capture.interval_seconds", 30)
            self._scheduler.start(regions, interval)
            self._main_window.set_monitoring_state(True)
            self._tray.update_tooltip("ProgressEye - 모니터링 중")
            log.info("모니터링 시작 (%d개 영역, %d초 주기)", len(regions), interval)

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

        if region_type == "ocr":
            # OCR로 숫자% 읽기
            progress = self._ocr_reader.read_progress(image)
            if progress is None:
                log.warning("[%s] OCR 숫자 인식 실패", region_id)
                return
        else:
            # 바 영역 탐지 + 전환점 분석
            bar_region = self._bar_finder.find(image)
            direction = bar_region.direction if bar_region else "horizontal"
            bar_image = image.crop(bar_region.bbox) if bar_region else image
            result = self._analyzer.analyze(bar_image, direction=direction)
            progress = result.progress

        log.info("[%s] 진행률: %.1f%% (%s)", region_id, progress, region_type)

        # 멈춤 감지
        freeze_state = self._freeze_detector.update(region_id, progress)

        # Firebase 전송
        if self._realtime_db and self._firebase_id_token:
            uid = str(self._config.get("auth.uid", ""))
            device_id = str(self._config.get("auth.device_id", ""))
            if uid and device_id:
                import time

                task_data = {
                    "label": label,
                    "progress": round(progress, 1),
                    "status": "freeze" if freeze_state.is_frozen else "running",
                    "updatedAt": int(time.time() * 1000),
                }
                try:
                    path = f"users/{uid}/tasks/{device_id}/{region_id}"
                    self._realtime_db.patch(path, task_data)
                except Exception as exc:
                    log.debug("Firebase 전송 실패 [%s]: %s", region_id, exc)

        self._tray.update_tooltip(f"ProgressEye - {label}: {progress:.1f}%")
        # UI 업데이트 — 큐로 메인 스레드 전달
        self._action_queue.put(
            lambda _id=region_id, _p=progress, _l=label: (
                self._main_window.update_progress(_id, _p, _l)
            )
        )

        if freeze_state.is_frozen:
            log.warning(
                "[%s] 멈춤 감지: %.1f%%에서 %d분째",
                region_id,
                progress,
                freeze_state.frozen_minutes,
            )

    def _show_main_window(self) -> None:
        """메인 창을 표시한다. pystray 스레드에서 호출됨."""
        self._action_queue.put(self._do_show_main_window)

    def _do_show_main_window(self) -> None:
        """메인 창 표시 (메인 스레드)."""
        self._main_window.show()
        self._main_window.activateWindow()
        self._main_window.raise_()

    def _quit(self) -> None:
        """애플리케이션을 종료한다. pystray 스레드에서 호출됨."""
        log.info("ProgressEye 종료")
        self._scheduler.stop()
        self._capturer.close()
        if self._heartbeat_timer:
            self._heartbeat_timer.stop()
        if self._device_manager:
            try:
                self._device_manager.set_offline()
            except Exception:
                pass
        self._action_queue.put(self._do_quit)

    def _do_quit(self) -> None:
        """앱 종료 (메인 스레드)."""
        self._poll_timer.stop()
        setattr(self._main_window, "_really_quit", True)
        self._main_window.close()
        self._app.quit()

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
    """메인 함수."""
    app = ProgressEyeApp()
    sys.exit(app.run())


if __name__ == "__main__":
    main()
