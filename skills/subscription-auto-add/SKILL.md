---
name: subscription-auto-add
version: 1
description: 智能添加订阅并推荐新番剧。根据用户偏好和当前番剧季节推荐订阅。
---

# 订阅智能添加

当用户询问"推荐一些新番"、"帮我添加订阅"时使用此技能。

## 功能

1. **推荐新番** - 根据当前季节推荐热门番剧
2. **自动添加订阅** - 根据用户选择添加订阅
3. **检查重复** - 避免重复订阅

## 推荐逻辑

- 获取当季新番列表
- 根据用户历史订阅偏好筛选
- 排除已订阅的番剧
- 按热度排序推荐

## API 端点

| 端点 | 用途 |
|------|------|
| `GET /api/subscriptions` | 获取订阅列表 |
| `POST /api/subscriptions` | 添加订阅 |
| `GET /api/tmdb/trending` | 获取热门番剧 |
| `GET /api/bangumi/calendar` | 获取番剧日历 |
