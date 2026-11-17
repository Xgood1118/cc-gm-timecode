# -*- coding: utf-8 -*-
"""命令行入口：读取时间码文件，逐条换算为帧号并输出 JSON。"""

import argparse
import json

import timecode as m


def convert_file(path, fps):
    """逐行换算，返回确定性结果列表（非法条目记录原因，不中断）。"""
    results = []
    with open(path, encoding="utf-8") as f:
        lines = f.read().splitlines()
    for lineno, raw in enumerate(lines, 1):
        text = raw.strip()
        if not text:
            continue  # 空行：确定性跳过
        entry = {"line": lineno, "input": text}
        try:
            tc = m.parse_tc(text, fps)
            n = m.to_frames(tc, fps)
            back = m.from_frames(n, fps)
            n2 = m.to_frames(back, fps)
            entry.update(
                ok=True,
                frames=n,
                roundtrip=m.format_tc(back, fps),
                roundtrip_diff=n2 - n,
            )
        except ValueError as e:
            entry.update(ok=False, error=str(e))
        results.append(entry)
    return results


def main():
    ap = argparse.ArgumentParser(description="时间码换算与丢帧处理")
    ap.add_argument("input", help="时间码文本文件，每行一条")
    ap.add_argument("--fps", type=float, required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    results = convert_file(a.input, a.fps)
    payload = {"fps": a.fps, "results": results}
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    ok = sum(1 for r in results if r["ok"])
    print("共 %d 条：%d 条换算成功，%d 条非法" % (len(results), ok, len(results) - ok))


if __name__ == "__main__":
    main()
