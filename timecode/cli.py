# -*- coding: utf-8 -*-
"""命令行入口：读取时间码文件，逐条换算为帧号并输出 JSON。

用法::

    python -m timecode.cli data/tc.txt --fps 29.97 --out frames.json

输出为确定性 JSON（同样的输入跑两次逐字节一致）：非法条目只记录原因，
不中断整批处理。
"""

import argparse
import json

import timecode as m


def convert_file(path, fps):
    """逐行换算，返回确定性结果列表。"""
    results = []
    with open(path, encoding="utf-8") as handle:
        lines = handle.read().splitlines()
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
        except ValueError as exc:
            # ValueError 的构造参数不含位置信息，位置单独记录
            entry.update(ok=False, error=str(exc))
            for attr in ("field", "position"):
                value = getattr(exc, attr, None)
                if value is not None:
                    entry[attr] = value
        results.append(entry)
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description="时间码换算与丢帧处理")
    parser.add_argument("input", help="时间码文本文件，每行一条")
    parser.add_argument("--fps", type=float, required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    results = convert_file(args.input, args.fps)
    payload = {"fps": args.fps, "results": results}
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")

    ok = sum(1 for item in results if item["ok"])
    print("共 %d 条：%d 条换算成功，%d 条非法"
          % (len(results), ok, len(results) - ok))


if __name__ == "__main__":
    main()
