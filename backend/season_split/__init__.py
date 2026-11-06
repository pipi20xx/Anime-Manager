# -*- coding: utf-8 -*-
"""番剧分季拆分（Season Splitter）。

对外只暴露三件事：
  - `store.as_render_words()`  给识别链路取当前生效的渲染词（同步、纯内存）
  - `service.*`                预览 / 保存 / 编译 / 写剧集组
  - 纯函数内核                 models / splitter / compiler / grouping（可离线测试）

执行方式见 docs/season-split-plan.md：规则编译成渲染词，由现有 RenderEngine 执行，
不新增识别阶段。
"""

__all__ = ["models", "splitter", "compiler", "grouping"]
