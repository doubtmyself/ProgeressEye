"""메인 윈도우 모듈.

모니터링 상태, 등록된 영역의 진행률을 표시하고
영역 추가, 모니터링 시작/정지 기능을 제공한다.
"""

from datetime import datetime

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCloseEvent, QFont, QMouseEvent
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
)

from utils.logger import log

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

    def __init__(
        self,
        region_id: str,
        label: str,
        region_type: str = "bar",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.region_id = region_id
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


        type_text = "진행률 숫자" if region_type == "ocr" else "진행률 바"
        # ── Row 1: 작업 이름 라벨 (큰 글씨, 볼드) ──
        self._label = QLabel(label)
        self._label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self._label.setStyleSheet(
            f"color: {CARD_LABEL}; background: transparent; border: none;"
        )
        layout.addWidget(self._label)

        # ── Row 2: 체크박스 + 타입 라벨 (작은 글씨) ──
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
        header_row.addWidget(self._checkbox)
        self._type_label = QLabel(type_text)
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

        # ── Progress bar (percentage shown ON bar, no separate label) ──
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 1000)
        self._progress_bar.setValue(0)
        self._progress_bar.setFixedHeight(24)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setFormat("0.0%")
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

        # ── Bottom row: timestamp ──
        self._time_label = QLabel("대기 중")
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

        self._btn_edit = QPushButton("✏ 작업 수정")
        self._btn_edit.setFixedHeight(24)
        self._btn_edit.setStyleSheet(btn_style)
        self._btn_edit.clicked.connect(
            lambda: self.edit_requested.emit(self.region_id)
        )
        btn_row.addWidget(self._btn_edit)

        self._btn_view = QPushButton("👁 영역보기")
        self._btn_view.setFixedHeight(24)
        self._btn_view.setStyleSheet(btn_style)
        self._btn_view.clicked.connect(
            lambda: self.view_requested.emit(self.region_id)
        )
        btn_row.addWidget(self._btn_view)

        self._btn_delete = QPushButton("🗑 삭제")
        self._btn_delete.setFixedHeight(24)
        self._btn_delete.setStyleSheet(btn_style)
        self._btn_delete.clicked.connect(
            lambda: self.delete_requested.emit(self.region_id)
        )
        btn_row.addWidget(self._btn_delete)

        btn_row.insertStretch(0)
        layout.addLayout(btn_row)



    def _on_check_changed(self, state: int) -> None:
        """체크박스 상태 변경 시 시그널을 발생시킨다."""
        enabled = state == Qt.CheckState.Checked.value
        self.toggled.emit(self.region_id, enabled)

    def update_progress(self, progress: float) -> None:
        """진행률을 업데이트한다."""
        self._progress_bar.setValue(int(progress * 10))
        self._progress_bar.setFormat(f"{progress:.1f}%")
        self._time_label.setText(f"⏱ 업데이트: {datetime.now().strftime('%H:%M:%S')}")

    def set_label(self, label: str) -> None:
        """라벨을 변경한다."""
        self._label.setText(label)

    def set_checked(self, checked: bool) -> None:
        """체크박스 상태를 설정한다."""
        self._checkbox.setChecked(checked)


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

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._monitoring = False
        self._region_cards: dict[str, RegionCard] = {}

        self.setWindowTitle("ProgressEye")
        self.setMinimumSize(400, 350)
        self.resize(420, 500)

        self._setup_ui()

    def _setup_ui(self) -> None:
        """UI를 구성한다."""
        central = QWidget()
        central.setStyleSheet(f"background: {APP_BG};")
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # ── Header ──
        title = QLabel("ProgressEye")
        title.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {TITLE_TEXT}; background: transparent;")
        layout.addWidget(title)

        subtitle = QLabel("진행률 모니터링")
        subtitle.setStyleSheet(
            f"color: {SUBTITLE_TEXT}; font-size: 13px;"
            f"margin-bottom: 4px; background: transparent;"
        )
        layout.addWidget(subtitle)

        # ── Status indicator ──
        self._status_label = QLabel("● 대기 중")
        self._status_label.setStyleSheet(
            f"color: {STATUS_GRAY}; font-size: 13px;"
            f"font-weight: bold; background: transparent;"
        )
        layout.addWidget(self._status_label)

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
        self._empty_label = QLabel(
            "등록된 모니터링 영역이 없습니다.\n아래 버튼을 눌러 시작하세요."
        )
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet(
            f"color: {EMPTY_TEXT}; padding: 40px;"
            f"font-size: 13px; background: transparent;"
        )
        self._region_layout.addWidget(self._empty_label)

        self._region_layout.addStretch()
        scroll.setWidget(self._region_container)
        layout.addWidget(scroll, stretch=1)

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

        self._btn_add_bar = QPushButton("진행률 바 추가")
        self._btn_add_bar.setFixedHeight(36)
        self._btn_add_bar.setStyleSheet(_btn_add_style)
        self._btn_add_bar.clicked.connect(self.select_area_requested.emit)
        btn_layout.addWidget(self._btn_add_bar)

        self._btn_add_ocr = QPushButton("진행률 숫자 추가")
        self._btn_add_ocr.setFixedHeight(36)
        self._btn_add_ocr.setStyleSheet(_btn_add_style)
        self._btn_add_ocr.clicked.connect(self.select_ocr_area_requested.emit)
        btn_layout.addWidget(self._btn_add_ocr)

        self._btn_toggle = QPushButton("모니터링 시작")
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
        btn_layout.addWidget(self._btn_toggle)

        layout.addLayout(btn_layout)

    def add_region_display(
        self,
        region_id: str,
        label: str,
        region_type: str = "bar",
        enabled: bool = True,
    ) -> None:
        """영역 카드를 추가한다."""
        if region_id in self._region_cards:
            return
        self._empty_label.hide()
        card = RegionCard(region_id, label, region_type=region_type)
        card.set_checked(enabled)
        card.toggled.connect(self.region_toggled)
        card.delete_requested.connect(self.region_delete_requested)
        card.view_requested.connect(self.region_view_requested)
        card.edit_requested.connect(self.region_edit_requested)
        self._region_cards[region_id] = card
        # addStretch 앞에 삽입
        self._region_layout.insertWidget(self._region_layout.count() - 1, card)
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

    def update_progress(self, region_id: str, progress: float, label: str = "") -> None:
        """영역의 진행률을 업데이트한다."""
        if region_id not in self._region_cards:
            self.add_region_display(region_id, label or region_id)

        card = self._region_cards[region_id]
        card.update_progress(progress)
        if label:
            card.set_label(label)

    def set_monitoring_state(self, active: bool) -> None:
        """모니터링 상태 UI를 변경한다."""
        self._monitoring = active
        if active:
            self._status_label.setText("● 모니터링 중")
            self._status_label.setStyleSheet(
                f"color: {STATUS_GREEN}; font-size: 13px;"
                f"font-weight: bold; background: transparent;"
            )
            self._btn_toggle.setText("● 모니터링 정지")
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
            self._status_label.setText("● 대기 중")
            self._status_label.setStyleSheet(
                f"color: {STATUS_GRAY}; font-size: 13px;"
                f"font-weight: bold; background: transparent;"
            )
            self._btn_toggle.setText("모니터링 시작")
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

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """닫기 버튼 → 트레이 최소화. request_quit 호출 시 실제 종료."""
        if getattr(self, "_really_quit", False):
            event.accept()
            log.info("메인 창 종료")
            return
        event.ignore()
        self.hide()
        log.info("메인 창 트레이로 최소화")
