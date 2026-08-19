---
name: get_weather
description: 获取指定城市的实时天气信息
entry: scripts/weather.py
parameters:
  city:
    type: string
    description: 城市名称
    required: true
---

# 天气查询技能

使用 `search_web` 获取公开天气数据，然后整理输出。

## 调用示例

`python scripts/weather.py --city "北京"`

## 依赖

本技能依赖 requests 库，如果无法运行请执行：

```bash
pip install requests
```
