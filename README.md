# 时间码换算与丢帧处理

一个能正确处理 drop-frame 与普通时间码互转的换算器

## 保留签名

- `parse_tc(text, fps)`
- `format_tc(frames, fps)`
- `to_frames(tc, fps)`
- `from_frames(n, fps)`

## 自测

```
python -m pytest tests -q
python -m timecode.cli data/tc.txt --fps 29.97 --out frames.json
```
