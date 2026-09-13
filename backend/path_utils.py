"""路径归属(local / cd2)推断与日志标注工具"""
import os


def infer_path_via(path) -> str:
    """按 CD2 客户端挂载点前缀推断路径归属；非挂载点路径返回 local"""
    if not path:
        return "local"
    from clients.manager import ClientManager
    for c in ClientManager.get_all_clients():
        if c.get("type") == "cd2":
            mount = (c.get("mount_path") or "").strip()
            if mount and os.path.abspath(str(path)).startswith(os.path.abspath(mount)):
                return "cd2"
    return "local"


def via_tag(path, via=None, force_cd2=False) -> str:
    """日志用归属标注：路径后附加 (本地)/(CD2)"""
    if not path:
        return ""
    if not force_cd2 and not via:
        via = infer_path_via(path)
    return f" ({'CD2' if (force_cd2 or via == 'cd2') else '本地'})"
