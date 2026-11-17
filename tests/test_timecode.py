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
