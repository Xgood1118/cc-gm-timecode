# -*- coding: utf-8 -*-
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import timecode  # noqa: E402


# ---------- 保留签名 + 基础往返 ----------

def test_roundtrip():
    tc = timecode.parse_tc("00:01:00;02", 29.97)
    n = timecode.to_frames(tc, 29.97)
    back = timecode.from_frames(n, 29.97)
    assert timecode.format_tc(back, 29.97) == "00:01:00;02"


def test_drop_frame_skips_two():
    # 第 1 分钟开始跳过帧号 00、01：合法起点是 ;02，且正好接在 1799 之后
    assert timecode.to_frames(timecode.parse_tc("00:00:59;29", 29.97), 29.97) == 1799
    n = timecode.to_frames(timecode.parse_tc("00:01:00;02", 29.97), 29.97)
    assert n == 1800
    with pytest.raises(ValueError, match="丢帧位不存在"):
        timecode.parse_tc("00:01:00;00", 29.97)
    with pytest.raises(ValueError, match="丢帧位不存在"):
        timecode.parse_tc("00:01:00;01", 29.97)


@pytest.mark.parametrize("tc", [
    "00:00:00;00",
    "00:00:00;29",
    "00:00:01;00",
    "00:00:59;29",
    "00:01:00;02",   # 丢帧后第一个合法帧
    "00:01:00;29",
    "00:09:59;29",
    "00:10:00;00",   # 整十分不丢帧
    "00:10:00;01",
    "01:00:00;00",
    "12:34:56;15",
    "23:59:59;29",   # 一天最后一帧
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
    (24, "00:00:00:00"),
    (25, "00:00:00:00"),
    (25, "00:01:00:00"),
    (25, "12:34:56:24"),
    (25, "23:59:59:24"),
    (30, "00:01:00:00"),
    (30, "23:59:59:29"),
])
def test_roundtrip_nondrop(fps, tc):
    n = timecode.to_frames(timecode.parse_tc(tc, fps), fps)
    assert timecode.format_tc(timecode.from_frames(n, fps), fps) == tc


def test_roundtrip_sweep_minute_boundaries():
    # 连续扫过多个整分钟边界，帧号必须严格连续且往返无偏差
    prev = None
    for n in range(1790, 1800 + 1800 * 3):
        tc = timecode.from_frames(n, 29.97)
        assert timecode.to_frames(tc, 29.97) == n
        if prev is not None:
            assert n == prev + 1
        prev = n


def test_roundtrip_full_ten_minute_cycle():
    # 扫完整个 10 分钟循环（17982 帧），确保跳帧位置全部正确
    for n in list(range(0, 17982, 7)) + [17980, 17981, 17982]:
        assert timecode.frames_from_tc(
            timecode.tc_from_frames(n, 29.97), 29.97
        ) == n


# ---------- 整分钟边界精确值 ----------

def test_minute_boundary_values():
    assert timecode.to_frames("00:00:59;29", 29.97) == 1799
    assert timecode.to_frames("00:01:00;02", 29.97) == 1800
    assert timecode.to_frames("00:01:00;03", 29.97) == 1801
    assert timecode.to_frames("00:10:00;00", 29.97) == 17982
    assert timecode.to_frames("00:10:00;01", 29.97) == 17983
    assert timecode.format_tc(1800, 29.97) == "00:01:00;02"
    assert timecode.format_tc(17982, 29.97) == "00:10:00;00"
    assert timecode.format_tc(107892, 29.97) == "01:00:00;00"


# ---------- 校验：字段越界与丢帧位 ----------

def test_invalid_minute_second():
    with pytest.raises(ValueError, match="分钟位"):
        timecode.parse_tc("00:99:00;00", 29.97)
    with pytest.raises(ValueError, match="秒位"):
        timecode.parse_tc("00:00:99;00", 29.97)
    with pytest.raises(ValueError, match="分钟位"):
        timecode.parse_tc("00:99:99;99", 29.97)


def test_invalid_hour():
    with pytest.raises(ValueError, match="小时位"):
        timecode.parse_tc("24:00:00;00", 29.97)


@pytest.mark.parametrize("fps,bad", [
    (29.97, "00:00:00;30"),
    (23.976, "00:00:00:24"),
    (25, "00:00:00:25"),
    (24, "00:00:00:24"),
])
def test_invalid_frame_field(fps, bad):
    with pytest.raises(ValueError, match="帧位"):
        timecode.parse_tc(bad, fps)


def test_error_points_at_position():
    # 错误信息与异常都指出错在哪一位（1 基字符位置）
    with pytest.raises(timecode.TimecodeError) as info:
        timecode.parse_tc("00:99:99;99", 29.97)
    assert info.value.field == "分钟位"
    assert info.value.position == 4
    assert "第 4 个字符" in str(info.value)

    with pytest.raises(timecode.TimecodeError) as info:
        timecode.parse_tc("00:00:00;30", 29.97)
    assert info.value.field == "帧位"
    assert info.value.position == 10


def test_dropped_frames_do_not_exist():
    for bad in ("00:01:00;00", "00:01:00;01", "00:02:00;00", "01:59:00;01"):
        with pytest.raises(ValueError, match="丢帧位不存在"):
            timecode.parse_tc(bad, 29.97)
    # 整十分的 0、1 帧存在
    assert timecode.parse_tc("00:10:00;00", 29.97).frames == 0
    assert timecode.parse_tc("00:10:00;01", 29.97).frames == 1
    # 第 0 分 0 秒的 00、01 帧属于整十分，合法存在
    assert timecode.to_frames("00:00:00;00", 29.97) == 0
    assert timecode.to_frames("00:00:00;01", 29.97) == 1


def test_drop_separator_only_for_2997():
    with pytest.raises(ValueError, match="分隔符"):
        timecode.parse_tc("00:00:00;00", 25)
    with pytest.raises(ValueError, match="分隔符"):
        timecode.parse_tc("00:00:00;00", 24)


def test_malformed_format():
    with pytest.raises(ValueError, match="格式错误"):
        timecode.parse_tc("abc", 29.97)
    with pytest.raises(ValueError, match="格式错误"):
        timecode.parse_tc("00:00:00", 29.97)


# ---------- 边界：24 小时回绕 / 空输入 / 单帧 ----------

def test_day_wraparound():
    frames_in_day = 2589408  # 24h @ 29.97 丢帧
    assert timecode.to_frames("23:59:59;29", 29.97) == frames_in_day - 1
    assert timecode.format_tc(frames_in_day, 29.97) == "00:00:00;00"
    assert timecode.format_tc(-1, 29.97) == "23:59:59;29"
    assert timecode.to_frames(timecode.from_frames(-1, 29.97), 29.97) == frames_in_day - 1
    assert timecode.format_tc(0, 29.97) == "00:00:00;00"


def test_day_wraparound_nondrop():
    assert timecode.format_tc(24 * 3600 * 25, 25) == "00:00:00:00"
    assert timecode.format_tc(-1, 25) == "23:59:59:24"
    assert timecode.format_tc(24 * 3600 * 24, 24) == "00:00:00:00"


def test_empty_input_deterministic():
    for bad in ("", "   ", None):
        with pytest.raises(ValueError, match="空输入"):
            timecode.parse_tc(bad, 29.97)
    # 空输入两次报同样的错
    def err():
        try:
            timecode.parse_tc("", 29.97)
        except ValueError as exc:
            return str(exc)
        return None
    assert err() == err()


def test_single_frame_input():
    assert timecode.to_frames("00:00:00;00", 29.97) == 0
    assert timecode.format_tc(0, 29.97) == "00:00:00;00"
    assert timecode.to_frames(timecode.parse_tc("1800", 29.97), 29.97) == 1800
    assert timecode.format_tc(timecode.parse_tc("0", 29.97), 29.97) == "00:00:00;00"


# ---------- 23.976 / 25 名义帧率 ----------

def test_nominal_rate_conversion():
    assert timecode.to_frames("00:00:01:00", 23.976) == 24
    assert timecode.to_frames("00:00:01:00", 25) == 25
    assert timecode.to_frames("00:01:00:00", 23.976) == 24 * 60
    assert timecode.to_frames("00:01:00:00", 25) == 25 * 60
    assert timecode.nominal_fps(23.976) == 24
    assert timecode.nominal_fps(29.97) == 30


def test_convert_keeps_frame_number():
    # 23.976 -> 25 保持帧号不变，按目标帧率重新分段
    assert timecode.convert_tc("00:00:01:00", 23.976, 25) == "00:00:00:24"
    assert timecode.convert_tc("00:00:00:24", 25, 23.976) == "00:00:01:00"


# ---------- 确定性 ----------

def test_deterministic_repeat():
    inputs = ["00:00:00;00", "00:01:00;02", "01:00:00;00", "23:59:59;29"]

    def run():
        out = []
        for text in inputs:
            n = timecode.to_frames(timecode.parse_tc(text, 29.97), 29.97)
            out.append((n, timecode.format_tc(timecode.from_frames(n, 29.97), 29.97)))
        return out

    assert run() == run()


# ---------- 多帧率拼接 ----------

def test_concat_continuity():
    segs = [{"fps": 25, "frames": 100}, {"fps": 30, "frames": 60}, {"fps": 24, "frames": 48}]
    r = timecode.concat_segments(segs)
    assert r["total_frames"] == 208
    assert r["starts"] == [0, 100, 160]
    assert r["boundaries"] == [100, 160]


def test_concat_mixed_with_2997_and_segment_tc():
    segs = [
        {"fps": 24, "frames": 24},
        {"fps": 25, "frames": 25},
        {"fps": 30, "frames": 30},
        {"fps": 29.97, "frames": 30},
    ]
    r = timecode.concat_segments(segs)
    assert r["total_frames"] == 109
    assert r["starts"] == [0, 24, 49, 79]
    assert r["boundaries"] == [24, 49, 79]
    # 每段起止时间码按该段帧率换算
    assert r["start_tc"][1] == timecode.tc_from_frames(24, 25)
    assert r["start_tc"][1] == "00:00:00:24"
    assert r["start_tc"][2] == timecode.tc_from_frames(49, 30)
    assert r["start_tc"][3] == timecode.tc_from_frames(79, 29.97)
    assert r["start_tc"][3] == "00:00:02;19"
    # 段边界无缝隙：前段末帧 + 1 == 后段首帧
    for i, boundary in enumerate(r["boundaries"]):
        assert boundary == r["segments"][i]["end"]
        assert boundary == r["segments"][i + 1]["start"]


def test_concat_roundtrip_at_boundaries_mixed_rates():
    segs = [
        {"fps": 24, "frames": 50},
        {"fps": 25, "frames": 50},
        {"fps": 30, "frames": 50},
        {"fps": 29.97, "frames": 50},
    ]
    r = timecode.concat_segments(segs)
    # 每个拼接点两侧：段内首尾帧的往返换算仍成立
    for start, seg in zip(r["starts"], r["segments"]):
        for local in (0, 1, seg["frames"] - 1):
            absolute = start + local
            tc = timecode.tc_from_frames(absolute, seg["fps"])
            assert timecode.frames_from_tc(tc, seg["fps"]) == absolute
    # 拼接点本身：前段末帧 +1 == 后段首帧，且后段首帧按后段帧率往返
    for boundary, nxt in zip(r["boundaries"], r["segments"][1:]):
        assert timecode.frames_from_tc(
            timecode.tc_from_frames(boundary, nxt["fps"]), nxt["fps"]
        ) == boundary
        assert timecode.frames_from_tc(
            timecode.tc_from_frames(boundary - 1, nxt["fps"]), nxt["fps"]
        ) == boundary - 1


def test_concat_empty_and_single():
    assert timecode.concat_segments([])["total_frames"] == 0
    assert timecode.concat_segments([])["starts"] == []
    one = timecode.concat_segments([{"fps": 25, "frames": 1}])
    assert one["total_frames"] == 1
    assert one["starts"] == [0]
    assert one["boundaries"] == []
    assert one["start_tc"] == ["00:00:00:00"]
    assert one["end_tc"] == ["00:00:00:00"]


def test_concat_rejects_bad_segment():
    with pytest.raises(ValueError):
        timecode.concat_segments([{"fps": 25, "frames": -1}])
    with pytest.raises(ValueError):
        timecode.concat_segments([{"frames": 10}])
    with pytest.raises(ValueError):
        timecode.concat_segments(["nope"])


# ---------- 跨日拼接：回绕但单调 ----------

def test_concat_midnight_monotonic():
    segs = [{"fps": 25, "frames": 100000}, {"fps": 25, "frames": 100000}]
    r = timecode.concat_segments(segs)
    assert r["total_frames"] == 200000
    assert all(b > a for a, b in zip(r["starts"], r["starts"][1:]))
    assert all(s >= 0 for s in r["starts"])


def test_concat_crossing_midnight_wraps_tc_not_index():
    day = timecode.day_frames(25)
    segs = [{"fps": 25, "frames": day - 10}, {"fps": 25, "frames": 20}]
    r = timecode.concat_segments(segs)
    assert r["total_frames"] == day + 10
    assert r["starts"] == [0, day - 10]
    # 第二段跨越午夜：起始时间码回绕到 23:59:59:xx，帧号仍单调递增
    assert r["start_tc"][1] == "23:59:59:15"
    assert r["starts"][1] > r["starts"][0]
    assert r["day_index"] == [0, 0]
    assert r["segments"][1]["start"] == day - 10
    # 段内回绕：第二段最后 1 帧在午夜后，不产生负帧号
    assert r["end_tc"][1] == timecode.tc_from_frames(day + 9, 25)
    assert r["end_tc"][1] == "00:00:00:09"
    assert r["segments"][1]["day_index"] == 0  # 起始在午夜前


# ---------- 时基对齐 ----------

def test_align_reports_offset():
    r = timecode.align_to_reference("00:00:10:00", 25, 10.2, tol_frames=8)
    assert abs(r["offset_frames"]) <= 8
    assert r["error_frames"] <= 8
    assert r["frames"] == 250


def test_align_exact_and_zero_offset():
    r = timecode.align_to_reference("00:00:10:00", 25, 10.0)
    assert r["frames"] == 250
    assert r["offset_frames"] == 0
    assert r["error_frames"] == 0
    assert r["aligned_tc"] == "00:00:10:00"
    assert r["aligned_frames"] == 250


def test_align_drop_frame_uses_real_rate():
    # 29.97 对齐使用真实帧率 30000/1001，而非名义 30
    r = timecode.align_to_reference("00:01:00;02", 29.97, 60.0, tol_frames=2)
    assert r["frames"] == 1800
    assert r["reference_frames"] == 1798
    assert r["offset_frames"] == -2
    assert r["error_frames"] <= 2
    assert r["aligned_frames"] == 1798
    assert r["aligned_tc"] == "00:00:59;28"


def test_align_out_of_tolerance_raises():
    with pytest.raises(ValueError, match="超出容差"):
        timecode.align_to_reference("00:00:00:00", 25, 5.0, tol_frames=2)
    with pytest.raises(ValueError, match="容差不能为负"):
        timecode.align_to_reference("00:00:00:00", 25, 0.0, tol_frames=-1)
    # 容差边界：恰好等于容差时可通过
    r = timecode.align_to_reference("00:00:10:00", 25, 10.08, tol_frames=2)
    assert r["offset_frames"] == 2
    assert r["error_frames"] == 0


def test_align_midnight_anchor():
    # 外部锚点跨越午夜：23:59:59:24 之后 1 帧即 00:00:00:00，偏移 +1 帧
    r = timecode.align_to_reference("23:59:59:24", 25, 86400.0, tol_frames=1)
    day = timecode.day_frames(25)
    assert r["frames"] == day - 1
    assert r["reference_frames"] == day
    assert r["offset_frames"] == 1
    assert r["aligned_frames"] == day
    assert r["aligned_tc"] == "00:00:00:00"  # 对齐后跨过午夜回绕
    assert r["error_frames"] == 0


def test_align_drop_frame_exact_anchor():
    # 29.97：60.06 真实秒恰好对应帧 1800（1800*1001/30000 = 60.06）
    r = timecode.align_to_reference("00:01:00;02", 29.97, 60.06)
    assert r["reference_frames"] == 1800
    assert r["offset_frames"] == 0
    assert r["error_frames"] == 0


def test_align_idempotent_report():
    # 同一输入跑两次，偏移量与结果一致
    a = timecode.align_to_reference("00:00:10:00", 25, 10.2, tol_frames=8)
    b = timecode.align_to_reference("00:00:10:00", 25, 10.2, tol_frames=8)
    assert a == b
