#!/usr/bin/env python3
"""
示例脚本：天气查询技能
依赖: requests
"""

import argparse
import sys
import requests


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--city", help="城市名称", required=True)
    args = parser.parse_args()

    city = args.city

    # 这里使用 wttr.in 公开 API，无需 Key
    try:
        url = f"https://wttr.in/{city}?format=3"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        print(resp.text.strip())
    except Exception as e:
        print(f"查询天气失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
