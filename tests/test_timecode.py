# -*- coding: utf-8 -*-
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import timecode  # noqa: E402


# ---------- 往返无损 ----------

@pytest.mark.parametrize("tc", [
    "00:00:00;00",
    "00:00:00;29",
    "00:00:01;00",
    "00:00:59;29",
    "00:01:00;02",   # 丢帧后第一个合法帧
    "00:01:00;29",
    "00:09:59;29",
    "00:10:00;00",  # 整十分不丢帧
    "00:10:00;01",
    "01:00:00;00",
    "12:34:56;15",
    "23:59:59;29",  # 一天最后一帧
])
def test_roundtrip_drop_2997(tc):
    n = timecode.to_frames(timecode.parse_tc(tc, 29.97), 29.97)
    back = timecode.from_frames(n, 29.97)
    assert timecode.format_tc(back, 29.97) == tc
    assert timecode.to_frames(back, 29.97) == n


@pytest.mark.parametrize("fps,tc", [
    (23.976, "00:00:00:00"),
    (23.976, "00:01:00:00"),
    (23.976, "12:34:56:23"),
    (23.976, "23:59:59:23"),
    (25, "00:00:00:00"),
    (25, "00:01:00:00"),
    (25, "12:34:56:24"),
    (25, "23:59:59:24"),
])
def test_roundtrip_nondrop(fps, tc):
    n = timecode.to_frames(timecode.parse_tc(tc, fps), fps)
    assert timecode.format_tc(timecode.from_frames(n, fps), fps) == tc


def test_roundtrip_sweep_minute_boundaries():
    # 连续扫过多个整分钟边界，帧号必须严格连续且无偏差
    prev = None
    for n in range(1790, 1800 + 1800 * 3):
        tc = timecode.from_frames(n, 29.97)
        assert timecode.to_frames(tc, 29.97) == n
        if prev is not None:
            assert n == prev + 1
        prev = n


# ---------- 整分钟边界 ----------

def test_minute_boundary_values():
    # 00:01:00;02 是第 1 分钟的第一个合法帧：1800 - 2 = 1798... 验证精确值
    assert timecode.to_frames("00:00:59;29", 29.97) == 1799
    assert timecode.to_frames("00:01:00;02", 29.97) == 1800
    assert timecode.to_frames("00:01:00;03", 29.97) == 1801
    # 整十分不丢帧
    assert timecode.to_frames("00:10:00;00", 29.97) == 17982
    assert timecode.to_frames("00:10:00;01", 29.97) == 17983
    # 反向
    assert timecode.format_tc(1800, 29.97) == "00:01:00;02"
    assert timecode.format_tc(17982, 29.97) == "00:10:00;00"


def test_hour_boundary():
    assert timecode.to_frames("01:00:00;00", 29.97) == 107892
    assert timecode.format_tc(107892, 29.97) == "01:00:00;00"


# ---------- 非法码报错 ----------

def test_invalid_minute_second():
    with pytest.raises(ValueError, match="分钟位"):
        timecode.parse_tc("00:99:00;00", 29.97)
    with pytest.raises(ValueError, match="秒位"):
        timecode.parse_tc("00:00:99;00", 29.97)
    with pytest.raises(ValueError, match="分钟位"):
        timecode.parse_tc("00:99:99;99", 29.97)


def test_invalid_frame_field():
    with pytest.raises(ValueError, match="帧位"):
        timecode.parse_tc("00:00:00;30", 29.97)  # 名义 30，合法帧 0-29
    with pytest.raises(ValueError, match="帧位"):
        timecode.parse_tc("00:00:00:24", 23.976)  # 名义 24，合法帧 0-23
    with pytest.raises(ValueError, match="帧位"):
        timecode.parse_tc("00:00:00:25", 25)


def test_invalid_hour():
    with pytest.raises(ValueError, match="小时位"):
        timecode.parse_tc("24:00:00;00", 29.97)


def test_dropped_frames_do_not_exist():
    # 非整十分的 0 秒第 0、1 帧不存在
    for bad in ("00:01:00;00", "00:01:00;01", "00:02:00;00", "01:59:00;01"):
        with pytest.raises(ValueError, match="丢帧位不存在"):
            timecode.parse_tc(bad, 29.97)
    # 整十分的 0、1 帧存在
    assert timecode.parse_tc("00:10:00;00", 29.97).frames == 0
    assert timecode.parse_tc("00:10:00;01", 29.97).frames == 1


def test_drop_separator_only_for_2997():
    with pytest.raises(ValueError, match="丢帧分隔符"):
        timecode.parse_tc("00:00:00;00", 25)


def test_malformed_format():
    with pytest.raises(ValueError, match="格式错误"):
        timecode.parse_tc("abc", 29.97)
    with pytest.raises(ValueError, match="格式错误"):
        timecode.parse_tc("00:00:00", 29.97)


# ---------- 边界 ----------

def test_day_wraparound():
    frames_in_day = 2589408  # 24h @ 29.97 丢帧
    assert timecode.to_frames("23:59:59;29", 29.97) == frames_in_day - 1
    # 回绕：一天末尾 +1 帧回到 00:00:00;00
    assert timecode.format_tc(frames_in_day, 29.97) == "00:00:00;00"
    # 负帧号不出现：-1 回绕到一天最后一帧
    tc = timecode.from_frames(-1, 29.97)
    assert timecode.format_tc(tc, 29.97) == "23:59:59;29"
    assert timecode.to_frames(tc, 29.97) == frames_in_day - 1


def test_day_wraparound_nondrop():
    assert timecode.format_tc(24 * 3600 * 25, 25) == "00:00:00:00"
    assert timecode.format_tc(-1, 25) == "23:59:59:24"


def test_empty_input_deterministic():
    with pytest.raises(ValueError, match="空输入"):
        timecode.parse_tc("", 29.97)
    with pytest.raises(ValueError, match="空输入"):
        timecode.parse_tc("   ", 29.97)


def test_single_frame_input():
    # 单帧时间码
    assert timecode.to_frames("00:00:00;00", 29.97) == 0
    assert timecode.format_tc(0, 29.97) == "00:00:00;00"
    # 裸帧号输入按总帧数处理
    assert timecode.to_frames(timecode.parse_tc("1800", 29.97), 29.97) == 1800
    assert timecode.format_tc(timecode.parse_tc("0", 29.97), 29.97) == "00:00:00;00"


# ---------- 23.976 / 25 名义帧率 ----------

def test_nominal_rate_conversion():
    # 23.976 按名义 24、25 按名义 25，各自独立换算
    assert timecode.to_frames("00:00:01:00", 23.976) == 24
    assert timecode.to_frames("00:00:01:00", 25) == 25
    assert timecode.to_frames("00:01:00:00", 23.976) == 24 * 60
    assert timecode.to_frames("00:01:00:00", 25) == 25 * 60


# ---------- 两次一致 ----------

def test_deterministic_repeat():
    inputs = ["00:00:00;00", "00:01:00;02", "01:00:00;00", "23:59:59;29"]
    def run():
        out = []
        for tc in inputs:
            n = timecode.to_frames(timecode.parse_tc(tc, 29.97), 29.97)
            out.append((n, timecode.format_tc(timecode.from_frames(n, 29.97), 29.97)))
        return out
    assert run() == run()
