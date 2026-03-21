"""FreezeDetector 단위 테스트."""

import time
import pytest
from unittest.mock import patch

from core.freeze_detector import FreezeDetector, FreezeState


class TestFreezeDetectorInit:
    def test_default_timeout_is_5_minutes(self):
        detector = FreezeDetector()
        assert detector._timeout_seconds == 5 * 60

    def test_custom_timeout(self):
        detector = FreezeDetector(timeout_minutes=10)
        assert detector._timeout_seconds == 10 * 60

    def test_custom_change_threshold(self):
        detector = FreezeDetector(change_threshold=1.0)
        assert detector._change_threshold == 1.0


class TestFreezeDetectorUpdate:
    def setup_method(self):
        self.detector = FreezeDetector(timeout_minutes=1)

    def test_first_update_creates_state(self):
        state = self.detector.update("r1", 50.0)
        assert state.region_id == "r1"
        assert state.last_progress == 50.0
        assert state.is_frozen is False

    def test_progress_change_above_threshold_resets_timer(self):
        self.detector.update("r1", 10.0)
        first_time = self.detector._states["r1"].last_change_time

        with patch("time.time", return_value=first_time + 30):
            state = self.detector.update("r1", 15.0)

        assert state.is_frozen is False
        assert state.last_progress == 15.0

    def test_small_change_below_threshold_does_not_reset(self):
        self.detector.update("r1", 10.0)
        state = self.detector.update("r1", 10.3)  # 0.3 < default threshold 0.5
        assert state.last_progress == 10.0  # not updated

    def test_freeze_detected_after_timeout(self):
        now = time.time()
        with patch("time.time", return_value=now):
            self.detector.update("r1", 50.0)

        with patch("time.time", return_value=now + 61):
            state = self.detector.update("r1", 50.0)

        assert state.is_frozen is True

    def test_not_frozen_before_timeout(self):
        now = time.time()
        with patch("time.time", return_value=now):
            self.detector.update("r1", 50.0)

        with patch("time.time", return_value=now + 30):
            state = self.detector.update("r1", 50.0)

        assert state.is_frozen is False

    def test_freeze_unfreezes_on_progress_change(self):
        now = time.time()
        with patch("time.time", return_value=now):
            self.detector.update("r1", 50.0)

        # freeze
        with patch("time.time", return_value=now + 61):
            self.detector.update("r1", 50.0)

        # unfreeze
        with patch("time.time", return_value=now + 62):
            state = self.detector.update("r1", 60.0)

        assert state.is_frozen is False
        assert state.frozen_minutes == 0

    def test_frozen_minutes_increments(self):
        now = time.time()
        with patch("time.time", return_value=now):
            self.detector.update("r1", 50.0)

        with patch("time.time", return_value=now + 3 * 60):
            state = self.detector.update("r1", 50.0)

        assert state.frozen_minutes == 3


class TestFreezeDetectorReset:
    def setup_method(self):
        self.detector = FreezeDetector()

    def test_reset_removes_region(self):
        self.detector.update("r1", 50.0)
        self.detector.reset("r1")
        assert self.detector.get_state("r1") is None

    def test_reset_nonexistent_region_is_safe(self):
        self.detector.reset("does_not_exist")  # should not raise

    def test_reset_all_clears_all_regions(self):
        self.detector.update("r1", 10.0)
        self.detector.update("r2", 20.0)
        self.detector.reset_all()
        assert self.detector.get_state("r1") is None
        assert self.detector.get_state("r2") is None

    def test_set_timeout_minutes(self):
        self.detector.set_timeout_minutes(15)
        assert self.detector._timeout_seconds == 15 * 60
