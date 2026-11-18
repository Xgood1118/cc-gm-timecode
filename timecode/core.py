# -*- coding: utf-8 -*-
"""时间码换算与丢帧处理（仅 Python 标准库，无第三方依赖）。

换算约定
--------
- 29.97 fps（30000/1001）：SMPTE 丢帧时间码（drop-frame），名义帧率 30。
  除整十分（分钟数为 10 的倍数）外，每分钟跳过帧号 00、01 两帧；
  输出/解析使用 ``;`` 分隔帧号。一天共 2589408 帧。
- 23.976 fps（24000/1001）：按名义帧率 24 处理，非丢帧。
- 24 / 25 / 30 fps：按给定帧率，非丢帧。
- 其他 fps：按 ``round(fps)`` 的名义帧率处理，非丢帧。
- 任何帧号都按 24 小时回绕，负数取模后同样落到 [0, 一天帧数) 内。
"""

import math
import re
from collections import namedtuple

__all__ = [
    "TC",
    "TimecodeError",
    "SegmentError",
    "parse_tc",
    "format_tc",
    "to_frames",
    "from_frames",
    "tc_from_frames",
    "frames_from_tc",
    "concat_segments",
    "align_to_reference",
    "convert_tc",
    "nominal_fps",
    "day_frames",
]

#: 时间码结构：时、分、秒、帧、是否丢帧
TC = namedtuple("TC", ["hours", "minutes", "seconds", "frames", "drop"])

_NTSC_RATE = 30000 / 1001  # 29.97
_FILM_RATE = 24000 / 1001  # 23.976
_RATE_TOLERANCE = 0.01  # 识别 29.97 / 23.976 的容差
_DROP_PER_MINUTE = 2  # 每个非整十分分钟跳过的帧数
_SECONDS_PER_DAY = 24 * 60 * 60
_MINUTES_PER_DAY = 24 * 60

_TC_RE = re.compile(r"^(\d{1,2}):(\d{1,2}):(\d{1,2})([:;])(\d{1,2})$")

# 字段名 -> (正则分组号, 起始字符的 1 基位置)
_FIELD_POS = {
    "小时位": 1,
    "分钟位": 2,
    "秒位": 3,
    "分隔符": 4,
    "帧位": 5,
}


class TimecodeError(ValueError):
    """时间码错误。

    继承 :class:`ValueError`，额外携带出错字段名与字段起始字符位置，
    便于调用方或 CLI 指出错在哪一位。
    """

    def __init__(self, message, field=None, position=None):
        super().__init__(message)
        self.field = field
        self.position = position


class SegmentError(ValueError):
    """拼接片段参数错误。"""


def _coerce_fps(fps):
    """把 fps 规范为有限的浮点数，非法值直接报错。"""
    try:
        value = float(fps)
    except (TypeError, ValueError):
        raise TimecodeError("fps 非法：%r（应为正数）" % (fps,), field="fps")
    if not math.isfinite(value) or value <= 0:
        raise TimecodeError("fps 非法：%r（应为有限正数）" % (fps,), field="fps")
    return value


def nominal_fps(fps):
    """返回名义帧率（整数）：29.97→30，23.976→24，25→25，24→24。"""
    value = _coerce_fps(fps)
    nominal = int(round(value))
    if nominal < 1:
        raise TimecodeError(
            "fps 非法：%r（名义帧率小于 1）" % (fps,), field="fps"
        )
    return nominal


def _is_drop_fps(fps):
    """是否为 29.97 丢帧时基。"""
    value = _coerce_fps(fps)
    return int(round(value)) == 30 and abs(value - _NTSC_RATE) < _RATE_TOLERANCE


def _real_fps(fps):
    """真实播放帧率（用于把“真实秒”换算成帧数）。

    29.97 用 30000/1001、23.976 用 24000/1001，其余帧率原样返回。
    """
    value = _coerce_fps(fps)
    if _is_drop_fps(value):
        return _NTSC_RATE
    if int(round(value)) == 24 and abs(value - _FILM_RATE) < _RATE_TOLERANCE:
        return _FILM_RATE
    return value


def day_frames(fps):
    """一天的帧数（丢帧时扣除跳过的帧）。"""
    nominal = nominal_fps(fps)
    if _is_drop_fps(fps):
        dropped = _DROP_PER_MINUTE * (_MINUTES_PER_DAY - _MINUTES_PER_DAY // 10)
        return nominal * _SECONDS_PER_DAY - dropped
    return nominal * _SECONDS_PER_DAY


def _field_error(label, match, message):
    """构造带字段位置的错误（1 基字符位置）。"""
    group = _FIELD_POS[label]
    position = match.start(group) + 1
    raise TimecodeError(
        "%s（第 %d 个字符起）%s" % (label, position, message),
        field=label,
        position=position,
    )


def parse_tc(text, fps):
    """解析时间码，返回 :class:`TC`。

    - 接受 ``HH:MM:SS:FF``（非丢帧）或 ``HH:MM:SS;FF``（丢帧，仅 29.97）。
    - 纯数字串按“总帧数”处理，与 :func:`from_frames` 一致。
    - 空输入、格式错误、字段越界、丢帧位不合法都会抛出
      :class:`TimecodeError`（``ValueError`` 子类），并指出出错字段的位置。
    """
    value = _coerce_fps(fps)
    nominal = nominal_fps(value)
    drop_capable = _is_drop_fps(value)

    if text is None:
        raise TimecodeError("空输入：时间码为 None", field="输入")
    raw = str(text).strip()
    if not raw:
        raise TimecodeError("空输入：时间码字符串为空", field="输入")
    if raw.isdigit():
        # 裸数字串按总帧数处理（对 24 小时回绕），确定性结果
        return from_frames(int(raw), value)

    match = _TC_RE.match(raw)
    if not match:
        raise TimecodeError(
            "格式错误：%r（应为 HH:MM:SS:FF，29.97 下也可为 HH:MM:SS;FF）" % raw,
            field="格式",
        )

    hh, mm, ss, sep, ff = match.groups()
    hours, minutes, seconds, frames = int(hh), int(mm), int(ss), int(ff)

    if hours > 23:
        _field_error("小时位", match, "越界：%d（应按 24 小时制取 0-23）" % hours)
    if minutes > 59:
        _field_error("分钟位", match, "越界：%d（应取 0-59）" % minutes)
    if seconds > 59:
        _field_error("秒位", match, "越界：%d（应取 0-59）" % seconds)
    if sep == ";" and not drop_capable:
        _field_error(
            "分隔符",
            match,
            "不合法：';' 仅用于 29.97 丢帧时间码，当前 fps=%s" % value,
        )
    if frames > nominal - 1:
        _field_error(
            "帧位",
            match,
            "越界：%d（fps=%s 名义帧率 %d，应取 0-%d）"
            % (frames, value, nominal, nominal - 1),
        )

    drop = sep == ";"
    # SMPTE 丢帧规则：除分钟数为 10 的倍数的整十分外，每分钟第 0 秒的
    # 帧号 00、01 不存在（00:00:00 属于整十分，帧 00/01 合法）。
    if drop and seconds == 0 and frames < _DROP_PER_MINUTE and minutes % 10 != 0:
        _field_error(
            "帧位",
            match,
            "丢帧位不存在：%02d:%02d 的第 %d 帧在丢帧模式下被跳过"
            "（整十分除外）" % (minutes, seconds, frames),
        )

    return TC(hours, minutes, seconds, frames, drop)


def to_frames(tc, fps):
    """时间码转总帧号（0 起，落在 [0, 一天帧数)）。

    ``tc`` 可以是 :class:`TC` 或时间码字符串；字符串会先经
    :func:`parse_tc` 校验。
    """
    value = _coerce_fps(fps)
    nominal = nominal_fps(value)
    if isinstance(tc, str):
        tc = parse_tc(tc, value)
    elif not isinstance(tc, TC):
        raise TimecodeError(
            "参数非法：需要 TC 或时间码字符串，收到 %r" % (tc,), field="输入"
        )
    if tc.drop and not _is_drop_fps(value):
        raise TimecodeError(
            "丢帧标记与 fps=%s 不匹配（';' 仅用于 29.97）" % value,
            field="分隔符",
        )
    total_minutes = tc.hours * 60 + tc.minutes
    base = ((total_minutes * 60) + tc.seconds) * nominal + tc.frames
    if tc.drop:
        base -= _DROP_PER_MINUTE * (total_minutes - total_minutes // 10)
    return base


def from_frames(n, fps):
    """总帧号转 :class:`TC`，按 24 小时回绕，不产生负帧号。"""
    value = _coerce_fps(fps)
    nominal = nominal_fps(value)
    drop = _is_drop_fps(value)

    try:
        number = int(n)
    except (TypeError, ValueError):
        raise TimecodeError("帧号非法：%r（应为整数）" % (n,), field="帧号")

    number %= day_frames(value)

    if drop:
        # 每 10 分钟一个循环：名义 18000 帧，实际 17982 帧；
        # 非整十分分钟 1798 帧，整十分分钟 1800 帧。
        frames_per_ten = nominal * 600 - _DROP_PER_MINUTE * 9
        frames_per_minute = nominal * 60 - _DROP_PER_MINUTE
        blocks, rest = divmod(number, frames_per_ten)
        if rest < nominal * 60:
            adjusted = number + _DROP_PER_MINUTE * 9 * blocks
        else:
            extra = (rest - nominal * 60) // frames_per_minute + 1
            adjusted = (
                number
                + _DROP_PER_MINUTE * 9 * blocks
                + _DROP_PER_MINUTE * extra
            )
        number = adjusted

    seconds_total, frames = divmod(number, nominal)
    minutes_total, seconds = divmod(seconds_total, 60)
    hours, minutes = divmod(minutes_total, 60)
    return TC(hours, minutes, seconds, frames, drop)


def format_tc(frames, fps):
    """生成时间码字符串。

    ``frames`` 可以是 :class:`TC`（保留其丢帧标记与分隔符），也可以是
    总帧号（按 ``fps`` 从 :func:`from_frames` 反推）。
    """
    value = _coerce_fps(fps)
    if isinstance(frames, TC):
        tc = frames
    else:
        try:
            number = int(frames)
        except (TypeError, ValueError):
            raise TimecodeError(
                "帧号非法：%r（应为整数或 TC）" % (frames,), field="帧号"
            )
        tc = from_frames(number, value)
    sep = ";" if tc.drop else ":"
    return "%02d:%02d:%02d%s%02d" % (
        tc.hours,
        tc.minutes,
        tc.seconds,
        sep,
        tc.frames,
    )


def tc_from_frames(frames, fps):
    """按给定帧率把帧号格式化为时间码字符串（24 小时回绕）。"""
    return format_tc(int(frames) % day_frames(fps), fps)


def frames_from_tc(text, fps):
    """把时间码字符串按给定帧率换算为帧号（先校验再换算）。"""
    return to_frames(parse_tc(text, fps), fps)


def convert_tc(text, from_fps, to_fps):
    """在两种帧率之间换算时间码：**保持帧号不变**，按目标帧率重新分段。

    23.976 按名义 24、25 按名义 25，不做 1000/1001 速率校正；
    即同一帧号在源/目标帧率下各自被解释。
    """
    source = _coerce_fps(from_fps)
    target = _coerce_fps(to_fps)
    number = frames_from_tc(text, source)
    return tc_from_frames(number, target)


def concat_segments(segments):
    """多帧率片段首尾拼接。

    每个片段形如 ``{"fps": 25, "frames": 100}``，``frames`` 为该片段帧数。
    返回 dict：

    - ``total_frames``：所有片段帧数之和（单调递增，不回绕）
    - ``starts``：每段起始总帧号（严格递增，段间无缝隙）
    - ``boundaries``：内部拼接点（第 i 段结束、第 i+1 段开始的帧号）
    - ``start_tc`` / ``end_tc``：每段按自身帧率换算的起止时间码（按 24h 回绕）
    - ``day_index``：每段起始时刻所在的天数（用该段帧率的一天帧数计算）
    - ``segments``：逐段明细
    """
    starts = []
    boundaries = []
    start_tc = []
    end_tc = []
    day_index = []
    details = []
    cursor = 0

    for index, segment in enumerate(segments):
        if not isinstance(segment, dict):
            raise SegmentError("第 %d 段非法：需要 dict，收到 %r" % (index, segment))
        if "fps" not in segment:
            raise SegmentError("第 %d 段缺少 fps" % index)
        fps = _coerce_fps(segment["fps"])
        try:
            count = int(segment.get("frames", 0))
        except (TypeError, ValueError):
            raise SegmentError(
                "第 %d 段帧数非法：%r" % (index, segment.get("frames"))
            )
        if count < 0:
            raise SegmentError("第 %d 段帧数为负：%d" % (index, count))

        start = cursor
        end = cursor + count
        starts.append(start)
        start_tc.append(tc_from_frames(start, fps))
        end_tc.append(tc_from_frames(end - 1, fps) if count else start_tc[-1])
        day_index.append(start // day_frames(fps))
        details.append(
            {
                "index": index,
                "fps": fps,
                "frames": count,
                "start": start,
                "end": end,
                "start_tc": start_tc[-1],
                "end_tc": end_tc[-1],
                "day_index": day_index[-1],
            }
        )

        cursor = end
        if index < len(segments) - 1:
            boundaries.append(cursor)

    return {
        "total_frames": cursor,
        "starts": starts,
        "boundaries": boundaries,
        "start_tc": start_tc,
        "end_tc": end_tc,
        "day_index": day_index,
        "segments": details,
    }


def align_to_reference(tc_text, fps, ref_seconds, tol_frames=2):
    """按外部时基锚点对齐时间码。

    ``ref_seconds`` 是某个真实时刻的秒数（外部时基），``tc_text`` 是该时刻
    在素材中的时间码。用真实帧率（29.97→30000/1001，23.976→24000/1001）
    把秒换算成帧，与时间码帧号比较得到偏移量。

    返回 dict：

    - ``frames``：输入时间码的帧号（未对齐）
    - ``offset_frames``：对齐使用的偏移量（参考帧数 − 输入帧号）
    - ``error_frames``：对齐后的残差（帧，四舍五入）
    - ``aligned_frames`` / ``aligned_tc``：施加偏移后的帧号与时间码
    - ``tolerance_frames`` / ``reference_frames`` / 帧率信息

    ``abs(offset_frames) > tol_frames`` 时抛出 :class:`TimecodeError`。
    """
    value = _coerce_fps(fps)
    try:
        tolerance = int(tol_frames)
    except (TypeError, ValueError):
        raise TimecodeError("容差非法：%r" % (tol_frames,), field="容差")
    if tolerance < 0:
        raise TimecodeError("容差不能为负：%d" % tolerance, field="容差")

    frames = frames_from_tc(tc_text, value)

    try:
        ref = float(ref_seconds)
    except (TypeError, ValueError):
        raise TimecodeError("参考秒数非法：%r" % (ref_seconds,), field="参考秒数")
    if not math.isfinite(ref):
        raise TimecodeError("参考秒数非法：%r" % (ref_seconds,), field="参考秒数")

    real_fps = _real_fps(value)
    ref_exact = ref * real_fps
    ref_frames = int(round(ref_exact))
    offset = ref_frames - frames

    if abs(offset) > tolerance:
        raise TimecodeError(
            "超出容差：偏移 %d 帧，容差 %d 帧（输入 %s @%sfps，参考 %.6fs）"
            % (offset, tolerance, tc_text, value, ref),
            field="容差",
        )

    aligned_frames = frames + offset
    return {
        "frames": frames,
        "offset_frames": offset,
        "error_frames": int(round(abs(ref_exact - aligned_frames))),
        "aligned_frames": aligned_frames,
        "aligned_tc": tc_from_frames(aligned_frames, value),
        "tolerance_frames": tolerance,
        "reference_frames": ref_frames,
        "fps": value,
        "nominal_fps": nominal_fps(value),
        "real_fps": real_fps,
    }
