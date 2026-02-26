"""시스템 하드웨어 모니터링 모듈 (CPU/GPU/RAM 사용량).

psutil      — CPU/RAM 사용량 (no admin, 모든 플랫폼)
nvidia-ml-py — NVIDIA GPU 사용량 (no admin, 드라이버만 필요)
Windows PDH  — AMD/Intel GPU 사용량 fallback (no admin, PowerShell 내장)

측정 방식:
  백그라운드 데몬 스레드에서 ~2초 간격으로 CPU/GPU/RAM을 샘플링한다.
  CPU/GPU는 최근 5개 샘플의 이동평균을, RAM은 최신값을 반환한다.
  collect_stats()는 캐시된 값만 읽으므로 호출 시점의 spike가 반영되지 않는다.
"""

from __future__ import annotations

import subprocess
import threading
from collections import deque

from utils.logger import log  # pyright: ignore[reportImplicitRelativeImport]

_SAMPLE_SIZE = 5

# ── 샘플 저장소 (모듈 레벨 싱글턴) ──
_cpu_samples: deque[float] = deque(maxlen=_SAMPLE_SIZE)
_gpu_samples: deque[float] = deque(maxlen=_SAMPLE_SIZE)
_ram_value: float | None = None
_lock = threading.Lock()
_thread: threading.Thread | None = None
_stop = threading.Event()


# ═════════════════════════════════════════════════════════
# Background sampler thread
# ═════════════════════════════════════════════════════════

def _sampler_loop() -> None:
    """백그라운드에서 CPU/GPU/RAM을 ~2초 주기로 샘플링한다."""
    global _ram_value

    # ── psutil 초기화 ──
    try:
        import psutil
        has_psutil = True
        psutil.cpu_percent(interval=None)  # 워밍업 (첫 호출 0.0 방지)
    except ImportError:
        has_psutil = False

    # ── NVIDIA GPU 핸들 (앱 수명동안 유지) ──
    nvidia_handle = None
    try:
        from pynvml import nvmlInit, nvmlDeviceGetCount, nvmlDeviceGetHandleByIndex
        nvmlInit()
        if nvmlDeviceGetCount() > 0:
            nvidia_handle = nvmlDeviceGetHandleByIndex(0)
            log.debug("NVIDIA GPU 핸들 획득")
    except Exception:
        pass

    while not _stop.is_set():
        # ── CPU (1초 차단 측정 — 정확) ──
        if has_psutil:
            try:
                cpu = psutil.cpu_percent(interval=1)
                with _lock:
                    _cpu_samples.append(cpu)
            except Exception:
                pass
        else:
            _stop.wait(timeout=1)

        if _stop.is_set():
            break

        # ── GPU ──
        gpu_val: float | None = None
        if nvidia_handle is not None:
            try:
                from pynvml import nvmlDeviceGetUtilizationRates
                util = nvmlDeviceGetUtilizationRates(nvidia_handle)
                gpu_val = float(util.gpu)
            except Exception:
                pass
        if gpu_val is None:
            gpu_val = _get_pdh_gpu_usage()

        # ── RAM ──
        ram_val: float | None = None
        if has_psutil:
            try:
                ram_val = psutil.virtual_memory().percent
            except Exception:
                pass

        with _lock:
            if gpu_val is not None:
                _gpu_samples.append(gpu_val)
            _ram_value = ram_val

        # CPU interval=1이 1초를 소비했으므로 추가 1초 대기 → ~2초 주기
        _stop.wait(timeout=1)

    # ── NVIDIA 정리 ──
    if nvidia_handle is not None:
        try:
            from pynvml import nvmlShutdown
            nvmlShutdown()
        except Exception:
            pass


# ═════════════════════════════════════════════════════════
# Public API
# ═════════════════════════════════════════════════════════

def start_sampler() -> None:
    """하드웨어 샘플러 데몬 스레드를 시작한다 (앱 시작 시 1회 호출)."""
    global _thread
    if _thread is not None and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_sampler_loop, daemon=True, name="hw-sampler")
    _thread.start()
    log.debug("하드웨어 샘플러 스레드 시작")


def stop_sampler() -> None:
    """하드웨어 샘플러 스레드를 정지한다 (앱 종료 시 호출, 선택적)."""
    global _thread
    _stop.set()
    if _thread is not None:
        _thread.join(timeout=3)
        _thread = None


def collect_stats() -> dict[str, object]:
    """CPU/GPU/RAM 사용량을 수집하여 RTDB 전송용 dict를 반환한다.

    Returns:
        {"cpu": float, "gpu": float, "ram": float}
        사용 불가한 항목은 포함하지 않는다.
    """
    stats: dict[str, object] = {}

    with _lock:
        # CPU 이동평균
        if _cpu_samples:
            stats["cpu"] = round(sum(_cpu_samples) / len(_cpu_samples), 1)

        # GPU 이동평균
        if _gpu_samples:
            stats["gpu"] = round(sum(_gpu_samples) / len(_gpu_samples), 1)

        # RAM 최신값
        if _ram_value is not None:
            stats["ram"] = round(_ram_value, 1)

    return stats


def _get_pdh_gpu_usage() -> float | None:
    """Windows PDH 카운터로 GPU 사용량을 수집한다 (AMD/Intel/NVIDIA 공통).

    PowerShell 내장 기능만 사용하므로 추가 설치 불필요.
    약 200ms 소요되나 샘플링 주기(~2초) 대비 허용 가능.
    """
    try:
        cmd = (
            'Get-Counter "\\GPU Engine(*engtype_3D)\\Utilization Percentage" '
            "-ErrorAction SilentlyContinue | "
            "Select-Object -ExpandProperty CounterSamples | "
            "Measure-Object -Property CookedValue -Sum | "
            "Select-Object -ExpandProperty Sum"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW,  # type: ignore[attr-defined]
        )
        val = result.stdout.strip()
        if val:
            return round(float(val), 1)
    except Exception:
        pass
    return None


def warmup_cpu_percent() -> None:
    """하드웨어 샘플러를 시작한다.

    기존 호출부(main.py _init_firebase)와의 호환성을 위해 함수명 유지.
    """
    start_sampler()
