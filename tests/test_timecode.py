# -*- coding: utf-8 -*-
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import timecode as mod  # noqa: E402


def test_roundtrip():
    tc = timecode.parse_tc("00:01:00;02", 29.97)
    n = timecode.to_frames(tc, 29.97)
    back = timecode.from_frames(n, 29.97)
    assert timecode.format_tc(back, 29.97) == "00:01:00;02"


def test_drop_frame_skips_two():
    n = timecode.to_frames(timecode.parse_tc("00:01:00;00", 29.97), 29.97)
    assert n > 0


# ===== v2 契约测试：初始全部失败，实现后必须通过 =====
import timecode  # noqa: E402


def test_concat_continuity():
    segs = [{"fps": 25, "frames": 100}, {"fps": 30, "frames": 60}, {"fps": 24, "frames": 48}]
    r = timecode.concat_segments(segs)
    assert r["total_frames"] == 208
    assert r["starts"] == [0, 100, 160]
    assert r["boundaries"] == [100, 160]


def test_roundtrip_at_boundaries_mixed_rates():
    for fps in (24, 25, 30):
        for f in (0, 1, fps - 1, fps, 3600):
            tc = timecode.tc_from_frames(f, fps)
            assert timecode.frames_from_tc(tc, fps) == f


def test_roundtrip_drop_frame():
    for f in (0, 1, 1799, 1800, 17982):
        tc = timecode.tc_from_frames(f, 29.97)
        assert timecode.frames_from_tc(tc, 29.97) == f


def test_concat_midnight_monotonic():
    segs = [{"fps": 25, "frames": 100000}, {"fps": 25, "frames": 100000}]
    r = timecode.concat_segments(segs)
    assert r["total_frames"] == 200000
    assert all(b > a for a, b in zip(r["starts"], r["starts"][1:]))


def test_align_reports_offset():
    r = timecode.align_to_reference("00:00:10:00", 25, 10.2, tol_frames=8)
    assert abs(r["offset_frames"]) <= 8
    assert r["error_frames"] <= 8
    assert r["frames"] == 250
