"""HTML-based startup login panel for PC app (self-contained CSS)."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QVBoxLayout, QWidget
from PyQt6.QtWebEngineCore import QWebEnginePage
from PyQt6.QtWebEngineWidgets import QWebEngineView

from utils.i18n import t  # pyright: ignore[reportImplicitRelativeImport]


class _LoginPage(QWebEnginePage):
    def __init__(self, host: "LoginStartDialog") -> None:
        super().__init__(host)
        self._host = host

    def acceptNavigationRequest(
        self,
        url: QUrl,
        nav_type: object,
        is_main_frame: bool,
    ) -> bool:
        scheme = url.scheme().lower()
        if scheme == "app":
            action = url.host().lower()
            if action == "login":
                self._host.login_requested.emit()
            elif action == "cancel":
                self._host.cancel_requested.emit()
            return False
        if scheme in {"http", "https"}:
            QDesktopServices.openUrl(url)
            return False
        return super().acceptNavigationRequest(url, nav_type, is_main_frame)


class LoginStartDialog(QWidget):
    """In-window login panel shown before opening OAuth browser."""

    login_requested = pyqtSignal()
    cancel_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view = QWebEngineView(self)
        self._page = _LoginPage(self)
        self._view.setPage(self._page)
        self._view.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._view)

        self._load_html(error_message="")

    def set_error(self, message: str) -> None:
        self._load_html(error_message=message)

    def _load_html(self, error_message: str) -> None:
        esc = (
            (
                error_message.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
            )
            if error_message
            else ""
        )
        error_html = f"<div class='error'>{esc}</div>" if esc else ""

        google_label = t("login_start_google")
        quit_label = t("login_start_cancel")
        subtitle = t("login_start_subtitle").replace("\n", "<br/>")

        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>ProgressEye Welcome Screen</title>
  <style>
    * {{ box-sizing: border-box; }}
    html, body {{
      margin: 0;
      width: 100%;
      height: 100%;
      overflow: hidden;
      font-family: "Segoe UI", "Noto Sans KR", sans-serif;
      color: #f8fafc;
      background: #101622;
    }}
    .root {{
      width: 100%;
      height: 100%;
      display: flex;
      flex-direction: column;
      background: radial-gradient(circle at 50% 0%, #1c2738 0%, #101622 100%);
      position: relative;
    }}
    .main {{
      flex: 1;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 26px;
      padding: 22px;
    }}
    .hero {{ display: flex; flex-direction: column; align-items: center; gap: 14px; }}
    .hero-wrap {{
      width: 160px;
      height: 160px;
      position: relative;
      display: flex;
      align-items: center;
      justify-content: center;
    }}
    .hero-wrap::before {{
      content: "";
      position: absolute;
      inset: 0;
      border-radius: 999px;
      background: rgba(37, 106, 244, 0.18);
      filter: blur(26px);
    }}
    .hero-circle {{
      width: 128px;
      height: 128px;
      border-radius: 999px;
      border: 1px solid rgba(37, 106, 244, 0.18);
      background: #151b28;
      box-shadow: 0 18px 34px rgba(0,0,0,0.35);
      position: relative;
      z-index: 1;
      display: flex;
      align-items: center;
      justify-content: center;
    }}
    .eye {{ width: 64px; height: 64px; color: #256af4; }}
    .mini-track {{
      position: absolute;
      left: 50%;
      bottom: 24px;
      transform: translateX(-50%);
      width: 64px;
      height: 6px;
      border-radius: 999px;
      background: #334155;
      overflow: hidden;
    }}
    .mini-fill {{ width: 66%; height: 100%; background: #256af4; border-radius: 999px; }}
    .title {{ text-align: center; max-width: 320px; }}
    .title h1 {{
      margin: 0;
      color: #fff;
      font-size: 54px;
      line-height: 1;
      font-weight: 700;
      letter-spacing: -0.5px;
    }}
    .title p {{
      margin: 12px 0 0;
      color: #94a3b8;
      font-size: 18px;
      line-height: 1.42;
    }}

    .card {{
      width: min(100%, 320px);
      aspect-ratio: 4 / 3;
      border-radius: 16px;
      padding: 16px;
      border: 1px solid rgba(255,255,255,0.08);
      background: rgba(21, 27, 40, 0.5);
      box-shadow: 0 20px 30px rgba(0,0,0,0.25);
      display: flex;
      flex-direction: column;
      gap: 16px;
    }}
    .row {{ display: flex; align-items: center; gap: 12px; }}
    .row.dim {{ opacity: .62; }}
    .pill {{
      width: 40px;
      height: 40px;
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: rgba(37,106,244,0.2);
      color: #256af4;
      flex-shrink: 0;
    }}
    .pill svg {{ width: 18px; height: 18px; display: block; }}
    .pill.dim {{ background: rgba(99,102,241,0.2); color: #818cf8; }}
    .meta {{ flex: 1; display: flex; flex-direction: column; gap: 6px; }}
    .meta-head {{ display: flex; justify-content: space-between; font-size: 12px; color: #94a3b8; }}
    .pct {{ color: #256af4; font-weight: 700; }}
    .pct.dim {{ color: #818cf8; }}
    .track {{ width: 100%; height: 6px; border-radius: 999px; background: #334155; overflow: hidden; }}
    .fill78 {{ width: 78%; height: 100%; background: #256af4; border-radius: 999px; }}
    .fill42 {{ width: 42%; height: 100%; background: #6366f1; border-radius: 999px; }}

    .footer {{
      width: min(100%, 320px);
      margin: 0 auto;
      padding: 0 0 16px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }}
    .terms {{ display: flex; align-items: center; gap: 8px; color: #64748b; font-size: 13px; }}
    .terms input {{ width: 18px; height: 18px; accent-color: #256af4; }}
    .terms a {{ color: #94a3b8; text-decoration: underline; }}
    .signin {{
      width: 100%;
      border: 0;
      border-radius: 12px;
      background: #fff;
      color: #111827;
      padding: 15px 16px;
      font-size: 18px;
      font-weight: 700;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 10px;
      cursor: pointer;
    }}
    .signin:disabled {{ background: rgba(255,255,255,0.56); color: rgba(17,24,39,0.45); cursor: not-allowed; }}
    .gicon {{ width: 20px; height: 20px; }}
    .quit {{ border: 0; background: transparent; color: #64748b; font-size: 13px; cursor: pointer; padding: 4px; }}
    .quit:hover {{ color: #cbd5e1; }}
    .error {{ color: #ef4444; text-align: center; font-size: 13px; }}
  </style>
</head>
<body>
  <div class="root">
    <div class="main">
      <div class="hero">
        <div class="hero-wrap">
          <div class="hero-circle">
            <svg class="eye" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M2.5 12C4.7 8.1 8.1 6 12 6C15.9 6 19.3 8.1 21.5 12C19.3 15.9 15.9 18 12 18C8.1 18 4.7 15.9 2.5 12Z" stroke="currentColor" stroke-width="1.7"/>
              <circle cx="12" cy="12" r="3.1" stroke="currentColor" stroke-width="1.7"/>
              <circle cx="12" cy="12" r="1.2" fill="currentColor"/>
            </svg>
            <div class="mini-track"><div class="mini-fill"></div></div>
          </div>
        </div>
        <div class="title">
          <h1>ProgressEye</h1>
          <p>{subtitle}</p>
        </div>
      </div>

      <div class="card">
        <div class="row">
          <div class="pill">
            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
              <path d="M7 8L4 12L7 16" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
              <path d="M17 8L20 12L17 16" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
              <path d="M10 18H14" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
              <rect x="9" y="5" width="6" height="10" rx="1.5" stroke="currentColor" stroke-width="1.6"/>
            </svg>
          </div>
          <div class="meta">
            <div class="meta-head"><span>Rendering Scene 04</span><span class="pct">78%</span></div>
            <div class="track"><div class="fill78"></div></div>
          </div>
        </div>
        <div class="row dim">
          <div class="pill dim">
            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
              <circle cx="12" cy="12" r="6" stroke="currentColor" stroke-width="1.8"/>
              <circle cx="12" cy="12" r="1.6" fill="currentColor"/>
              <path d="M12 6V4M12 20V18M6 12H4M20 12H18" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
            </svg>
          </div>
          <div class="meta">
            <div class="meta-head"><span>Training Epoch 12</span><span class="pct dim">42%</span></div>
            <div class="track"><div class="fill42"></div></div>
          </div>
        </div>
      </div>

      <div class="footer">
        <label class="terms">
          <input id="terms" type="checkbox"/>
          <span>By continuing you agree to our <a href="https://progresseye-49244.web.app">Terms</a></span>
        </label>

        <button id="loginBtn" class="signin" disabled>
          <svg class="gicon" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"></path>
            <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"></path>
            <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.84z" fill="#FBBC05"></path>
            <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"></path>
          </svg>
          <span>{google_label}</span>
        </button>

        <button id="cancelBtn" class="quit">{quit_label}</button>
        {error_html}
      </div>
    </div>
  </div>

  <script>
    const terms = document.getElementById('terms');
    const loginBtn = document.getElementById('loginBtn');
    terms.addEventListener('change', () => {{ loginBtn.disabled = !terms.checked; }});
    loginBtn.addEventListener('click', () => {{ window.location.href = 'app://login'; }});
    document.getElementById('cancelBtn').addEventListener('click', () => {{ window.location.href = 'app://cancel'; }});
    document.addEventListener('keydown', (e) => {{ if (e.key === 'Escape') window.location.href = 'app://cancel'; }});
  </script>
</body>
</html>
"""
        self._view.setHtml(html, QUrl("file:///C:/ProgressEye/pc-agent/"))
