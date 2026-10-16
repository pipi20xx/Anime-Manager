"""字体管家核心模块 —— assfonts 的 Python 封装。

模块划分：
- binary      : 二进制定位 / 版本探测 / 在线更新（GitHub Release）
- ass_parser  : ASS 字幕解析（引用字体清单、是否已内嵌字体）
- index_store : assfonts 字体索引（fonts.json）的构建与读取
- runner      : 调用 assfonts 对单个字幕做子集化并内嵌字体

设计约定：
- 所有对外函数均不抛异常（返回结构化结果），由路由层决定 HTTP 语义；
- 子进程一律异步（asyncio.create_subprocess_exec），不阻塞事件循环；
- 不引入第三方依赖（仅标准库 + 内置 assfonts 二进制）。
"""
