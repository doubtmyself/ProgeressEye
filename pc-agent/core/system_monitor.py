"""시스템 하드웨어 모니터링 모듈 (CPU/GPU 사용량).

psutil      — CPU 사용량 (no admin, 모든 플랫폼)
nvidia-ml-py — NVIDIA GPU 사용량 (no admin, 드라이버만 필요)
Windows PDH  — AMD/Intel GPU 사용량 fallback (no admin, PowerShell 내장)
"""

from __future__ import annotations

import subprocess

from utils.logger import log  # pyright: ignore[reportImplicitRelativeImport]


def collect_stats() -> dict[str, object]:
    """CPU/GPU 사용량을 수집하여 RTDB 전송용 dict를 반환한다.

    Returns:
        {"cpu": float, "gpu": float}
        사용 불가한 항목은 포함하지 않는다.
    """
    stats: dict[str, object] = {}

    # ── CPU 사용량 (psutil) ──
    try:
        import psutil

        cpu = psutil.cpu_percent(interval=None)
        stats["cpu"] = round(cpu, 1)
    except Exception:
        pass

    # ── GPU 사용량: NVIDIA 우선, 실패 시 PDH fallback ──
    gpu = _get_nvidia_gpu_usage()
    if gpu is None:
        gpu = _get_pdh_gpu_usage()
    if gpu is not None:
        stats["gpu"] = gpu

    return stats


def _get_nvidia_gpu_usage() -> int | None:
    """NVIDIA GPU 사용량을 nvidia-ml-py로 수집한다 (빠름, 정확)."""
    try:
        from pynvml import (  # nvidia-ml-py 패키지
            NVMLError,
            nvmlDeviceGetCount,
            nvmlDeviceGetHandleByIndex,
            nvmlDeviceGetUtilizationRates,
            nvmlInit,
            nvmlShutdown,
        )

        nvmlInit()
        try:
            if nvmlDeviceGetCount() > 0:
                handle = nvmlDeviceGetHandleByIndex(0)
                util = nvmlDeviceGetUtilizationRates(handle)
                return util.gpu  # type: ignore[no-any-return]
        except NVMLError:
            pass
        finally:
            nvmlShutdown()
    except Exception:
        pass
    return None


def _get_pdh_gpu_usage() -> float | None:
    """Windows PDH 카운터로 GPU 사용량을 수집한다 (AMD/Intel/NVIDIA 공통).

    PowerShell 내장 기능만 사용하므로 추가 설치 불필요.
    약 200ms 소요되나 모니터링 주기(1~30초) 대비 허용 가능.
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
    """psutil.cpu_percent() 워밍업.

    첫 호출은 이전 측정값이 없어 0.0을 반환하므로
    앱 시작 시 1회 호출하여 기준점을 설정한다.
    """
    try:
        import psutil

        psutil.cpu_percent(interval=None)
    except Exception:
        log.debug("psutil 워밍업 실패 (설치되지 않았을 수 있음)")
