from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules, copy_metadata


PROJECT_ROOT = Path(__file__).resolve().parents[2]

hiddenimports = []
hiddenimports += collect_submodules("google_auth_oauthlib")
hiddenimports += collect_submodules("google.oauth2")
hiddenimports += collect_submodules("google.auth")

datas = []
datas += copy_metadata("google-auth")
datas += copy_metadata("google-auth-oauthlib")


a = Analysis(
    [str(PROJECT_ROOT / "main.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "pytest",
        "unittest",
        "test",
        "tests",
    ],
    noarchive=False,
    optimize=0,
)

# ── Remove unused large binaries ──
EXCLUDE_BINARIES = {
    'opencv_videoio_ffmpeg',    # FFmpeg video I/O (27 MB)
    'libscipy_openblas',        # OpenBLAS BLAS (19 MB)
    '_multiarray_tests',        # numpy test module
    'Qt6Pdf',                   # Qt PDF module (5 MB)
    'qt6pdf',
}
a.binaries = [b for b in a.binaries if not any(ex in b[0] for ex in EXCLUDE_BINARIES)]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ProgressEye",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    [d for d in a.datas if 'osd.traineddata' not in d[0]],  # exclude Tesseract OSD (10 MB)
    strip=False,
    upx=False,
    upx_exclude=[],
    name="ProgressEye",
)
