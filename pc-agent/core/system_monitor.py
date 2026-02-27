"""시스템 하드웨어 모니터링 모듈 (CPU/GPU/RAM 사용량).

플랫폼별 CPU 측정:
  Windows  — PDH '% Processor Utility' (주파수 보정, 작업관리자와 일치)
           → GetSystemTimes fallback (in-process, 시간 기반)
           → psutil.cpu_percent fallback
  기타     — psutil.cpu_percent(interval=None) (in-process 저오버헤드)

공통:
  psutil      — RAM 사용량 (모든 플랫폼)
  nvidia-ml-py — NVIDIA GPU 사용량 (no admin, 드라이버만 필요)
  Windows PDH  — AMD/Intel GPU 사용량 fallback

측정 방식:
  백그라운드 데몬 스레드에서 5초 간격으로 CPU/GPU/RAM을 샘플링한다.
  CPU/GPU는 최근 5개 샘플의 이동평균(~25초)을, RAM은 최신값을 반환한다.
  collect_stats()는 캐시된 값만 읽으므로 호출 시점의 spike가 반영되지 않는다.
"""

from __future__ import annotations

import ctypes
import subprocess
import sys
import threading
from collections import deque

from utils.logger import log  # pyright: ignore[reportImplicitRelativeImport]

_SAMPLE_SIZE = 5
_IS_WINDOWS = sys.platform == "win32"
_CPU_WARMUP_SKIP_SAMPLES = 2
_CPU_MIN_REPORT_SAMPLES = _SAMPLE_SIZE

# ── 샘플 저장소 (모듈 레벨 싱글턴) ──
_cpu_samples: deque[float] = deque(maxlen=_SAMPLE_SIZE)
_gpu_samples: deque[float] = deque(maxlen=_SAMPLE_SIZE)
_ram_value: float | None = None
_windows_cpu_prev: tuple[int, int] | None = None  # (idle, total)
_lock = threading.Lock()
_thread: threading.Thread | None = None
_stop = threading.Event()

# ═════════════════════════════════════════════════════════
# Background sampler thread
# ═════════════════════════════════════════════════════════


def _sampler_loop() -> None:
    """백그라운드에서 CPU/GPU/RAM을 5초 주기로 샘플링한다."""
    global _ram_value

    # ── psutil 초기화 (RAM + CPU) ──
    has_psutil = False
    psutil_mod = None
    process_handle = None
    try:
        import psutil as psutil_mod

        has_psutil = True
        psutil_mod.cpu_percent(interval=None)  # 워밍업 (첫 샘플 기준점 설정)
        try:
            process_handle = psutil_mod.Process()
            process_handle.cpu_percent(interval=None)
        except Exception:
            process_handle = None
    except ImportError:
        pass

    # ── NVIDIA GPU 핸들 (앱 수명동안 유지) ──
    nvidia_handle = None
    cpu_sample_count = 0
    try:
        from pynvml import nvmlInit, nvmlDeviceGetCount, nvmlDeviceGetHandleByIndex

        nvmlInit()
        if nvmlDeviceGetCount() > 0:
            nvidia_handle = nvmlDeviceGetHandleByIndex(0)
            log.debug("NVIDIA GPU 핸들 획득")
    except Exception:
        pass

    while not _stop.is_set():
        # 5초 대기 (첫 반복 포함)
        _stop.wait(timeout=5)
        if _stop.is_set():
            break

        # ── CPU (Windows: PDH Utility 우선 → GetSystemTimes → psutil) ──
        cpu_val: float | None = None
        if _IS_WINDOWS:
            cpu_val = _get_pdh_cpu_usage()  # 주파수 보정, 작업관리자와 일치
        if cpu_val is None and _IS_WINDOWS:
            cpu_val = _get_windows_cpu_busy()  # in-process fallback
        if cpu_val is None and has_psutil and psutil_mod is not None:
            try:
                cpu_val = psutil_mod.cpu_percent(interval=None)
            except Exception:
                pass

        if cpu_val is not None:
            cpu_sample_count += 1
            if cpu_sample_count <= _CPU_WARMUP_SKIP_SAMPLES:
                log.debug(
                    "[hw-sampler] CPU warmup sample skipped: %.1f%% (%d/%d)",
                    cpu_val,
                    cpu_sample_count,
                    _CPU_WARMUP_SKIP_SAMPLES,
                )
            else:
                with _lock:
                    _cpu_samples.append(cpu_val)

        # ── GPU ──
        gpu_val: float | None = None
        if _IS_WINDOWS:
            # Windows는 작업 관리자(PDH) 기준을 우선 사용
            gpu_val = _get_pdh_gpu_usage()

        if gpu_val is None and nvidia_handle is not None:
            try:
                from pynvml import nvmlDeviceGetUtilizationRates

                util = nvmlDeviceGetUtilizationRates(nvidia_handle)
                gpu_val = float(util.gpu)
            except Exception:
                pass

        # ── RAM (psutil, 모든 플랫폼) ──
        ram_val: float | None = None
        app_cpu_val: float | None = None
        if has_psutil and psutil_mod is not None:
            try:
                ram_val = psutil_mod.virtual_memory().percent
            except Exception:
                pass
            if process_handle is not None:
                try:
                    app_cpu_val = process_handle.cpu_percent(interval=None)
                except Exception:
                    app_cpu_val = None

        with _lock:
            if gpu_val is not None:
                _gpu_samples.append(gpu_val)
            _ram_value = ram_val

        log.debug(
            "[hw-sampler] CPU=%s%%  GPU=%s%%  RAM=%s%%  APPCPU=%s%%",
            "%.1f" % cpu_val
            if cpu_val is not None and len(_cpu_samples) >= _CPU_MIN_REPORT_SAMPLES
            else "N/A",
            "%.1f" % gpu_val if gpu_val is not None else "N/A",
            "%.1f" % ram_val if ram_val is not None else "N/A",
            "%.1f" % app_cpu_val if app_cpu_val is not None else "N/A",
        )

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
        if len(_cpu_samples) >= _CPU_MIN_REPORT_SAMPLES:
            stats["cpu"] = round(sum(_cpu_samples) / len(_cpu_samples), 1)

        # GPU 이동평균
        if _gpu_samples:
            stats["gpu"] = round(sum(_gpu_samples) / len(_gpu_samples), 1)

        # RAM 최신값
        if _ram_value is not None:
            stats["ram"] = round(_ram_value, 1)

    return stats


def _get_pdh_cpu_usage() -> float | None:
    """Windows CPU 사용량을 수집한다.

    우선순위:
    1) PDH `% Processor Utility` — 주파수 보정(터보부스트 반영), 작업관리자와 일치
    2) PDH `% Idle Time` 기반 busy 계산 (시간 기반 fallback)
    3) PDH `% Processor Time` (호환 fallback)
    4) Win32_Processor.LoadPercentage (최후 fallback, 정수/coarse)

    샘플링 주기(5초) 대비 호출 비용은 허용 가능하다.
    """
    # 1) % Processor Utility — 작업관리자와 동일한 주파수 보정 카운터
    utility = _read_windows_counter(
        "\\Processor Information(_Total)\\% Processor Utility"
    )
    if utility is not None:
        return utility

    # 2) % Idle Time 기반 (시간 기반, 주파수 미보정)
    idle = _read_windows_counter("\\Processor Information(_Total)\\% Idle Time")
    if idle is None:
        idle = _read_windows_counter("\\Processor(_Total)\\% Idle Time")
    if idle is not None:
        return round(max(0.0, 100.0 - idle), 1)

    # 3) % Processor Time (시간 기반)
    processor_time = _read_windows_counter("\\Processor(_Total)\\% Processor Time")
    if processor_time is not None:
        return processor_time

    # 4) WMI 최후 fallback
    try:
        cmd = (
            "Get-CimInstance Win32_Processor | "
            "Measure-Object -Property LoadPercentage -Average | "
            "Select-Object -ExpandProperty Average"
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
            return min(round(float(val), 1), 100.0)
    except Exception:
        pass
    return None


def _read_windows_counter(counter_path: str) -> float | None:
    """PowerShell Get-Counter 값을 float로 읽는다."""
    try:
        cmd = (
            f'Get-Counter "{counter_path}" '
            "-ErrorAction SilentlyContinue | "
            "Select-Object -ExpandProperty CounterSamples | "
            "Select-Object -ExpandProperty CookedValue"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW,  # type: ignore[attr-defined]
        )
        text = result.stdout.strip()
        if not text:
            return None

        # locale에 따라 소수점이 ',' 로 내려오는 경우를 흡수한다.
        normalized = text.replace(",", ".")
        return min(round(float(normalized), 1), 100.0)
    except Exception:
        return None


def _get_pdh_gpu_usage() -> float | None:
    """Windows PDH 카운터로 GPU 사용량을 수집한다 (AMD/Intel/NVIDIA 공통).

    PowerShell 내장 기능만 사용하므로 추가 설치 불필요.
    엔진별 합계(sum)는 100%를 초과할 수 있으므로 최대값(max)으로 집계한다.
    약 200ms 소요되나 샘플링 주기(5초) 대비 허용 가능.
    """
    try:
        cmd = (
            'Get-Counter "\\GPU Engine(*engtype_3D)\\Utilization Percentage" '
            "-ErrorAction SilentlyContinue | "
            "Select-Object -ExpandProperty CounterSamples | "
            "Measure-Object -Property CookedValue -Maximum | "
            "Select-Object -ExpandProperty Maximum"
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
            return min(round(float(val), 1), 100.0)
    except Exception:
        pass
    return None


def _get_windows_cpu_busy() -> float | None:
    """GetSystemTimes 기반 Windows CPU busy(%)를 계산한다.

    - 매우 저오버헤드(in-process)
    - 첫 호출은 기준점만 설정하고 None 반환
    """

    if not _IS_WINDOWS:
        return None

    class _FILETIME(ctypes.Structure):
        _fields_ = [
            ("dwLowDateTime", ctypes.c_uint32),
            ("dwHighDateTime", ctypes.c_uint32),
        ]

    def _filetime_to_int(ft: object) -> int:
        hi = int(getattr(ft, "dwHighDateTime", 0))
        lo = int(getattr(ft, "dwLowDateTime", 0))
        return (hi << 32) | lo

    global _windows_cpu_prev

    try:
        idle = _FILETIME()
        kernel = _FILETIME()
        user = _FILETIME()
        ok = ctypes.windll.kernel32.GetSystemTimes(
            ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)
        )
        if ok == 0:
            return None

        idle_now = _filetime_to_int(idle)
        total_now = _filetime_to_int(kernel) + _filetime_to_int(user)

        if _windows_cpu_prev is None:
            _windows_cpu_prev = (idle_now, total_now)
            return None

        idle_prev, total_prev = _windows_cpu_prev
        _windows_cpu_prev = (idle_now, total_now)

        idle_delta = idle_now - idle_prev
        total_delta = total_now - total_prev
        if total_delta <= 0:
            return None

        busy = 100.0 * (1.0 - (idle_delta / total_delta))
        return max(0.0, min(round(busy, 1), 100.0))
    except Exception:
        return None


def warmup_cpu_percent() -> None:
    """하드웨어 샘플러를 시작한다.

    기존 호출부(main.py _init_firebase)와의 호환성을 위해 함수명 유지.
    """
    start_sampler()
