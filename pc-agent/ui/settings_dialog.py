"""설정 오버레이 패널.

MainWindow 내부 반투명 배경 + 중앙 카드 형태의 설정 UI를 제공한다.
웰컴 모드에서는 2단계 가이드(언어 선택 → 절전 안내 + 설정)를 표시한다.
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QMouseEvent
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from utils.i18n import set_language, t

# ── Color Palette ──
APP_BG = "#0f0f1a"
CARD_BG = "#1c1c30"
CARD_BORDER = "#2a2a45"
TITLE_TEXT = "#ffffff"
SUBTITLE_TEXT = "#8888aa"
CHECKBOX_BLUE = "#3b82f6"

# ── 언어 ──
LANGUAGES = [
    ("ko", "한국어"),
    ("en", "English"),
]


class SettingsOverlay(QWidget):
    """MainWindow 내부 오버레이 설정 패널."""

    saved = pyqtSignal(int, str, int)  # (interval, language, freeze_min)
    logout_requested = pyqtSignal()
    delete_account_requested = pyqtSignal()
    withdrawal_expired_test_requested = pyqtSignal()
    rejoin_expired_test_requested = pyqtSignal()
    privacy_policy_requested = pyqtSignal()
    third_party_licenses_requested = pyqtSignal()
    bar_guide_requested = pyqtSignal()
    closed = pyqtSignal()  # 취소/배경클릭

    def __init__(self, parent: QWidget, show_debug_buttons: bool = False) -> None:
        super().__init__(parent)
        self._show_debug_buttons = show_debug_buttons
        self._welcome_mode = False
        self._welcome_step = 0  # 0=언어 선택, 1=절전안내+설정
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background: rgba(0, 0, 0, 150);")
        self.hide()
        self._setup_ui()

    def _setup_ui(self) -> None:
        """UI를 구성한다."""
        # ── 중앙 배치용 외부 레이아웃 ──
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addStretch()

        card_row = QHBoxLayout()
        card_row.addStretch()

        # ── 카드 위젯 ──
        self._card = QWidget()
        self._card.setFixedWidth(360)
        self._card.setStyleSheet(
            f"background: {APP_BG};border: 1px solid {CARD_BORDER};border-radius: 16px;"
        )

        layout = QVBoxLayout(self._card)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # ── 공통 스타일 ──
        label_style = f"color: {SUBTITLE_TEXT}; font-size: 12px; background: transparent; border: none;"
        input_style = (
            f"QSpinBox, QComboBox {{"
            f"  background: {CARD_BG};"
            f"  border: 1px solid {CARD_BORDER};"
            f"  border-radius: 6px;"
            f"  padding: 6px 10px;"
            f"  color: {TITLE_TEXT};"
            f"  font-size: 13px;"
            f"}}"
            f"QSpinBox:focus, QComboBox:focus {{"
            f"  border-color: {CHECKBOX_BLUE};"
            f"}}"
            f"QSpinBox::up-button {{ width: 24px; }}"
            f"QSpinBox::down-button {{ width: 24px; }}"
            f"QComboBox::drop-down {{"
            f"  border: none;"
            f"  width: 24px;"
            f"}}"
            f"QComboBox QAbstractItemView {{"
            f"  background: {CARD_BG};"
            f"  border: 1px solid {CARD_BORDER};"
            f"  color: {TITLE_TEXT};"
            f"  selection-background-color: {CHECKBOX_BLUE};"
            f"}}"
        )
        hint_style = (
            f"color: {SUBTITLE_TEXT}; font-size: 11px;"
            f" background: transparent; border: none;"
        )
        btn_style_cancel = (
            f"QPushButton {{"
            f"  background: {CARD_BG};"
            f"  border: 1px solid {CARD_BORDER};"
            f"  border-radius: 6px;"
            f"  padding: 8px 20px;"
            f"  color: {SUBTITLE_TEXT};"
            f"  font-size: 13px;"
            f"}}"
            f"QPushButton:hover {{ background: {CARD_BORDER}; }}"
        )
        btn_style_save = (
            f"QPushButton {{"
            f"  background: {CHECKBOX_BLUE};"
            f"  border: none;"
            f"  border-radius: 6px;"
            f"  padding: 8px 20px;"
            f"  color: #ffffff;"
            f"  font-size: 13px;"
            f"  font-weight: bold;"
            f"}}"
            f"QPushButton:hover {{ background: #2563eb; }}"
        )
        btn_style_logout = (
            "QPushButton {"
            "  background: transparent;"
            "  border: 1px solid #ef4444;"
            "  color: #ef4444;"
            "  border-radius: 6px;"
            "  padding: 6px 16px;"
            "  font-size: 12px;"
            "}"
            "QPushButton:hover {"
            "  background: #ef4444;"
            "  color: #ffffff;"
            "}"
        )
        btn_style_withdraw = (
            "QPushButton {"
            "  background: transparent;"
            "  border: 1px solid #f59e0b;"
            "  color: #f59e0b;"
            "  border-radius: 6px;"
            "  padding: 6px 16px;"
            "  font-size: 12px;"
            "}"
            "QPushButton:hover {"
            "  background: #f59e0b;"
            "  color: #ffffff;"
            "}"
        )
        section_style = "background: transparent; border: none;"

        # ══════════════════════════════════════════
        # ── 타이틀 ──
        # ══════════════════════════════════════════
        self._title_label = QLabel(t("settings_title"))
        self._title_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self._title_label.setStyleSheet(
            f"color: {TITLE_TEXT}; background: transparent; border: none;"
        )
        layout.addWidget(self._title_label)

        # ── 웰컴 서브타이틀 ──
        self._welcome_subtitle = QLabel(t("welcome_subtitle"))
        self._welcome_subtitle.setStyleSheet(
            f"color: {SUBTITLE_TEXT}; font-size: 12px; background: transparent; border: none;"
        )
        self._welcome_subtitle.hide()
        layout.addWidget(self._welcome_subtitle)

        # ══════════════════════════════════════════
        # ── 언어 섹션 ──
        # ══════════════════════════════════════════
        self._lang_section = QWidget()
        self._lang_section.setStyleSheet(section_style)
        ls = QVBoxLayout(self._lang_section)
        ls.setContentsMargins(0, 0, 0, 0)
        ls.setSpacing(8)
        self._lang_label = QLabel(t("settings_language"))
        self._lang_label.setStyleSheet(label_style)
        ls.addWidget(self._lang_label)
        self._lang_combo = QComboBox()
        self._lang_combo.setStyleSheet(input_style)
        self._lang_combo.setFixedHeight(36)
        for code, name in LANGUAGES:
            self._lang_combo.addItem(name, code)
        ls.addWidget(self._lang_combo)
        layout.addWidget(self._lang_section)

        # ── "다음" 버튼 (welcome step 0 전용) ──
        self._next_section = QWidget()
        self._next_section.setStyleSheet(section_style)
        ns = QHBoxLayout(self._next_section)
        ns.setContentsMargins(0, 8, 0, 0)
        ns.addStretch()
        self._btn_next = QPushButton(t("btn_next"))
        self._btn_next.setStyleSheet(btn_style_save)
        self._btn_next.clicked.connect(self._on_next_clicked)
        ns.addWidget(self._btn_next)
        self._next_section.hide()
        layout.addWidget(self._next_section)

        # ══════════════════════════════════════════
        # ── 절전 방지 안내 (welcome step 1 전용) ──
        # ══════════════════════════════════════════
        self._sleep_info = QFrame()
        self._sleep_info.setStyleSheet(
            "QFrame {"
            "  background: #1a2332;"
            "  border: 1px solid #2a3a55;"
            "  border-radius: 10px;"
            "  padding: 14px;"
            "}"
        )
        si = QVBoxLayout(self._sleep_info)
        si.setSpacing(6)
        si.setContentsMargins(0, 0, 0, 0)
        self._sleep_title = QLabel(t("sleep_prevention_title"))
        self._sleep_title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self._sleep_title.setStyleSheet(
            "color: #22d3ee; background: transparent; border: none;"
        )
        si.addWidget(self._sleep_title)
        self._sleep_text = QLabel(t("sleep_prevention_info"))
        self._sleep_text.setWordWrap(True)
        self._sleep_text.setStyleSheet(
            f"color: {SUBTITLE_TEXT}; font-size: 11px;"
            f" background: transparent; border: none;"
        )
        si.addWidget(self._sleep_text)
        self._sleep_info.hide()
        layout.addWidget(self._sleep_info)

        # ══════════════════════════════════════════
        # ── 계정 섹션 ──
        # ══════════════════════════════════════════
        self._account_section = QWidget()
        self._account_section.setStyleSheet(section_style)
        acc = QVBoxLayout(self._account_section)
        acc.setContentsMargins(0, 0, 0, 0)
        acc.setSpacing(8)
        account_line = QFrame()
        account_line.setFrameShape(QFrame.Shape.HLine)
        account_line.setStyleSheet(f"color: {CARD_BORDER};")
        acc.addWidget(account_line)
        self._account_label = QLabel(t("settings_account"))
        self._account_label.setStyleSheet(label_style)
        acc.addWidget(self._account_label)
        self._app_version_label = QLabel()
        self._app_version_label.setStyleSheet(
            f"color: {SUBTITLE_TEXT}; font-size: 11px; background: transparent; border: none;"
        )
        acc.addWidget(self._app_version_label)
        self._btn_licenses = QPushButton(t("btn_third_party_licenses"))
        self._btn_licenses.setStyleSheet(btn_style_cancel)
        self._btn_licenses.setToolTip(t("tooltip_third_party_licenses"))
        self._btn_licenses.clicked.connect(self._on_third_party_licenses_clicked)
        acc.addWidget(self._btn_licenses)
        self._btn_privacy = QPushButton(t("btn_privacy_policy"))
        self._btn_privacy.setStyleSheet(btn_style_cancel)
        self._btn_privacy.setToolTip(t("tooltip_privacy_policy"))
        self._btn_privacy.clicked.connect(self._on_privacy_policy_clicked)
        acc.addWidget(self._btn_privacy)
        self._btn_bar_guide = QPushButton(t("btn_show_bar_guide"))
        self._btn_bar_guide.setStyleSheet(btn_style_cancel)
        self._btn_bar_guide.setToolTip(t("tooltip_show_bar_guide"))
        self._btn_bar_guide.clicked.connect(self._on_bar_guide_clicked)
        acc.addWidget(self._btn_bar_guide)
        account_row = QHBoxLayout()
        self._email_label = QLabel("")
        self._email_label.setStyleSheet(
            f"color: {TITLE_TEXT}; font-size: 13px; background: transparent; border: none;"
        )
        account_row.addWidget(self._email_label)
        account_row.addStretch()
        self._btn_logout = QPushButton(t("btn_logout"))
        self._btn_logout.setStyleSheet(btn_style_logout)
        self._btn_logout.setToolTip(t("tooltip_logout"))
        self._btn_logout.clicked.connect(self._on_logout_clicked)
        account_row.addWidget(self._btn_logout)
        self._btn_delete_account = QPushButton(t("btn_delete_account"))
        self._btn_delete_account.setStyleSheet(btn_style_withdraw)
        self._btn_delete_account.setToolTip(t("tooltip_delete_account"))
        self._btn_delete_account.clicked.connect(self._on_delete_account_clicked)
        account_row.addWidget(self._btn_delete_account)
        self._btn_test_withdrawal_expired = QPushButton(
            t("btn_test_withdrawal_expired")
        )
        self._btn_test_withdrawal_expired.setStyleSheet(btn_style_withdraw)
        self._btn_test_withdrawal_expired.setToolTip(
            t("tooltip_test_withdrawal_expired")
        )
        self._btn_test_withdrawal_expired.clicked.connect(
            self._on_test_withdrawal_expired_clicked
        )
        self._btn_test_withdrawal_expired.setVisible(self._show_debug_buttons)
        account_row.addWidget(self._btn_test_withdrawal_expired)
        self._btn_test_rejoin_expired = QPushButton(t("btn_test_rejoin_expired"))
        self._btn_test_rejoin_expired.setStyleSheet(btn_style_withdraw)
        self._btn_test_rejoin_expired.setToolTip(t("tooltip_test_rejoin_expired"))
        self._btn_test_rejoin_expired.clicked.connect(
            self._on_test_rejoin_expired_clicked
        )
        self._btn_test_rejoin_expired.setVisible(self._show_debug_buttons)
        account_row.addWidget(self._btn_test_rejoin_expired)
        acc.addLayout(account_row)
        layout.addWidget(self._account_section)

        # ══════════════════════════════════════════
        # ── 모니터링 간격 섹션 ──
        # ══════════════════════════════════════════
        self._interval_section = QWidget()
        self._interval_section.setStyleSheet(section_style)
        inv = QVBoxLayout(self._interval_section)
        inv.setContentsMargins(0, 0, 0, 0)
        inv.setSpacing(8)
        self._interval_label = QLabel(t("settings_interval"))
        self._interval_label.setStyleSheet(label_style)
        inv.addWidget(self._interval_label)
        self._interval_spin = QSpinBox()
        self._interval_spin.setRange(1, 600)
        self._interval_spin.setValue(30)
        self._interval_spin.setSuffix(t("settings_interval_suffix"))
        self._interval_spin.setStyleSheet(input_style)
        self._interval_spin.setFixedHeight(36)
        inv.addWidget(self._interval_spin)
        self._interval_hint = QLabel(t("settings_interval_hint"))
        self._interval_hint.setStyleSheet(hint_style)
        inv.addWidget(self._interval_hint)
        layout.addWidget(self._interval_section)

        # ══════════════════════════════════════════
        # ── 프리징 감지 섹션 ──
        # ══════════════════════════════════════════
        self._freeze_section = QWidget()
        self._freeze_section.setStyleSheet(section_style)
        frz = QVBoxLayout(self._freeze_section)
        frz.setContentsMargins(0, 0, 0, 0)
        frz.setSpacing(8)
        self._freeze_label = QLabel(t("settings_freeze_timeout"))
        self._freeze_label.setStyleSheet(label_style)
        frz.addWidget(self._freeze_label)
        self._freeze_spin = QSpinBox()
        self._freeze_spin.setRange(1, 60)
        self._freeze_spin.setValue(5)
        self._freeze_spin.setSuffix(t("settings_freeze_suffix"))
        self._freeze_spin.setStyleSheet(input_style)
        self._freeze_spin.setFixedHeight(36)
        frz.addWidget(self._freeze_spin)
        self._freeze_hint = QLabel(t("settings_freeze_hint"))
        self._freeze_hint.setStyleSheet(hint_style)
        frz.addWidget(self._freeze_hint)
        layout.addWidget(self._freeze_section)

        # ══════════════════════════════════════════
        # ── 버튼 섹션 ──
        # ══════════════════════════════════════════
        self._btn_section = QWidget()
        self._btn_section.setStyleSheet(section_style)
        bs = QHBoxLayout(self._btn_section)
        bs.setContentsMargins(0, 0, 0, 0)
        bs.addStretch()
        self._btn_cancel = QPushButton(t("btn_cancel"))
        self._btn_cancel.setStyleSheet(btn_style_cancel)
        self._btn_cancel.setToolTip(t("tooltip_cancel"))
        self._btn_cancel.clicked.connect(self._on_cancel_clicked)
        bs.addWidget(self._btn_cancel)
        self._btn_save = QPushButton(t("btn_save"))
        self._btn_save.setStyleSheet(btn_style_save)
        self._btn_save.setDefault(True)
        self._btn_save.setToolTip(t("tooltip_save"))
        self._btn_save.clicked.connect(self._on_save_clicked)
        bs.addWidget(self._btn_save)
        layout.addWidget(self._btn_section)

        card_row.addWidget(self._card)
        card_row.addStretch()
        outer.addLayout(card_row)
        outer.addStretch()

    # ── 공개 메서드 ──

    def show_settings(
        self,
        interval: int,
        language: str,
        email: str,
        freeze_minutes: int = 5,
        welcome_mode: bool = False,
        app_version: str = "",
    ) -> None:
        """설정값을 세팅하고 오버레이를 표시한다."""
        self._welcome_mode = welcome_mode
        self._welcome_step = 0 if welcome_mode else -1
        self._interval_spin.setValue(interval)
        self._freeze_spin.setValue(freeze_minutes)
        for i in range(self._lang_combo.count()):
            if self._lang_combo.itemData(i) == language:
                self._lang_combo.setCurrentIndex(i)
                break
        self._email_label.setText(t("settings_logged_in_as").format(email=email))
        version_text = app_version.strip() if app_version else "-"
        self._app_version_label.setText(f"{t('settings_app_version')}: {version_text}")
        self._apply_visibility()
        self.show()
        self.raise_()

    @property
    def interval_seconds(self) -> int:
        """설정된 모니터링 간격 (초)."""
        return self._interval_spin.value()

    @property
    def language(self) -> str:
        """설정된 언어 코드 ('ko' 또는 'en')."""
        return self._lang_combo.currentData()

    @property
    def freeze_minutes(self) -> int:
        """설정된 프리징 감지 시간 (분)."""
        return self._freeze_spin.value()

    # ── 내부: 가시성 제어 ──

    def _apply_visibility(self) -> None:
        """현재 모드/스텝에 따라 위젯 가시성을 설정한다."""
        if self._welcome_mode and self._welcome_step == 0:
            # Welcome step 0: 언어 선택만
            self._title_label.setText(t("settings_title"))
            self._welcome_subtitle.setText(t("welcome_lang_subtitle"))
            self._welcome_subtitle.show()
            self._lang_section.show()
            self._next_section.show()
            self._sleep_info.hide()
            self._account_section.hide()
            self._interval_section.hide()
            self._freeze_section.hide()
            self._btn_section.hide()
        elif self._welcome_mode and self._welcome_step == 1:
            # Welcome step 1: 절전 안내 + 나머지 설정
            self._title_label.setText(t("settings_title"))
            self._welcome_subtitle.setText(t("welcome_subtitle"))
            self._welcome_subtitle.show()
            self._lang_section.hide()
            self._next_section.hide()
            self._sleep_info.show()
            self._account_section.show()
            self._btn_logout.hide()  # welcome에서 로그아웃 숨김
            self._btn_delete_account.hide()  # welcome에서 회원탈퇴 숨김
            self._btn_test_withdrawal_expired.hide()
            self._btn_test_rejoin_expired.hide()
            self._interval_section.show()
            self._freeze_section.show()
            self._btn_section.show()
            self._btn_cancel.hide()
            self._btn_save.setText(t("btn_start_app"))
        else:
            # 일반 설정 모드
            self._title_label.setText(t("settings_title"))
            self._welcome_subtitle.hide()
            self._lang_section.show()
            self._next_section.hide()
            self._sleep_info.hide()
            self._account_section.show()
            self._btn_logout.show()
            self._btn_delete_account.show()
            self._btn_test_withdrawal_expired.setVisible(self._show_debug_buttons)
            self._btn_test_rejoin_expired.setVisible(self._show_debug_buttons)
            self._interval_section.show()
            self._freeze_section.show()
            self._btn_section.show()
            self._btn_cancel.show()
            self._btn_save.setText(t("btn_save"))

    def _refresh_dialog_texts(self) -> None:
        """언어 변경 후 다이얼로그 내부 텍스트를 갱신한다."""
        self._lang_label.setText(t("settings_language"))
        self._account_label.setText(t("settings_account"))
        prefix = t("settings_app_version")
        current = self._app_version_label.text()
        value = current.split(":", 1)[1].strip() if ":" in current else "-"
        self._app_version_label.setText(f"{prefix}: {value}")
        self._btn_logout.setText(t("btn_logout"))
        self._btn_logout.setToolTip(t("tooltip_logout"))
        self._btn_delete_account.setText(t("btn_delete_account"))
        self._btn_delete_account.setToolTip(t("tooltip_delete_account"))
        self._btn_test_withdrawal_expired.setText(t("btn_test_withdrawal_expired"))
        self._btn_test_withdrawal_expired.setToolTip(
            t("tooltip_test_withdrawal_expired")
        )
        self._btn_test_rejoin_expired.setText(t("btn_test_rejoin_expired"))
        self._btn_test_rejoin_expired.setToolTip(t("tooltip_test_rejoin_expired"))
        self._btn_licenses.setText(t("btn_third_party_licenses"))
        self._btn_licenses.setToolTip(t("tooltip_third_party_licenses"))
        self._btn_privacy.setText(t("btn_privacy_policy"))
        self._btn_privacy.setToolTip(t("tooltip_privacy_policy"))
        self._btn_bar_guide.setText(t("btn_show_bar_guide"))
        self._btn_bar_guide.setToolTip(t("tooltip_show_bar_guide"))
        self._interval_label.setText(t("settings_interval"))
        self._interval_spin.setSuffix(t("settings_interval_suffix"))
        self._interval_hint.setText(t("settings_interval_hint"))
        self._freeze_label.setText(t("settings_freeze_timeout"))
        self._freeze_spin.setSuffix(t("settings_freeze_suffix"))
        self._freeze_hint.setText(t("settings_freeze_hint"))
        self._btn_cancel.setText(t("btn_cancel"))
        self._btn_cancel.setToolTip(t("tooltip_cancel"))
        self._btn_save.setToolTip(t("tooltip_save"))
        self._sleep_title.setText(t("sleep_prevention_title"))
        self._sleep_text.setText(t("sleep_prevention_info"))

    # ── 내부 핸들러 ──

    def _on_next_clicked(self) -> None:
        """웰컴 step 0 → step 1: 언어 적용 후 다음 단계로 전환."""
        # 선택한 언어 즉시 적용
        new_lang = self.language
        set_language(new_lang)
        # 부모(MainWindow) 텍스트 갱신
        parent = self.parent()
        if parent is not None:
            refresh = getattr(parent, "refresh_texts", None)
            if callable(refresh):
                refresh()
        # 다이얼로그 자체 텍스트 갱신
        self._refresh_dialog_texts()
        self._welcome_step = 1
        self._apply_visibility()

    def _on_save_clicked(self) -> None:
        self.saved.emit(
            self.interval_seconds,
            self.language,
            self.freeze_minutes,
        )
        self.hide()

    def _on_cancel_clicked(self) -> None:
        self.closed.emit()
        self.hide()

    def _on_logout_clicked(self) -> None:
        self.hide()
        self.logout_requested.emit()

    def _on_delete_account_clicked(self) -> None:
        self.hide()
        self.delete_account_requested.emit()

    def _on_test_withdrawal_expired_clicked(self) -> None:
        self.withdrawal_expired_test_requested.emit()
        self.hide()

    def _on_test_rejoin_expired_clicked(self) -> None:
        self.rejoin_expired_test_requested.emit()
        self.hide()

    def _on_third_party_licenses_clicked(self) -> None:
        self.third_party_licenses_requested.emit()

    def _on_privacy_policy_clicked(self) -> None:
        self.privacy_policy_requested.emit()

    def _on_bar_guide_clicked(self) -> None:
        self.bar_guide_requested.emit()
        self.hide()

    def mousePressEvent(self, a0: QMouseEvent | None) -> None:  # noqa: N802
        """배경(카드 바깥) 클릭 시 닫기. 웰컴 모드에서는 무시."""
        if a0 is None:
            return
        if self._welcome_mode:
            return
        if not self._card.geometry().contains(a0.pos()):
            self.closed.emit()
            self.hide()
