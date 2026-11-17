import argparse
import timecode as m


def main():
    ap = argparse.ArgumentParser(description="时间码换算与丢帧处理")
        ap.add_argument("--fps", type=float, required=True)
        ap.add_argument("--out", required=True)
    a = ap.parse_args()
        print("TODO")


if __name__ == "__main__":
    main()
