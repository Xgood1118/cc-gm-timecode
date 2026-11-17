# -*- coding: utf-8 -*-
"""时间码换算与丢帧处理（仅标准库）

规则：
- 29.97 fps：丢帧（drop-frame）时间码，名义帧率 30，每分钟丢 2 帧，
  整十分（分钟为 10 的倍数）不丢。分隔符用 ';'。
- 23.976 fps：按名义帧率 24 处理，非丢帧。
- 25 fps：名义帧率 25，非丢帧。
- 其他 fps：按 round(fps) 的名义帧率处理，非丢帧。
- 所有换算按 24 小时回绕，不产生负帧号。
"""

import re
from collections import namedtuple

__all__ = ["TC", "parse_tc", "format_tc", "to_frames", "from_frames"]

#: 时间码结构：时、分、秒、帧、是否丢帧
TC = namedtuple("TC", ["hours", "minutes", "seconds", "frames", "drop"])

_TC_RE = re.compile(r"^(\d{1,2}):(\d{1,2}):(\d{1,2})([:;])(\d{1,2})$")

_DROP_FPS = 30000 / 1001  # 29.97
_FPS_TOLERANCE = 0.01
_DROP_PER_MINUTE = 2


def _is_drop_fps(fps):
    return abs(float(fps) - _DROP_FPS) < _FPS_TOLERANCE


def _nominal_fps(fps):
    n = int(round(float(fps)))
    if n <= 0:
        raise ValueError("fps 必须为正数，收到 %r" % (fps,))
    return n


def _frames_per_day(fps):
    nominal = _nominal_fps(fps)
    if _is_drop_fps(fps):
        total_minutes = 24 * 60
        dropped = _DROP_PER_MINUTE * (total_minutes - total_minutes // 10)
        return nominal * 86400 - dropped
    return nominal * 86400


def parse_tc(text, fps):
    """解析时间码，返回 TC(hours, minutes, seconds, frames, drop)。

    接受 "HH:MM:SS:FF"（非丢帧）或 "HH:MM:SS;FF"（丢帧，仅 29.97）。
    裸数字串按总帧数处理；空输入报错。非法字段报错并指出错在哪一位。
    """
    nominal = _nominal_fps(fps)
    drop_fps = _is_drop_fps(fps)
    if text is None:
        raise ValueError("空输入：时间码为 None")
    s = str(text).strip()
    if not s:
        raise ValueError("空输入：时间码字符串为空")
    if s.isdigit():
        # 单帧/裸帧号输入：按总帧数处理（对一天回绕）
        return from_frames(int(s), fps)
    m = _TC_RE.match(s)
    if not m:
        raise ValueError(
            "格式错误：%r，应为 HH:MM:SS:FF（非丢帧）或 HH:MM:SS;FF（丢帧）" % s
        )
    hh, mm, ss, sep, ff = m.groups()
    h, mi, sec, fr = int(hh), int(mm), int(ss), int(ff)
    drop = sep == ";"
    if drop and not drop_fps:
        raise ValueError(
            "丢帧分隔符位不合法：';' 仅适用于 29.97，当前 fps=%s" % fps
        )
    if h > 23:
        raise ValueError("小时位越界：%d（应按 24 小时制取 0-23）" % h)
    if mi > 59:
        raise ValueError("分钟位越界：%d（应取 0-59）" % mi)
    if sec > 59:
        raise ValueError("秒位越界：%d（应取 0-59）" % sec)
    if fr > nominal - 1:
        raise ValueError(
            "帧位越界：%d（fps=%s 名义帧率 %d，应取 0-%d）"
            % (fr, fps, nominal, nominal - 1)
        )
    if drop and sec == 0 and fr < _DROP_PER_MINUTE and mi % 10 != 0:
        raise ValueError(
            "丢帧位不存在：%d 分 0 秒的第 %d 帧在丢帧模式下被跳过"
            "（整十分除外）" % (mi, fr)
        )
    return TC(h, mi, sec, fr, drop)


def to_frames(tc, fps):
    """时间码转总帧。tc 可为 TC 或时间码字符串。"""
    if isinstance(tc, str):
        tc = parse_tc(tc, fps)
    nominal = _nominal_fps(fps)
    base = ((tc.hours * 60 + tc.minutes) * 60 + tc.seconds) * nominal + tc.frames
    if tc.drop:
        total_minutes = tc.hours * 60 + tc.minutes
        base -= _DROP_PER_MINUTE * (total_minutes - total_minutes // 10)
    return base


def from_frames(n, fps):
    """总帧转时间码。按 24 小时回绕，不产生负帧号。"""
    nominal = _nominal_fps(fps)
    drop = _is_drop_fps(fps)
    n = int(n) % _frames_per_day(fps)
    if drop:
        # 每 10 分钟一个循环：名义 18000 帧，实存 17982 帧
        fp10 = nominal * 600 - _DROP_PER_MINUTE * 9
        fpm = nominal * 60 - _DROP_PER_MINUTE
        d, r = divmod(n, fp10)
        if r < nominal * 60:
            adj = n + _DROP_PER_MINUTE * 9 * d
        else:
            adj = n + _DROP_PER_MINUTE * 9 * d + _DROP_PER_MINUTE * (
                (r - nominal * 60) // fpm + 1
            )
        n = adj
    sec, fr = divmod(n, nominal)
    mi, sec = divmod(sec, 60)
    h, mi = divmod(mi, 60)
    return TC(h, mi, sec, fr, drop)


def format_tc(frames, fps):
    """生成时间码字符串。frames 可为 TC 或总帧数。"""
    if isinstance(frames, TC):
        tc = frames
    else:
        tc = from_frames(int(frames), fps)
    sep = ";" if tc.drop else ":"
    return "%02d:%02d:%02d%s%02d" % (
        tc.hours, tc.minutes, tc.seconds, sep, tc.frames
    )
