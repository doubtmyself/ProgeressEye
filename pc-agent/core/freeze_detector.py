"""진행 멈춤 감지 모듈.

진행률이 일정 시간 동안 변하지 않으면 'freeze' 상태로 전환한다.
"""

import time
from dataclasses import dataclass, field

from utils.logger import log


@dataclass
class FreezeState:
    """특정 작업의 멈춤 감지 상태."""

    region_id: str
    last_progress: float = -1.0
    last_change_time: float = field(default_factory=time.time)
    is_frozen: bool = False
    frozen_minutes: int = 0


class FreezeDetector:
    """진행률 변화를 추적하여 멈춤을 감지한다.

    일정 시간(timeout_minutes) 동안 진행률이 변하지 않으면
    freeze 상태로 판정한다.
    """

    def __init__(self, timeout_minutes: int = 5, change_threshold: float = 0.5) -> None:
        """
        Args:
            timeout_minutes: 멈춤 판정까지의 시간(분).
            change_threshold: 이 값 이상 변해야 '변화'로 인정 (노이즈 무시).
        """
        self._timeout_seconds = timeout_minutes * 60
        self._change_threshold = change_threshold
        self._states: dict[str, FreezeState] = {}

    def set_timeout_minutes(self, minutes: int) -> None:
        """멈춤 판정 시간을 변경한다.

        Args:
            minutes: 마지막 변화 후 이 시간이 지나면 freeze 판정.
        """
        self._timeout_seconds = minutes * 60
        log.debug("프리징 감지 시간 변경: %d분", minutes)

    def update(self, region_id: str, progress: float) -> FreezeState:
        """새 진행률로 상태를 업데이트한다.

        Args:
            region_id: 모니터링 영역 ID.
            progress: 현재 진행률 (0.0~100.0).

        Returns:
            업데이트된 FreezeState.
        """
        now = time.time()

        if region_id not in self._states:
            self._states[region_id] = FreezeState(
                region_id=region_id,
                last_progress=progress,
                last_change_time=now,
            )
            return self._states[region_id]

        state = self._states[region_id]

        # 진행률이 변했는지 확인 (threshold 이상 변화)
        if abs(progress - state.last_progress) >= self._change_threshold:
            state.last_progress = progress
            state.last_change_time = now
            if state.is_frozen:
                state.is_frozen = False
                state.frozen_minutes = 0
                log.info("[%s] 멈춤 해제 — 진행률 변화 감지: %.1f%%", region_id, progress)
            return state

        # 진행률 미변화 — 경과 시간 확인
        elapsed = now - state.last_change_time
        state.frozen_minutes = int(elapsed / 60)

        if elapsed >= self._timeout_seconds and not state.is_frozen:
            state.is_frozen = True
            log.warning(
                "[%s] 멈춤 감지! %.1f%%에서 %d분째 멈춤",
                region_id,
                state.last_progress,
                state.frozen_minutes,
            )

        return state

    def reset(self, region_id: str) -> None:
        """특정 영역의 멈춤 감지 상태를 초기화한다."""
        if region_id in self._states:
            del self._states[region_id]

    def reset_all(self) -> None:
        """모든 영역의 멈춤 감지 상태를 초기화한다."""
        self._states.clear()

    def get_state(self, region_id: str) -> FreezeState | None:
        """특정 영역의 현재 멈춤 상태를 반환한다."""
        return self._states.get(region_id)