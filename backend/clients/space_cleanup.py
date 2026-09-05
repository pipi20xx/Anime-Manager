"""
QB 空间回收引擎 —— 基于磁盘占用阈值的自动清理模块。

核心思路：
1. 调用 QB API 获取所有种子信息 (含 save_path, size, added_on, state 等)
2. 按 save_path 分组统计总占用
3. 对每条规则，当某路径总占用超过阈值时，从最老的种子开始删除
4. 支持 protected_tags / protected_categories 保护特定种子不被删除
5. 支持 min_seeders 保护做种数低于阈值的种子

设计原则：
- 本模块只做"纯逻辑"，不读取配置、不写日志到数据库、不发送通知
- 调用方 (scheduler.py / router) 负责编排：读配置 → 调引擎 → 记日志 → 发通知
"""
import logging
import os
from typing import Dict, List, Any, Tuple, Optional

logger = logging.getLogger(__name__)

# ── 常量 ──
GB = 1024 ** 3
MB = 1024 ** 2


def _path_matches(torrent_path: str, rule_path: str) -> bool:
    """
    判断种子的 save_path 是否属于规则匹配范围。
    采用前缀匹配：torrent_path 以 rule_path 开头即视为匹配。
    自动处理末尾斜杠差异。
    """
    if not torrent_path or not rule_path:
        return False
    tp = os.path.normpath(torrent_path).rstrip(os.sep)
    rp = os.path.normpath(rule_path).rstrip(os.sep)
    return tp == rp or tp.startswith(rp + os.sep)


def _is_protected(torrent: Dict[str, Any], rule: Dict[str, Any]) -> bool:
    """
    判断种子是否受保护（不应被删除）。
    保护条件：
    1. 种子标签包含 rule['protected_tags'] 中的任一标签
    2. 种子分类包含 rule['protected_categories'] 中的任一分类
    3. 种子的做种数 < rule['min_seeders']
    """
    # 标签保护
    protected_tags = rule.get("protected_tags", [])
    if protected_tags:
        torrent_tags = set(
            t.strip() for t in str(torrent.get("tags", "")).split(",") if t.strip()
        )
        if torrent_tags & set(protected_tags):
            return True

    # 分类保护
    protected_cats = rule.get("protected_categories", [])
    if protected_cats:
        torrent_cat = torrent.get("category", "")
        if torrent_cat and torrent_cat in protected_cats:
            return True

    # 做种数保护
    min_seeders = rule.get("min_seeders", 0)
    if min_seeders > 0:
        num_seeders = torrent.get("num_seeds", 0) or 0
        if num_seeders < min_seeders:
            return True

    return False


def _is_downloading(torrent: Dict[str, Any]) -> bool:
    """判断种子是否正在下载中（不应被删除）。"""
    state = str(torrent.get("state", "")).lower()
    progress = float(torrent.get("progress", 0) or 0)
    return progress < 1.0 and state in (
        "downloading", "stalleddl", "checkingdl", "metadownload", "forceddl"
    )


def group_torrents_by_path(
    torrents: List[Dict[str, Any]],
    rules: List[Dict[str, Any]],
    client_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    将种子按规则路径分组，返回每组的统计信息。

    :param torrents: 某个客户端的种子列表
    :param rules: 所有规则
    :param client_id: 当前客户端 ID，用于过滤 rule['client_id']
                     如果规则指定了 client_id 且与当前 client_id 不匹配，则跳过该规则

    返回结构:
    [
        {
            "rule": {原始规则},
            "path": "/downloads",
            "max_size_bytes": 536870912000,
            "total_size_bytes": 600000000000,
            "torrent_count": 42,
            "over_limit": True,
            "over_by_bytes": 63129120000,
            "torrents": [ {种子信息} ]  # 该路径下所有种子
        },
        ...
    ]
    """
    results: List[Dict[str, Any]] = []

    for rule in rules:
        # ── 规则指定了下载器，且不是当前下载器 → 跳过 ──
        rule_client_id = rule.get("client_id", "")
        if rule_client_id and client_id and rule_client_id != client_id:
            continue

        rule_path = rule.get("path", "")
        max_size_gb = float(rule.get("max_size_gb", 0) or 0)
        max_size_bytes = int(max_size_gb * GB)

        matched_torrents = [
            t for t in torrents
            if _path_matches(t.get("save_path", ""), rule_path)
        ]

        total_size = sum(
            int(t.get("size", 0) or t.get("total_size", 0) or 0)
            for t in matched_torrents
        )

        over_by = max(0, total_size - max_size_bytes) if max_size_bytes > 0 else 0

        results.append({
            "rule": rule,
            "path": rule_path,
            "max_size_bytes": max_size_bytes,
            "max_size_gb": max_size_gb,
            "total_size_bytes": total_size,
            "total_size_gb": round(total_size / GB, 2),
            "torrent_count": len(matched_torrents),
            "over_limit": over_by > 0,
            "over_by_bytes": over_by,
            "over_by_gb": round(over_by / GB, 2),
            "torrents": matched_torrents,
        })

    return results


def select_torrents_for_deletion(
    group: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    从一个分组中选择需要删除的种子列表。

    策略：
    1. 过滤掉正在下载的种子
    2. 过滤掉受保护的种子
    3. 按 added_on 升序排列（最老的在前）
    4. 从最老的开始累加，直到累计释放体积 >= over_by_bytes
    5. 返回被选中的种子列表
    """
    over_by = group.get("over_by_bytes", 0)
    if over_by <= 0:
        return []

    rule = group.get("rule", {})
    torrents = group.get("torrents", [])

    # ── 过滤 ──
    candidates = [
        t for t in torrents
        if not _is_downloading(t) and not _is_protected(t, rule)
    ]

    # ── 按添加时间升序（最老的在前） ──
    candidates.sort(key=lambda t: float(t.get("added_on", 0) or 0))

    # ── 累加删除直到释放足够空间 ──
    selected: List[Dict[str, Any]] = []
    freed = 0

    for t in candidates:
        if freed >= over_by:
            break
        size = int(t.get("size", 0) or t.get("total_size", 0) or 0)
        freed += size
        selected.append(t)

    return selected


def format_size(size_bytes: float) -> str:
    """将字节数格式化为人类可读的体积字符串。"""
    if size_bytes >= GB:
        return f"{size_bytes / GB:.2f} GB"
    elif size_bytes >= MB:
        return f"{size_bytes / MB:.1f} MB"
    else:
        return f"{size_bytes:.0f} B"
