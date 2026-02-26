"""시스템 하드웨어 모니터링 모듈 (CPU/GPU 사용량·온도).

psutil  — CPU 사용량 (no admin)
nvidia-ml-py — NVIDIA GPU 사용량·온도 (no admin, 드라이버만 필요)

CPU 온도는 Windows에서 관리자 권한 없이 안정적으로 수집할 수 없어 제외.
"""

from __future__ import annotations

from utils.logger import log  # pyright: ignore[reportImplicitRelativeImport]


def collect_stats() -> dict[str, object]:
    """CPU/GPU 사용량·온도를 수집하여 RTDB 전송용 dict를 반환한다.

    Returns:
        {"cpu": float, "gpu": int, "gpuTemp": int, "gpuName": str}
        사용 불가한 항목은 포함하지 않는다.
    """
    stats: dict[str, object] = {}

    # ── CPU 사용량 ──
    try:
        import psutil

        cpu = psutil.cpu_percent(interval=None)
        stats["cpu"] = round(cpu, 1)
    except Exception:
        pass

    # ── GPU 사용량 + 온도 (NVIDIA only) ──
    try:
        from pynvml import (  # nvidia-ml-py 패키지
            NVML_TEMPERATURE_GPU,
            NVMLError,
            nvmlDeviceGetCount,
            nvmlDeviceGetHandleByIndex,
            nvmlDeviceGetName,
            nvmlDeviceGetTemperature,
            nvmlDeviceGetUtilizationRates,
            nvmlInit,
            nvmlShutdown,
        )

        nvmlInit()
        try:
            if nvmlDeviceGetCount() > 0:
                handle = nvmlDeviceGetHandleByIndex(0)
                util = nvmlDeviceGetUtilizationRates(handle)
                temp = nvmlDeviceGetTemperature(handle, NVML_TEMPERATURE_GPU)
                name = nvmlDeviceGetName(handle)
                if isinstance(name, bytes):
                    name = name.decode("utf-8")
                stats["gpu"] = util.gpu
                stats["gpuTemp"] = temp
                stats["gpuName"] = name
        except NVMLError:
            pass
        finally:
            nvmlShutdown()
    except Exception:
        pass

    return stats


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
