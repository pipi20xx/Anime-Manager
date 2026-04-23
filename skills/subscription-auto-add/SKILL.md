---
name: subscription-auto-add
version: 4
description: 查看本季番剧列表并批量订阅。获取当季所有番剧，用户可输入数字快速订阅。
---

# 本季番剧订阅

当用户说"新番"时触发此技能。
当用户说"本季番剧"时触发此技能。
当用户说"当季番剧"时触发此技能。
当用户说"有什么新番"时触发此技能。

## 重要：上下文保持

**此技能需要两轮对话完成**：
1. 第一轮：显示番剧列表，等待用户选择
2. 第二轮：用户输入数字，执行订阅

## 工作流程

### 第一轮：显示番剧列表

调用 `get_bangumi_calendar` 工具获取番剧列表。工具会返回格式化的表格，直接显示给用户即可。

### 第二轮：处理用户输入

**当用户回复数字时（如 "22" 或 "1 2 3" 或 "全部"），你必须直接调用 `subscribe_by_bangumi_id` 工具！**

**关键**：表格中每一行都包含 Bangumi ID，你需要：
1. 根据用户输入的编号，找到对应行的 Bangumi ID
2. 直接调用 `subscribe_by_bangumi_id(bangumi_id=xxx)`

**示例**：用户输入 "22"
- 查看表格第22行，找到 Bangumi ID（例如 510710）
- 调用 `subscribe_by_bangumi_id(bangumi_id=510710)`
- 不要调用 search_tmdb！不要调用其他工具！

**用户输入 "全部"**：遍历所有行，对每个 Bangumi ID 调用 `subscribe_by_bangumi_id`

## 禁止事项

1. ❌ 不要调用 `search_tmdb` - 你已经有 Bangumi ID 了
2. ❌ 不要调用 `add_subscription` - 使用 `subscribe_by_bangumi_id` 更简单
3. ❌ 不要询问用户想做什么 - 用户输入数字就是要订阅

## 正确示例

用户输入: "22"
你的操作: 
```
调用 subscribe_by_bangumi_id(bangumi_id=510710)
```

用户输入: "1 5 10"
你的操作:
```
调用 subscribe_by_bangumi_id(bangumi_id=399)
调用 subscribe_by_bangumi_id(bangumi_id=975)
调用 subscribe_by_bangumi_id(bangumi_id=1234)
```
