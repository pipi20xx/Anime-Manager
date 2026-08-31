"""
出站 URL 安全校验（SSRF 防护）。

用于接受外部传入 URL 的代理类接口（壁纸代理、Bangumi 图片代理等）：
- 仅允许 http/https
- 禁止携带用户信息的 URL
- 目标域名解析出的所有 IP 均不得为私网/环回/链路本地/保留地址，
  防止借服务器探测内网或云元数据（169.254.169.254 等）
- safe_get 对重定向的每一跳重新校验，防止 302 跳转绕过
"""
import asyncio
import ipaddress
import logging
import socket
from urllib.parse import urlparse, urljoin

import httpx

logger = logging.getLogger(__name__)

MAX_REDIRECTS = 5


class UnsafeURLError(ValueError):
    """URL 未通过出站安全校验"""


def _is_disallowed_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return True
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        addr = addr.ipv4_mapped
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )


def assert_safe_url(url: str) -> None:
    """校验出站 URL，不通过时抛出 UnsafeURLError"""
    try:
        parsed = urlparse(url)
    except Exception as e:
        raise UnsafeURLError(f"URL 解析失败: {e}")

    if parsed.scheme not in ("http", "https"):
        raise UnsafeURLError(f"不允许的协议: {parsed.scheme or '(空)'}")
    if not parsed.hostname:
        raise UnsafeURLError("URL 缺少主机名")
    if parsed.username or parsed.password:
        raise UnsafeURLError("不允许携带用户信息的 URL")

    hostname = parsed.hostname
    try:
        ipaddress.ip_address(hostname)
        candidates = [hostname]
    except ValueError:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        try:
            infos = socket.getaddrinfo(hostname, port, proto=socket.IPPROTO_TCP)
        except socket.gaierror as e:
            raise UnsafeURLError(f"域名解析失败: {hostname}")
        candidates = [info[4][0] for info in infos]

    for ip in candidates:
        if _is_disallowed_ip(ip):
            raise UnsafeURLError(f"目标解析到内网地址，已拒绝: {hostname}")


async def safe_get(client: httpx.AsyncClient, url: str, **kwargs) -> httpx.Response:
    """带逐跳 SSRF 校验的 GET：重定向的每一跳都重新校验目标地址"""
    current = url
    for hop in range(MAX_REDIRECTS + 1):
        # DNS 解析可能阻塞事件循环，放到线程池执行
        await asyncio.to_thread(assert_safe_url, current)
        resp = await client.get(current, follow_redirects=False, **kwargs)
        if resp.is_redirect:
            if hop == MAX_REDIRECTS:
                raise UnsafeURLError("重定向次数过多")
            location = resp.headers.get("location", "")
            if not location:
                return resp
            current = urljoin(current, location)
            continue
        return resp
    raise UnsafeURLError("重定向次数过多")
