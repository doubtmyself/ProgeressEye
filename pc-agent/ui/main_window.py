"""메인 윈도우 모듈.

모니터링 상태, 등록된 영역의 진행률을 표시하고
영역 추가, 모니터링 시작/정지 기능을 제공한다.
"""

from datetime import datetime

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCloseEvent, QFont, QIcon, QMouseEvent
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QScrollArea,
    QFrame,
    QCheckBox,
    QSpinBox,
)

from utils.logger import log
from utils.i18n import t
from ui.login_start_dialog import LoginStartDialog
from ui.settings_dialog import SettingsOverlay, TutorialPage, WelcomePage

# ── Color Palette ──────────────────────────────────────────────
APP_BG = "#0f0f1a"
CARD_BG = "#1c1c30"
CARD_BORDER = "#2a2a45"
TITLE_TEXT = "#ffffff"
SUBTITLE_TEXT = "#8888aa"
STATUS_GREEN = "#4ade80"
STATUS_GRAY = "#666688"
CHECKBOX_BLUE = "#3b82f6"
CARD_LABEL = "#ffffff"
BAR_TRACK = "#252540"
BAR_GRAD_L = "#3b82f6"
BAR_GRAD_R = "#22d3ee"
BAR_TEXT = "#ffffff"
UPDATE_TEXT = "#666688"
DELETE_TEXT = "#666688"
DELETE_BG = "#2a2a45"
DELETE_BORDER = "#3a3a55"
BTN_ADD_BG = "#1c1c30"
BTN_ADD_TEXT = "#8888aa"
BTN_ADD_BORDER = "#3a3a55"
BTN_STOP_BG = "#ef4444"
BTN_START_BG = "#3b82f6"
BTN_ACTION_TEXT = "#ffffff"
EMPTY_TEXT = "#666688"
SCROLLBAR_BG = "#0f0f1a"
SCROLLBAR_HANDLE = "#2a2a45"


class RegionCard(QFrame):
    """모니터링 영역 카드 위젯."""

    toggled = pyqtSignal(str, bool)
    delete_requested = pyqtSignal(str)
    edit_requested = pyqtSignal(str)
    view_requested = pyqtSignal(str)
    threshold_changed = pyqtSignal(str, int)  # (region_id, threshold)
    delay_changed = pyqtSignal(str, int)  # (region_id, delay_minutes)
    test_stall_requested = pyqtSignal(str)
    test_complete_requested = pyqtSignal(str)

    def __init__(
        self,
        region_id: str,
        label: str,
        region_type: str = "bar",
        progress_unit: str = "%",
        alert_threshold: int = 100,
        alert_delay_minutes: int = 0,
        show_test_buttons: bool = False,
        bar_mode: str = "auto",
        target_color: list | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.region_id = region_id
        self._region_type = region_type
        self._progress_unit = progress_unit
        self._show_test_buttons = show_test_buttons
        self._bar_mode = bar_mode
        self._target_color = target_color
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setStyleSheet(
            f"RegionCard {{"
            f"  background: {CARD_BG};"
            f"  border: 1px solid {CARD_BORDER};"
            f"  border-radius: 12px;"
            f"  padding: 14px;"
            f"  margin: 4px 0px;"
            f"}}"
        )
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        type_text = t("type_ocr") if region_type == "ocr" else t("type_bar")
        self._label_text = label
        # ── Row 1: 작업 이름 (타입) 라벨 (큰 글씨, 볼드) ──
        self._label = QLabel(f"{label} ({type_text})")
        self._label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self._label.setStyleSheet(
            f"color: {CARD_LABEL}; background: transparent; border: none;"
        )
        layout.addWidget(self._label)

        # ── Row 1b: 분석 방식 + 색상 스와치 (bar 타입만) ──
        if region_type == "bar":
            mode_key = "bar_mode_color" if bar_mode == "color" else "bar_mode_auto"
            mode_row = QHBoxLayout()
            mode_row.setSpacing(6)
            self._mode_lbl = QLabel(f"· {t('bar_analysis_mode')}: {t(mode_key)}")
            mode_lbl = self._mode_lbl
            mode_lbl.setStyleSheet(
                f"color: {SUBTITLE_TEXT}; font-size: 11px; background: transparent; border: none;"
            )
            mode_row.addWidget(mode_lbl)
            if bar_mode == "color" and target_color and len(target_color) >= 3:
                r, g, b = int(target_color[0]), int(target_color[1]), int(target_color[2])
                swatch = QLabel()
                swatch.setFixedSize(14, 14)
                swatch.setStyleSheet(
                    f"background-color: rgb({r},{g},{b}); border: 1px solid #555; border-radius: 3px;"
                )
                swatch.setToolTip(f"RGB({r}, {g}, {b})")
                mode_row.addWidget(swatch)
            mode_row.addStretch()
            layout.addLayout(mode_row)

        # ── Row 2: 체크박스 + 모니터링 여부 라벨 (작은 글씨) ──
        header_row = QHBoxLayout()
        self._checkbox = QCheckBox()
        self._checkbox.setChecked(True)
        self._checkbox.setStyleSheet(
            f"QCheckBox::indicator {{"
            f"  width: 16px; height: 16px;"
            f"  border: 2px solid {CARD_BORDER};"
            f"  border-radius: 4px;"
            f"  background: {APP_BG};"
            f"}}"
            f"QCheckBox::indicator:checked {{"
            f"  background: {CHECKBOX_BLUE};"
            f"  border-color: {CHECKBOX_BLUE};"
            f"  image: none;"
            f"}}"
        )
        self._checkbox.stateChanged.connect(self._on_check_changed)
        self._checkbox.setToolTip(t("tooltip_checkbox"))
        header_row.addWidget(self._checkbox)
        self._type_label = QLabel(t("monitoring_check"))
        self._type_label.setStyleSheet(
            f"color: {SUBTITLE_TEXT};"
            f"background: transparent;"
            f"font-size: 11px;"
            f"border: none;"
            f"padding: 0px;"
        )
        header_row.addWidget(self._type_label)
        header_row.addStretch()
        layout.addLayout(header_row)

        # ── 작업 상태 라벨 (모니터링 중에만 표시) ──
        self._task_status_label = QLabel()
        self._task_status_label.setStyleSheet(
            "font-size: 12px; font-weight: bold;"
            " background: transparent; border: none; padding: 2px 0;"
        )
        self._task_status_label.hide()
        layout.addWidget(self._task_status_label)

        # ── Progress bar (percentage shown ON bar, no separate label) ──
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 1000)
        self._progress_bar.setValue(0)
        self._progress_bar.setFixedHeight(24)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setFormat(f"0.0{self._progress_unit}")
        self._progress_bar.setStyleSheet(
            f"QProgressBar {{"
            f"  text-align: center;"
            f"  font-size: 11px;"
            f"  font-weight: bold;"
            f"  color: {BAR_TEXT};"
            f"  background: {BAR_TRACK};"
            f"  border: none;"
            f"  border-radius: 8px;"
            f"}}"
            f"QProgressBar::chunk {{"
            f"  border-radius: 8px;"
            f"  background: qlineargradient("
            f"    x1:0, y1:0, x2:1, y2:0,"
            f"    stop:0 {BAR_GRAD_L}, stop:1 {BAR_GRAD_R}"
            f"  );"
            f"}}"
        )
        layout.addWidget(self._progress_bar)

        # ── Alert threshold row: 🔔 완료 알람 [80-100] % ──
        self._threshold_widget = QWidget()
        self._threshold_widget.setStyleSheet("background: transparent; border: none;")
        threshold_row = QHBoxLayout(self._threshold_widget)
        threshold_row.setContentsMargins(0, 0, 0, 0)
        self._threshold_label = QLabel(t("alert_threshold_label"))
        self._threshold_label.setStyleSheet(
            f"color: {SUBTITLE_TEXT}; font-size: 11px;"
            f" background: transparent; border: none;"
        )
        threshold_row.addWidget(self._threshold_label)

        spin_style = (
            f"QSpinBox {{"
            f"  background: {APP_BG};"
            f"  border: 1px solid {CARD_BORDER};"
            f"  border-radius: 4px;"
            f"  padding: 2px 6px;"
            f"  color: {TITLE_TEXT};"
            f"  font-size: 11px;"
            f"}}"
            f"QSpinBox:focus {{ border-color: {CHECKBOX_BLUE}; }}"
            f"QSpinBox::up-button {{ width: 20px; }}"
            f"QSpinBox::down-button {{ width: 20px; }}"
        )
        self._threshold_spin = QSpinBox()
        self._threshold_spin.setRange(80, 100)
        self._threshold_spin.setValue(alert_threshold)
        self._threshold_spin.setSuffix(t("alert_threshold_suffix"))
        self._threshold_spin.setStyleSheet(spin_style)
        self._threshold_spin.setFixedSize(110, 30)
        self._threshold_spin.valueChanged.connect(self._on_threshold_changed)
        self._threshold_spin.setToolTip(t("tooltip_threshold"))
        threshold_row.addWidget(self._threshold_spin)
        threshold_row.addStretch()
        layout.addWidget(self._threshold_widget)

        # ── Alert delay row: ⏱ 완료 확인 [0-60] 분 ──
        self._delay_widget = QWidget()
        self._delay_widget.setStyleSheet("background: transparent; border: none;")
        delay_row = QHBoxLayout(self._delay_widget)
        delay_row.setContentsMargins(0, 0, 0, 0)
        self._delay_label = QLabel(t("alert_delay_label"))
        self._delay_label.setStyleSheet(
            f"color: {SUBTITLE_TEXT}; font-size: 11px;"
            f" background: transparent; border: none;"
        )
        delay_row.addWidget(self._delay_label)

        self._delay_spin = QSpinBox()
        self._delay_spin.setRange(0, 60)
        self._delay_spin.setValue(alert_delay_minutes)
        self._delay_spin.setSuffix(t("alert_delay_suffix"))
        self._delay_spin.setStyleSheet(spin_style)
        self._delay_spin.setFixedSize(110, 30)
        self._delay_spin.valueChanged.connect(self._on_delay_changed)
        self._delay_spin.setToolTip(t("tooltip_delay"))
        delay_row.addWidget(self._delay_spin)
        delay_row.addStretch()
        layout.addWidget(self._delay_widget)

        # ── Bottom row: timestamp ──
        self._time_label = QLabel(t("card_standby"))
        self._time_label.setStyleSheet(
            f"color: {UPDATE_TEXT}; font-size: 11px;"
            f"background: transparent; border: none;"
        )
        layout.addWidget(self._time_label)

        # ── Button row: 작업 수정 + 영역보기 + 삭제 (왼쪽 정렬) ──
        btn_row = QHBoxLayout()

        btn_style = (
            f"QPushButton {{"
            f"  background: {DELETE_BG};"
            f"  border: 1px solid {DELETE_BORDER};"
            f"  border-radius: 4px;"
            f"  padding: 0 10px;"
            f"  font-size: 11px;"
            f"  color: {DELETE_TEXT};"
            f"}}"
            f"QPushButton:hover {{"
            f"  background: {CARD_BORDER};"
            f"}}"
        )

        self._btn_edit = QPushButton(t("btn_edit"))
        self._btn_edit.setFixedHeight(24)
        self._btn_edit.setStyleSheet(btn_style)
        self._btn_edit.clicked.connect(lambda: self.edit_requested.emit(self.region_id))
        self._btn_edit.setToolTip(t("tooltip_edit"))
        btn_row.addWidget(self._btn_edit)

        self._btn_view = QPushButton(t("btn_view"))
        self._btn_view.setFixedHeight(24)
        self._btn_view.setStyleSheet(btn_style)
        self._btn_view.clicked.connect(lambda: self.view_requested.emit(self.region_id))
        self._btn_view.setToolTip(t("tooltip_view"))
        btn_row.addWidget(self._btn_view)

        self._btn_delete = QPushButton(t("btn_delete"))
        self._btn_delete.setFixedHeight(24)
        self._btn_delete.setStyleSheet(btn_style)
        self._btn_delete.clicked.connect(
            lambda: self.delete_requested.emit(self.region_id)
        )
        self._btn_delete.setToolTip(t("tooltip_delete"))
        btn_row.addWidget(self._btn_delete)

        btn_row.insertStretch(0)

        # ── Test buttons: 프리징/완료 테스트 (FCM 파이프라인 검증용) ──
        test_row = QHBoxLayout()
        test_style = (
            f"QPushButton {{"
            f"  background: #1a1a35;"
            f"  border: 1px solid #3b82f6;"
            f"  border-radius: 4px;"
            f"  padding: 0 10px;"
            f"  font-size: 11px;"
            f"  color: #3b82f6;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background: #1e2a4a;"
            f"}}"
        )

        self._btn_test_stall = QPushButton(t("btn_test_stall"))
        self._btn_test_stall.setFixedHeight(24)
        self._btn_test_stall.setStyleSheet(test_style)
        self._btn_test_stall.clicked.connect(
            lambda: self.test_stall_requested.emit(self.region_id)
        )
        self._btn_test_stall.setToolTip(t("tooltip_test_stall"))
        test_row.addWidget(self._btn_test_stall)

        self._btn_test_complete = QPushButton(t("btn_test_complete"))
        self._btn_test_complete.setFixedHeight(24)
        self._btn_test_complete.setStyleSheet(test_style)
        self._btn_test_complete.clicked.connect(
            lambda: self.test_complete_requested.emit(self.region_id)
        )
        self._btn_test_complete.setToolTip(t("tooltip_test_complete"))
        test_row.addWidget(self._btn_test_complete)

        self._btn_test_stall.setVisible(self._show_test_buttons)
        self._btn_test_complete.setVisible(self._show_test_buttons)

        test_row.insertStretch(0)
        layout.addLayout(test_row)
        layout.addLayout(btn_row)

    def set_buttons_visible(self, visible: bool) -> None:
        """카드 버튼(작업 수정/영역보기/삭제/테스트)의 표시 여부를 설정한다.

        visible=False (모니터링 중): 수정/삭제 버튼·체크박스 숨김, 작업 상태 라벨 표시.
        visible=True (모니터링 정지): 수정/삭제 버튼·체크박스 표시, 작업 상태 라벨 숨김.
        """
        self._btn_edit.setVisible(visible)
        self._btn_view.setVisible(visible)
        self._btn_delete.setVisible(visible)
        self._btn_test_stall.setVisible(visible and self._show_test_buttons)
        self._btn_test_complete.setVisible(visible and self._show_test_buttons)
        # 모니터링 중: 체크박스 숨기고 작업 상태 라벨 표시
        self._checkbox.setVisible(visible)
        self._type_label.setVisible(visible)
        self._task_status_label.setVisible(not visible)

    def _on_check_changed(self, state: int) -> None:
        """체크박스 상태 변경 시 시그널을 발생시킨다."""
        enabled = state == Qt.CheckState.Checked.value
        self.toggled.emit(self.region_id, enabled)

    def _on_threshold_changed(self, value: int) -> None:
        """완료 알람 임계값 변경 시 시그널을 발생시킨다."""
        self.threshold_changed.emit(self.region_id, value)

    def _on_delay_changed(self, value: int) -> None:
        """완료 확인 지연 시간 변경 시 시그널을 발생시킨다."""
        self.delay_changed.emit(self.region_id, value)

    def update_progress(self, progress: float) -> None:
        """진행률을 업데이트한다."""
        self._progress_bar.setValue(int(progress * 10))
        self._progress_bar.setFormat(f"{progress:.1f}{self._progress_unit}")
        self._time_label.setText(
            t("card_update").format(time=datetime.now().strftime("%H:%M:%S"))
        )

    def set_progress_unit(self, progress_unit: str) -> None:
        """진행률 단위를 설정한다."""
        self._progress_unit = progress_unit

    def set_label(self, label: str) -> None:
        """라벨을 변경한다."""
        self._label_text = label
        type_text = t("type_ocr") if self._region_type == "ocr" else t("type_bar")
        self._label.setText(f"{label} ({type_text})")

    def set_checked(self, checked: bool) -> None:
        """체크박스 상태를 설정한다."""
        self._checkbox.setChecked(checked)

    def set_task_status(self, status: str) -> None:
        """모니터링 중 작업 상태를 설정한다.

        Args:
            status: "running" | "completed" | "stopped" | "frozen" | "idle"
        """
        if status == "running":
            self._task_status_label.setText(t("task_status_running"))
            self._task_status_label.setStyleSheet(
                "color: #4ade80; font-size: 12px; font-weight: bold;"
                " background: transparent; border: none;"
            )
        elif status == "completed":
            self._task_status_label.setText(t("task_status_completed"))
            self._task_status_label.setStyleSheet(
                "color: #4ade80; font-size: 12px; font-weight: bold;"
                " background: transparent; border: none;"
            )
        elif status == "stopped":
            self._task_status_label.setText(t("task_status_stopped"))
            self._task_status_label.setStyleSheet(
                "color: #f59e0b; font-size: 12px; font-weight: bold;"
                " background: transparent; border: none;"
            )
        elif status == "frozen":
            self._task_status_label.setText(t("task_status_frozen"))
            self._task_status_label.setStyleSheet(
                "color: #f59e0b; font-size: 12px; font-weight: bold;"
                " background: transparent; border: none;"
            )
        elif status == "idle":
            self._task_status_label.setText(t("task_status_idle"))
            self._task_status_label.setStyleSheet(
                "color: #6b7280; font-size: 12px; font-weight: bold;"
                " background: transparent; border: none;"
            )

    def refresh_texts(self) -> None:
        """언어 변경 시 카드 텍스트를 갱신한다."""
        self._btn_edit.setText(t("btn_edit"))
        self._btn_view.setText(t("btn_view"))
        self._btn_delete.setText(t("btn_delete"))
        type_text = t("type_ocr") if self._region_type == "ocr" else t("type_bar")
        self._label.setText(f"{self._label_text} ({type_text})")
        self._type_label.setText(t("monitoring_check"))
        self._threshold_label.setText(t("alert_threshold_label"))

        self._checkbox.setToolTip(t("tooltip_checkbox"))
        self._btn_edit.setToolTip(t("tooltip_edit"))
        self._btn_view.setToolTip(t("tooltip_view"))
        self._btn_delete.setToolTip(t("tooltip_delete"))
        self._threshold_spin.setToolTip(t("tooltip_threshold"))
        self._delay_label.setText(t("alert_delay_label"))
        self._delay_spin.setToolTip(t("tooltip_delay"))
        self._btn_test_stall.setText(t("btn_test_stall"))
        self._btn_test_stall.setToolTip(t("tooltip_test_stall"))
        self._btn_test_complete.setText(t("btn_test_complete"))
        self._btn_test_complete.setToolTip(t("tooltip_test_complete"))
        if self._region_type == "bar" and hasattr(self, "_mode_lbl"):
            mode_key = "bar_mode_color" if self._bar_mode == "color" else "bar_mode_auto"
            self._mode_lbl.setText(f"· {t('bar_analysis_mode')}: {t(mode_key)}")
        self._delay_spin.setSuffix(t("alert_delay_suffix"))
        self._threshold_spin.setSuffix(t("alert_threshold_suffix"))

    def set_warning(self, message: str) -> None:
        """카드에 경고 상태를 표시한다."""
        self._time_label.setText(message)
        self._time_label.setStyleSheet(
            f"color: #ef4444; font-size: 11px;"
            f"background: transparent; border: none; font-weight: bold;"
        )


class MainWindow(QMainWindow):
    """ProgressEye 메인 윈도우.

    모니터링 상태와 등록 영역의 진행률을 표시한다.
    """

    select_area_requested = pyqtSignal()
    select_ocr_area_requested = pyqtSignal()
    toggle_monitoring_requested = pyqtSignal()
    region_toggled = pyqtSignal(str, bool)
    region_delete_requested = pyqtSignal(str)
    region_view_requested = pyqtSignal(str)
    region_edit_requested = pyqtSignal(str)
    settings_requested = pyqtSignal()
    settings_saved = pyqtSignal(int, str, int)  # (interval, lang, freeze)
    settings_logout_requested = pyqtSignal()
    settings_reset_requested = pyqtSignal()
    settings_delete_account_requested = pyqtSignal()
    settings_withdrawal_expired_test_requested = pyqtSignal()
    settings_rejoin_expired_test_requested = pyqtSignal()
    settings_privacy_policy_requested = pyqtSignal()
    settings_third_party_licenses_requested = pyqtSignal()
    settings_bar_guide_requested = pyqtSignal()
    welcome_next_requested = pyqtSignal(str)  # (language)
    tutorial_next_requested = pyqtSignal()
    region_threshold_changed = pyqtSignal(str, int)  # (region_id, threshold)
    region_delay_changed = pyqtSignal(str, int)  # (region_id, delay_minutes)
    test_stall_requested = pyqtSignal(str)  # (region_id)
    test_complete_requested = pyqtSignal(str)  # (region_id)
    login_start_requested = pyqtSignal()
    login_cancel_requested = pyqtSignal()
    close_requested = pyqtSignal()  # 창 닫기 시 cleanup 요청

    def __init__(
        self,
        show_test_buttons: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._monitoring = False
        self._monitoring_interval: int = 0
        self._region_cards: dict[str, RegionCard] = {}
        self._show_test_buttons = show_test_buttons

        self.setWindowTitle("ProgressEye")

        # ── Window icon ──
        import sys
        from pathlib import Path

        if getattr(sys, "frozen", False) or "__compiled__" in globals():
            _icon_base = Path(sys.executable).parent
        else:
            _icon_base = Path(__file__).resolve().parent.parent
        _icon_candidates = [
            _icon_base / "resources" / "app-icon.ico",
            _icon_base / "resources" / "app-icon.png",
        ]
        for _icon_path in _icon_candidates:
            if _icon_path.exists():
                self.setWindowIcon(QIcon(str(_icon_path)))
                break
        self._app_min_size = (600, 625)
        self._app_default_size = (630, 875)
        self._login_min_size = (380, 616)
        self._login_default_size = (390, 650)
        self.setMinimumSize(600, 625)
        self.resize(630, 875)

        self._setup_ui()
        self._login_panel.login_requested.connect(self.login_start_requested)
        self._login_panel.cancel_requested.connect(self.login_cancel_requested)

        # ── Settings panel (page-style, added to root layout in _setup_ui) ──
        self._settings_overlay = SettingsOverlay(
            self.centralWidget(),
            show_debug_buttons=self._show_test_buttons,
        )
        self._root_layout.addWidget(self._settings_overlay, stretch=1)
        self._settings_overlay.hide()
        self._settings_overlay.saved.connect(self.settings_saved)
        self._settings_overlay.saved.connect(lambda *_: self.set_settings_mode(False))
        self._settings_overlay.closed.connect(lambda: self.set_settings_mode(False))
        self._settings_overlay.logout_requested.connect(self.settings_logout_requested)
        self._settings_overlay.logout_requested.connect(lambda: self.set_settings_mode(False))
        self._settings_overlay.reset_settings_requested.connect(self.settings_reset_requested)
        self._settings_overlay.delete_account_requested.connect(
            self.settings_delete_account_requested
        )
        self._settings_overlay.delete_account_requested.connect(lambda: self.set_settings_mode(False))
        self._settings_overlay.withdrawal_expired_test_requested.connect(
            self.settings_withdrawal_expired_test_requested
        )
        self._settings_overlay.withdrawal_expired_test_requested.connect(lambda: self.set_settings_mode(False))
        self._settings_overlay.rejoin_expired_test_requested.connect(
            self.settings_rejoin_expired_test_requested
        )
        self._settings_overlay.rejoin_expired_test_requested.connect(lambda: self.set_settings_mode(False))
        self._settings_overlay.privacy_policy_requested.connect(
            self.settings_privacy_policy_requested
        )
        self._settings_overlay.third_party_licenses_requested.connect(
            self.settings_third_party_licenses_requested
        )
        self._settings_overlay.bar_guide_requested.connect(
            self.settings_bar_guide_requested
        )
        self._settings_overlay.bar_guide_requested.connect(lambda: self.set_settings_mode(False))
        self._settings_overlay.welcome_next_requested.connect(self._on_welcome_next)
        self._settings_overlay.welcome_next_requested.connect(self.welcome_next_requested)

        # ── Tutorial page (step 1) ──
        self._tutorial_page = TutorialPage(self.centralWidget())
        self._root_layout.addWidget(self._tutorial_page, stretch=1)
        self._tutorial_page.next_requested.connect(self.tutorial_next_requested)

        # ── Welcome page (step 2) ──
        self._welcome_page = WelcomePage(self.centralWidget())
        self._root_layout.addWidget(self._welcome_page, stretch=1)
        self._welcome_page.started.connect(self.settings_saved)
        self._welcome_page.started.connect(lambda *_: self.set_welcome_mode(False))

    def _setup_ui(self) -> None:
        """UI를 구성한다."""
        central = QWidget()
        central.setStyleSheet(f"background: {APP_BG};")
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)
        self._root_layout = layout

        self._login_panel = LoginStartDialog(central)
        self._app_container = QWidget(central)
        app_layout = QVBoxLayout(self._app_container)
        app_layout.setSpacing(12)
        app_layout.setContentsMargins(0, 0, 0, 0)

        # ── Header ──
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        title = QLabel("ProgressEye")
        title.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {TITLE_TEXT}; background: transparent;")
        header_row.addWidget(title)
        header_row.addStretch()

        self._btn_settings = QPushButton("⚙")
        self._btn_settings.setFixedSize(32, 32)
        self._btn_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_settings.setStyleSheet(
            f"QPushButton {{"
            f"  background: transparent;"
            f"  border: 1px solid {CARD_BORDER};"
            f"  border-radius: 6px;"
            f"  color: {SUBTITLE_TEXT};"
            f"  font-size: 16px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background: {CARD_BG};"
            f"  color: {TITLE_TEXT};"
            f"  border-color: {CHECKBOX_BLUE};"
            f"}}"
        )
        self._btn_settings.clicked.connect(lambda: self.settings_requested.emit())
        self._btn_settings.setToolTip(t("tooltip_settings"))
        header_row.addWidget(self._btn_settings)
        app_layout.addLayout(header_row)

        self._subtitle = QLabel(t("progress_monitoring"))
        self._subtitle.setStyleSheet(
            f"color: {SUBTITLE_TEXT}; font-size: 13px;"
            f"margin-bottom: 4px; background: transparent;"
        )
        app_layout.addWidget(self._subtitle)

        # ── Status + HW stats row ──
        status_row = QHBoxLayout()
        status_row.setContentsMargins(0, 0, 0, 0)
        status_row.setSpacing(12)
        self._status_label = QLabel(t("status_standby"))
        self._status_label.setStyleSheet(
            f"color: {STATUS_GRAY}; font-size: 13px;"
            f"font-weight: bold; background: transparent;"
        )
        status_row.addWidget(self._status_label)
        status_row.addStretch()
        self._hw_label = QLabel("")
        self._hw_label.setStyleSheet(
            f"color: {SUBTITLE_TEXT}; font-size: 11px; background: transparent;"
        )
        status_row.addWidget(self._hw_label)
        app_layout.addLayout(status_row)

        # ── Scroll area for region cards ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(
            f"QScrollArea {{"
            f"  background: transparent;"
            f"  border: none;"
            f"}}"
            f"QScrollBar:vertical {{"
            f"  background: {SCROLLBAR_BG};"
            f"  width: 8px;"
            f"  border-radius: 4px;"
            f"  margin: 0;"
            f"}}"
            f"QScrollBar::handle:vertical {{"
            f"  background: {SCROLLBAR_HANDLE};"
            f"  min-height: 30px;"
            f"  border-radius: 4px;"
            f"}}"
            f"QScrollBar::add-line:vertical,"
            f"QScrollBar::sub-line:vertical {{"
            f"  height: 0px;"
            f"}}"
            f"QScrollBar::add-page:vertical,"
            f"QScrollBar::sub-page:vertical {{"
            f"  background: none;"
            f"}}"
        )

        self._region_container = QWidget()
        self._region_container.setStyleSheet("background: transparent;")
        self._region_layout = QVBoxLayout(self._region_container)
        self._region_layout.setSpacing(8)
        self._region_layout.setContentsMargins(0, 0, 0, 0)

        # ── Empty state label ──
        self._empty_label = QLabel(t("empty_state"))
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet(
            f"color: {EMPTY_TEXT}; padding: 40px;"
            f"font-size: 13px; background: transparent;"
        )
        self._region_layout.addWidget(self._empty_label)

        self._region_layout.addStretch()
        scroll.setWidget(self._region_container)
        app_layout.addWidget(scroll, stretch=1)

        # ── Bottom button bar ──
        btn_layout = QHBoxLayout()

        _btn_add_style = (
            f"QPushButton {{"
            f"  background: {BTN_ADD_BG};"
            f"  border: 1px solid {BTN_ADD_BORDER};"
            f"  border-radius: 8px;"
            f"  color: {BTN_ADD_TEXT};"
            f"  font-size: 12px;"
            f"  padding: 0 12px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background: {CARD_BORDER};"
            f"}}"
        )

        self._btn_add_bar = QPushButton(t("btn_add_bar"))
        self._btn_add_bar.setFixedHeight(36)
        self._btn_add_bar.setStyleSheet(_btn_add_style)
        self._btn_add_bar.clicked.connect(self.select_area_requested.emit)
        self._btn_add_bar.setToolTip(t("tooltip_add_bar"))
        btn_layout.addWidget(self._btn_add_bar)

        self._btn_add_ocr = QPushButton(t("btn_add_ocr"))
        self._btn_add_ocr.setFixedHeight(36)
        self._btn_add_ocr.setStyleSheet(_btn_add_style)
        self._btn_add_ocr.clicked.connect(self.select_ocr_area_requested.emit)
        self._btn_add_ocr.setToolTip(t("tooltip_add_ocr"))
        btn_layout.addWidget(self._btn_add_ocr)

        self._btn_toggle = QPushButton(t("btn_start"))
        self._btn_toggle.setFixedHeight(36)
        self._btn_toggle.setStyleSheet(
            f"QPushButton {{"
            f"  background-color: {BTN_START_BG};"
            f"  color: {BTN_ACTION_TEXT};"
            f"  border: none;"
            f"  border-radius: 8px;"
            f"  font-weight: bold;"
            f"  font-size: 12px;"
            f"  padding: 0 20px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background-color: #2563eb;"
            f"}}"
        )
        self._btn_toggle.clicked.connect(self.toggle_monitoring_requested.emit)
        self._btn_toggle.setToolTip(t("tooltip_start"))
        btn_layout.addWidget(self._btn_toggle)


        app_layout.addLayout(btn_layout)

        layout.addWidget(self._login_panel, stretch=1)
        layout.addWidget(self._app_container, stretch=1)
        self._login_panel.hide()

    def set_login_mode(self, enabled: bool, error: str = "") -> None:
        """로그인 시작 화면 표시 여부를 전환한다."""
        if enabled:
            self._root_layout.setSpacing(0)
            self._root_layout.setContentsMargins(0, 0, 0, 0)
            self.setMinimumSize(*self._login_min_size)
            self.resize(*self._login_default_size)
            self._login_panel.set_error(error)
            self._app_container.hide()
            self._login_panel.show()
            self._login_panel.raise_()
            return

        self._root_layout.setSpacing(12)
        self._root_layout.setContentsMargins(16, 16, 16, 16)
        self.setMinimumSize(*self._app_min_size)
        self.resize(*self._app_default_size)
        self._login_panel.hide()
        self._hide_all_pages()
        self._app_container.show()

    def add_region_display(
        self,
        region_id: str,
        label: str,
        region_type: str = "bar",
        progress_unit: str = "%",
        enabled: bool = True,
        alert_threshold: int = 100,
        alert_delay_minutes: int = 0,
        bar_mode: str = "auto",
        target_color: list | None = None,
    ) -> None:
        """영역 카드를 추가한다."""
        if region_id in self._region_cards:
            return
        self._empty_label.hide()
        card = RegionCard(
            region_id,
            label,
            region_type=region_type,
            progress_unit=progress_unit,
            alert_threshold=alert_threshold,
            alert_delay_minutes=alert_delay_minutes,
            show_test_buttons=self._show_test_buttons,
            bar_mode=bar_mode,
            target_color=target_color,
        )
        card.set_checked(enabled)
        card.toggled.connect(self.region_toggled)
        card.delete_requested.connect(self.region_delete_requested)
        card.view_requested.connect(self.region_view_requested)
        card.edit_requested.connect(self.region_edit_requested)
        card.threshold_changed.connect(self.region_threshold_changed)
        card.delay_changed.connect(self.region_delay_changed)
        card.test_stall_requested.connect(self.test_stall_requested)
        card.test_complete_requested.connect(self.test_complete_requested)
        self._region_cards[region_id] = card
        # addStretch 앞에 삽입
        self._region_layout.insertWidget(self._region_layout.count() - 1, card)
        if self._monitoring:
            card.set_buttons_visible(False)
        log.info("영역 카드 추가: %s (%s)", region_id, label)

    def remove_region_display(self, region_id: str) -> None:
        """영역 카드를 제거한다."""
        card = self._region_cards.pop(region_id, None)
        if card is None:
            return
        self._region_layout.removeWidget(card)
        card.deleteLater()
        if not self._region_cards:
            self._empty_label.show()
        log.info("영역 카드 제거: %s", region_id)

    def update_progress(
        self,
        region_id: str,
        progress: float,
        label: str = "",
        progress_unit: str | None = None,
    ) -> None:
        """영역의 진행률을 업데이트한다."""
        if region_id not in self._region_cards:
            self.add_region_display(region_id, label or region_id)

        card = self._region_cards[region_id]
        if progress_unit is not None:
            card.set_progress_unit(progress_unit)
        card.update_progress(progress)
        if label:
            card.set_label(label)

    def set_region_warning(self, region_id: str, message: str) -> None:
        """영역 카드에 경고 상태를 표시한다."""
        card = self._region_cards.get(region_id)
        if card is not None:
            card.set_warning(message)

    def set_region_enabled(self, region_id: str, enabled: bool) -> None:
        """영역 카드의 체크박스 상태를 변경한다."""
        card = self._region_cards.get(region_id)
        if card is not None:
            card.set_checked(enabled)

    def set_region_task_status(self, region_id: str, status: str) -> None:
        """모니터링 중 카드의 작업 상태를 설정한다 (running/completed/stopped)."""
        card = self._region_cards.get(region_id)
        if card is not None:
            card.set_task_status(status)

    def set_monitoring_state(self, active: bool, interval: int = 0) -> None:
        """모니터링 상태 UI를 변경한다."""
        self._monitoring = active
        self._monitoring_interval = interval
        if active:
            self._subtitle.setText(
                t("progress_monitoring_interval").format(interval=interval)
                if interval > 0
                else t("progress_monitoring")
            )
            self._status_label.setText(t("status_monitoring"))
            self._status_label.setStyleSheet(
                f"color: {STATUS_GREEN}; font-size: 13px;"
                f"font-weight: bold; background: transparent;"
            )
            self._btn_toggle.setText(t("btn_stop"))
            self._btn_toggle.setToolTip(t("tooltip_stop"))
            self._btn_toggle.setStyleSheet(
                f"QPushButton {{"
                f"  background-color: {BTN_STOP_BG};"
                f"  color: {BTN_ACTION_TEXT};"
                f"  border: none;"
                f"  border-radius: 8px;"
                f"  font-weight: bold;"
                f"  font-size: 12px;"
                f"  padding: 0 20px;"
                f"}}"
                f"QPushButton:hover {{"
                f"  background-color: #dc2626;"
                f"}}"
            )
        else:
            self._subtitle.setText(t("progress_monitoring"))
            self._status_label.setText(t("status_standby"))
            self._status_label.setStyleSheet(
                f"color: {STATUS_GRAY}; font-size: 13px;"
                f"font-weight: bold; background: transparent;"
            )
            self._btn_toggle.setText(t("btn_start"))
            self._btn_toggle.setToolTip(t("tooltip_start"))
            self._btn_toggle.setStyleSheet(
                f"QPushButton {{"
                f"  background-color: {BTN_START_BG};"
                f"  color: {BTN_ACTION_TEXT};"
                f"  border: none;"
                f"  border-radius: 8px;"
                f"  font-weight: bold;"
                f"  font-size: 12px;"
                f"  padding: 0 20px;"
                f"}}"
                f"QPushButton:hover {{"
                f"  background-color: #2563eb;"
                f"}}"
            )

        # 모니터링 중에는 추가 버튼과 카드 버튼 숨기기
        self._btn_add_bar.setVisible(not active)
        self._btn_add_ocr.setVisible(not active)
        for card in self._region_cards.values():
            card.set_buttons_visible(not active)
            if active:
                card.set_task_status("running")

        # 모니터링 중에는 설정 버튼 숨기기, 설정창이 열려있으면 닫기
        self._btn_settings.setVisible(not active)
        if active and self._settings_overlay.isVisible():
            self._settings_overlay.hide()

    def update_hw_stats(self, stats: dict) -> None:
        """CPU/GPU/RAM 사용량 표시를 갱신한다."""
        parts = []
        if "cpu" in stats:
            parts.append(f"CPU {stats['cpu']:.0f}%")
        if "gpu" in stats:
            parts.append(f"GPU {stats['gpu']:.0f}%")
        if "ram" in stats:
            parts.append(f"RAM {stats['ram']:.0f}%")
        self._hw_label.setText("  ·  ".join(parts))

    def refresh_texts(self) -> None:
        """언어 변경 시 UI 텍스트를 갱신한다."""
        if self._monitoring and self._monitoring_interval > 0:
            self._subtitle.setText(
                t("progress_monitoring_interval").format(
                    interval=self._monitoring_interval
                )
            )
        else:
            self._subtitle.setText(t("progress_monitoring"))
        self._empty_label.setText(t("empty_state"))
        self._btn_add_bar.setText(t("btn_add_bar"))
        self._btn_add_ocr.setText(t("btn_add_ocr"))
        if self._monitoring:
            self._status_label.setText(t("status_monitoring"))
            self._btn_toggle.setText(t("btn_stop"))
        else:
            self._status_label.setText(t("status_standby"))
            self._btn_toggle.setText(t("btn_start"))
        for card in self._region_cards.values():
            card.refresh_texts()
        self._login_panel.refresh_texts()
        self._settings_overlay._refresh_dialog_texts()
        self._tutorial_page.refresh_texts()
        self._btn_settings.setToolTip(t("tooltip_settings"))
        self._btn_add_bar.setToolTip(t("tooltip_add_bar"))
        self._btn_add_ocr.setToolTip(t("tooltip_add_ocr"))
        if self._monitoring:
            self._btn_toggle.setToolTip(t("tooltip_stop"))
        else:
            self._btn_toggle.setToolTip(t("tooltip_start"))

    def _hide_all_pages(self) -> None:
        """모든 페이지를 숨긴다."""
        self._settings_overlay.hide()
        self._tutorial_page.hide()
        self._welcome_page.hide()
        self._app_container.hide()

    def set_settings_mode(self, enabled: bool) -> None:
        """설정 페이지와 메인 화면을 전환한다."""
        if enabled:
            self._hide_all_pages()
            self._settings_overlay.show()
            self._settings_overlay.raise_()
        else:
            self._hide_all_pages()
            self._app_container.show()

    def set_tutorial_mode(self, enabled: bool) -> None:
        """Tutorial 페이지를 전환한다."""
        if enabled:
            self._hide_all_pages()
            self._tutorial_page.show()
            self._tutorial_page.raise_()
        else:
            self._hide_all_pages()
            self._app_container.show()

    def set_welcome_mode(self, enabled: bool) -> None:
        """Welcome step 2 페이지를 전환한다."""
        if enabled:
            self._hide_all_pages()
            self._welcome_page.show()
            self._welcome_page.raise_()
        else:
            self._hide_all_pages()
            self._app_container.show()

    def _on_welcome_next(self, language: str) -> None:
        """Welcome step 0 완료 → tutorial 페이지 표시."""
        self._settings_overlay.hide()
        self._tutorial_page.refresh_texts()
        self.set_tutorial_mode(True)

    def show_welcome_page(self, interval: int, freeze_minutes: int, language: str) -> None:
        """Welcome step 2 페이지를 표시한다."""
        self._welcome_page.show_welcome(interval=interval, freeze_minutes=freeze_minutes, language=language)
        self.set_welcome_mode(True)

    def show_settings(
        self,
        interval: int,
        language: str,
        email: str,
        freeze_minutes: int = 5,
        welcome_mode: bool = False,
        app_version: str = "",
    ) -> None:
        """설정 페이지를 표시한다."""
        self._settings_overlay.show_settings(
            interval,
            language,
            email,
            freeze_minutes,
            welcome_mode,
            app_version,
        )
        self.set_settings_mode(True)

    def resizeEvent(self, a0) -> None:  # noqa: N802
        super().resizeEvent(a0)

    def closeEvent(self, a0: QCloseEvent | None) -> None:  # noqa: N802
        """닫기 버튼을 누르면 cleanup 시그널을 발생시킨다."""
        if a0 is None:
            return
        if getattr(self, "_really_quit", False):
            a0.accept()
            return
        a0.ignore()
        self.close_requested.emit()
