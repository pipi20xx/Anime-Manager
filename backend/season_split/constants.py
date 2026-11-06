# -*- coding: utf-8 -*-
"""番剧分季拆分 · 常量与外部服务默认值。

TVDB 的 Key 是**官方共用 Key**（Lens 内置、社区通用），可在系统设置里覆盖自己的 Key；
未填写时用这里的默认值。
"""

DEFAULT_TVDB_BASE = "https://api4.thetvdb.com/v4"
DEFAULT_TVDB_KEY = "d3158670-26f0-48bb-9267-2f63781dca6b"

DEFAULT_BANGUMI_BASE = "https://api.bgm.tv"

DEFAULT_CURE_SOURCE = "https://raw.githubusercontent.com/wikrin/CureTMDb/main/tv.json"

# TMDB genre：动画
ANIME_GENRE_ID = 16

# 生成规则时用的版本标记（写进规则注释头，便于人工辨认来源）
AUTO_HEADER_PREFIX = "# [自动分季]"
