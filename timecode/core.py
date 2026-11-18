# -*- coding: utf-8 -*-
"""时间码换算与丢帧处理"""



def parse_tc(text, fps):
    """解析时间码"""
    raise NotImplementedError("parse_tc 尚未实现")


def format_tc(frames, fps):
    """生成时间码"""
    raise NotImplementedError("format_tc 尚未实现")


def to_frames(tc, fps):
    """时间码转总帧"""
    raise NotImplementedError("to_frames 尚未实现")


def from_frames(n, fps):
    """总帧转时间码"""
    raise NotImplementedError("from_frames 尚未实现")



def concat_segments(segments):
    """多帧率拼接：返回 dict(total_frames, starts, boundaries)。"""
    raise NotImplementedError("concat_segments 尚未实现")


def tc_from_frames(frames, fps):
    """按给定帧率把帧号格式化为时间码字符串。"""
    raise NotImplementedError("tc_from_frames 尚未实现")


def frames_from_tc(text, fps):
    """把时间码字符串按给定帧率换算为帧号。"""
    raise NotImplementedError("frames_from_tc 尚未实现")


def align_to_reference(tc_text, fps, ref_seconds, tol_frames=2):
    """按外部时基对齐：返回 dict(frames, offset_frames, error_frames)。"""
    raise NotImplementedError("align_to_reference 尚未实现")
