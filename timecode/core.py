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

