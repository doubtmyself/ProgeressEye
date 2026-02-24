"""ProgressEye PC Agent 엔트리포인트.

영역 선택 → 캡처 → 막대 분석 → 진행률 표시 파이프라인을 실행한다.
MVP 단계: Firebase 연동 없이 로컬 동작만 구현.
"""

import sys

from PIL import Image as PILImage
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QApplication

from config import Config
from core.bar_analyzer import BarAnalyzer
from core.bar_finder import BarFinder
from core.capturer import ScreenCapturer
from core.color_detector import ColorDetector
from core.freeze_detector import FreezeDetector
from core.scheduler import CaptureScheduler
from ui.area_selector import AreaSelector
from ui.color_picker import ColorPreviewDialog
from ui.main_window import MainWindow
from ui.tray_icon import TrayIcon
from utils.logger import log


class ProgressEyeApp:
    """ProgressEye 메인 애플리케이션.

    모든 모듈을 연결하고 전체 파이프라인을 관리한다.
    """

    def __init__(self) -> None:
        self._app = QApplication(sys.argv)
        self._config = Config()
        self._capturer = ScreenCapturer()
        self._analyzer = BarAnalyzer()
        self._color_detector = ColorDetector()
        self._bar_finder = BarFinder()
        self._freeze_detector = FreezeDetector(
            timeout_minutes=self._config.get("freeze_detection.timeout_minutes", 5),
        )
        self._scheduler = CaptureScheduler(
            on_capture=self._on_capture,
            capturer=self._capturer,
        )

        # UI
        self._main_window = MainWindow()
        self._tray = TrayIcon(
            on_select_area=self._start_area_selection,
            on_toggle_monitoring=self._toggle_monitoring,
            on_show_window=self._show_main_window,
            on_quit=self._quit,
        )
        self._area_selector: AreaSelector | None = None
        self._task_counter = len(self._config.regions)

        # 시그널 연결
        self._main_window.select_area_requested.connect(self._start_area_selection)
        self._main_window.toggle_monitoring_requested.connect(self._toggle_monitoring)

        # 기존 영역 복원
        self._restore_regions()

    def run(self) -> int:
        """애플리케이션을 실행한다."""
        log.info("ProgressEye 시작")
        self._tray.start()
        self._main_window.show()
        return self._app.exec()

    def _restore_regions(self) -> None:
        """설정에 저장된 영역을 복원한다."""
        for region in self._config.regions:
            self._main_window.add_region_display(
                region["id"], region.get("label", region["id"])
            )

    def _start_area_selection(self) -> None:
        """영역 선택 오버레이를 시작한다.

        pystray 트레이 콜백은 별도 스레드에서 실행되므로
        QTimer.singleShot으로 Qt 메인 스레드 실행을 보장한다.
        """
        QTimer.singleShot(0, self._do_start_area_selection)

    def _do_start_area_selection(self) -> None:
        """실제 영역 선택 시작 (메인 스레드)."""
        log.info("영역 선택 시작")
        # 기존 셀렉터 정리 (이미 close된 경우 대비)
        if self._area_selector is not None:
            try:
                self._area_selector.hide()
            except RuntimeError:
                pass  # C++ 객체 이미 삭제됨
            try:
                self._area_selector.deleteLater()
            except RuntimeError:
                pass
            self._area_selector = None

        # 이전 오버레이가 화면에서 완전히 사라진 후 새 셀렉터 생성
        QTimer.singleShot(200, self._create_area_selector)

    def _create_area_selector(self) -> None:
        """AreaSelector를 생성하고 표시한다."""
        self._area_selector = AreaSelector()
        self._area_selector.area_selected.connect(self._on_area_selected)
        self._area_selector.cancelled.connect(self._on_area_cancelled)
        self._area_selector.show()

    def _on_area_selected(self, area: dict) -> None:
        """영역 선택 완료 시 호출.

        색상 감지 → 미리보기 다이얼로그 표시.
        """
        log.info("영역 선택됨: %s", area)

        # 선택 영역 캡처
        try:
            image = self._capturer.capture(area)
        except Exception as e:
            log.error("영역 캡처 실패: %s", e)
            return

        # 바 영역 자동 탐지 (OpenCV contour 기반)
        bar_region = self._bar_finder.find(image)
        bar_image = image.crop(bar_region.bbox) if bar_region else image

        # 크롭된 바에서 색상 감지 및 분석
        detection = self._color_detector.detect(bar_image)
        result = self._analyzer.analyze(
            bar_image, detection.fill_color, detection.empty_color
        )

        # 전체 이미지를 미리보기로 표시 (클릭으로 색상 지정)
        qimage = self._pil_to_qimage(image)
        dialog = ColorPreviewDialog(
            image=qimage,
            full_image=image,
            pil_image=bar_image,
            fill_color=detection.fill_color,
            empty_color=detection.empty_color,
            detected_progress=result.progress,
            bar_region=bar_region,
        )

        if dialog.exec():
            # 확인 — 영역 등록
            fill_color = dialog.fill_color
            empty_color = dialog.empty_color

            self._task_counter += 1
            region_id = f"task_{self._task_counter:03d}"

            region = {
                "id": region_id,
                "label": f"작업 {self._task_counter}",
                "monitor": area.get("monitor", 0),
                "x": area["x"],
                "y": area["y"],
                "width": area["width"],
                "height": area["height"],
                "fill_color": list(fill_color),
                "empty_color": list(empty_color),
                "color_tolerance": 30,
                "direction": bar_region.direction if bar_region else "horizontal",
            }

            self._config.add_region(region)
            self._main_window.add_region_display(region_id, region["label"])
            self._main_window.update_progress(
                region_id, result.progress, region["label"]
            )

            # 스케줄러에 추가 (실행 중이면)
            if self._scheduler.is_running:
                self._scheduler.add_region(region)

            log.info("영역 등록: %s (%.1f%%)", region_id, result.progress)
        else:
            # 재선택
            log.info("색상 미리보기에서 재선택 요청")
            QTimer.singleShot(100, self._start_area_selection)

    def _on_area_cancelled(self) -> None:
        """영역 선택 취소."""
        log.info("영역 선택 취소됨")
        if self._area_selector is not None:
            self._area_selector.deleteLater()
            self._area_selector = None

    def _toggle_monitoring(self) -> None:
        """모니터링 시작/정지 토글.

        pystray 스레드에서 호출될 수 있으므로 메인 스레드로 마셜링.
        """
        QTimer.singleShot(0, self._do_toggle_monitoring)

    def _do_toggle_monitoring(self) -> None:
        """실제 모니터링 토글 (메인 스레드)."""
        if self._scheduler.is_running:
            self._scheduler.stop()
            self._main_window.set_monitoring_state(False)
            self._tray.set_monitoring(False)
            self._tray.update_tooltip("ProgressEye - 대기 중")
            log.info("모니터링 정지")
        else:
            regions = self._config.regions
            if not regions:
                log.warning("등록된 영역 없음 — 영역 먼저 추가하세요")
                return
            interval = self._config.get('capture.interval_seconds', 30)
            self._scheduler.start(regions, interval)
            self._main_window.set_monitoring_state(True)
            self._tray.set_monitoring(True)
            self._tray.update_tooltip("ProgressEye - 모니터링 중")
            log.info("모니터링 시작 (%d개 영역, %d초 주기)", len(regions), interval)

    def _on_capture(self, region_id: str, image: PILImage.Image) -> None:
        """캡처 콜백 — 분석 + UI 업데이트.

        이 메서드는 백그라운드 스레드에서 호출된다.
        UI 업데이트는 QTimer.singleShot으로 메인 스레드에서 실행.
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

        empty_color = tuple(region_config["empty_color"])
        label = region_config.get("label", region_id)
        # 바 영역 탐지 + 적응형 분석 (방향 자동 감지)
        bar_region = self._bar_finder.find(image)
        direction = bar_region.direction if bar_region else "horizontal"
        bar_image = image.crop(bar_region.bbox) if bar_region else image
        result = self._analyzer.analyze_adaptive(
            bar_image, empty_color=empty_color, direction=direction
        )

        # 멈춤 감지
        freeze_state = self._freeze_detector.update(region_id, result.progress)

        # 툴팁 업데이트
        self._tray.update_tooltip(f"ProgressEye - {label}: {result.progress:.1f}%")

        # UI 업데이트 (메인 스레드)
        QTimer.singleShot(
            0,
            lambda: self._main_window.update_progress(
                region_id, result.progress, label
            ),
        )

        if freeze_state.is_frozen:
            log.warning(
                "[%s] 멈춤 감지: %.1f%%에서 %d분째",
                region_id,
                result.progress,
                freeze_state.frozen_minutes,
            )

    def _show_main_window(self) -> None:
        """메인 창을 표시한다.

        pystray 스레드에서 호출될 수 있으므로 메인 스레드로 마셜링.
        """
        QTimer.singleShot(0, self._do_show_main_window)

    def _do_show_main_window(self) -> None:
        """실제 메인 창 표시 (메인 스레드)."""
        self._main_window.show()
        self._main_window.activateWindow()
        self._main_window.raise_()
    def _quit(self) -> None:
        """애플리케이션을 종료한다.
        pystray 스레드에서 호출됨.
        _on_quit_clicked가 이후 tray.stop()을 호출하므로 여기서는 tray 정리 생략.
        """
        log.info("ProgressEye 종료")
        self._scheduler.stop()
        self._capturer.close()
        # QApplication.quit()는 이벤트 루프에 종료 이벤트를 포스팅 (스레드 안전)
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
