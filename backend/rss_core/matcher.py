import re
import logging
from typing import List, Dict, Any, Tuple, Optional
from models import Rule
from clients.manager import ClientManager
from logger import log_audit
from notification import NotificationManager

logger = logging.getLogger(__name__)

class Matcher:
    """
    处理 RSS 规则匹配的核心逻辑。
    """

    @staticmethod
    def check_match(title: str, must_contain: str, must_not_contain: str, use_regex: bool) -> bool:
        """
        检查标题是否符合规则。
        """
        try:
            title_lower = title.lower()
            if use_regex:
                if must_contain and not re.search(must_contain, title, re.IGNORECASE):
                    return False
                if must_not_contain and re.search(must_not_contain, title, re.IGNORECASE):
                    return False
            else:
                if must_contain:
                    or_groups = must_contain.split('|')
                    group_match_found = False
                    for group in or_groups:
                        group = group.strip()
                        if not group: continue
                        all_keywords_present = True
                        for keyword in group.split():
                            if keyword.lower() not in title_lower:
                                all_keywords_present = False
                                break
                        if all_keywords_present:
                            group_match_found = True
                            break
                    if not group_match_found:
                        return False

                if must_not_contain:
                    exclusion_phrases = must_not_contain.split('|')
                    for phrase in exclusion_phrases:
                        phrase = phrase.strip()
                        if not phrase: continue
                        if phrase.lower() in title_lower:
                            return False
            return True
        except Exception as e:
            logger.error(f"正则匹配出错: {e}")
            return False

    @staticmethod
    async def _download_torrent_file(download_link: str, title: str, guid: str = None) -> Tuple[bool, Optional[bytes], str]:
        """
        下载种子文件内容。
        返回: (是否成功, 种子内容, 错误信息)
        """
        import requests
        import asyncio
        
        try:
            logger.info(f"  -> 正在下载种子文件: {download_link}")
            resp = await asyncio.to_thread(requests.get, download_link, timeout=15)
            resp.raise_for_status()
            torrent_content = resp.content
            
            if not torrent_content or len(torrent_content) < 100:
                error_msg = f"种子文件损坏或长度异常: {len(torrent_content) if torrent_content else 0} 字节"
                logger.error(f"❌ {error_msg} (Title: {title})")
                
                try:
                    from models import Blacklist
                    from database import db
                    async with db.session_scope():
                        bl_item = Blacklist(
                            guid=guid or download_link,
                            title=title,
                            reason=f"Invalid Torrent: {len(torrent_content) if torrent_content else 0}B"
                        )
                        await db.save(bl_item, audit=False)
                    logger.info(f"🚫 已将无效资源加入黑名单: {title}")
                except Exception as ble:
                    logger.error(f"记录黑名单失败: {ble}")
                
                return False, None, error_msg
            
            return True, torrent_content, ""
        except requests.exceptions.HTTPError as http_err:
            error_msg = f"HTTP {http_err.response.status_code}"
            logger.warning(f"种子下载失败: {error_msg} (Title: {title})")
            return False, None, error_msg
        except Exception as e:
            error_msg = str(e)
            logger.error(f"种子下载异常: {error_msg} (Title: {title})")
            return False, None, error_msg

    @staticmethod
    async def download(entry: Dict, rule: Rule) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        将匹配的条目推送到下载客户端。
        返回: (是否成功, InfoHash, 失败原因)
        """
        import requests
        import asyncio
        import re
        
        client_id = rule.target_client_id
        download_link = entry['link']
        fallback_link = entry.get('fallback_link')
        title = entry['title']
        guid = entry.get('guid')
        
        info_hash = None
        if download_link.startswith('magnet:'):
            match = re.search(r'xt=urn:btih:([a-fA-F0-9]{40}|[a-zA-Z2-7]{32})', download_link)
            if match:
                raw_hash = match.group(1).lower()
                if len(raw_hash) == 32:
                    try:
                        import base64
                        import binascii
                        missing_padding = len(raw_hash) % 8
                        if missing_padding:
                            raw_hash += '=' * (8 - missing_padding)
                        info_hash = base64.b32decode(raw_hash.upper()).hex().lower()
                    except Exception as e:
                        logger.warning(f"Base32 hash conversion failed: {e}")
                        info_hash = raw_hash
                else:
                    info_hash = raw_hash
        
        client = ClientManager.get_client(client_id)
        if not client:
            logger.warning(f"无法下载 '{title}': 找不到客户端 ID '{client_id}'")
            log_audit("RSS", "推送失败", f"找不到下载客户端 ID: {client_id}", level="ERROR", details=title)
            return False, None, f"找不到下载客户端 ID: {client_id}"

        kwargs = {
            'save_path': rule.save_path,
            'category': rule.category,
            'tags': rule.tags,
            'paused': rule.paused
        }

        async def try_download(link: str, is_fallback: bool = False) -> Tuple[bool, Optional[str], str]:
            """尝试下载并推送到客户端，返回 (是否成功, InfoHash, 错误信息)"""
            nonlocal info_hash
            
            prefix = "[备用链接] " if is_fallback else ""
            
            pre_hashes = set()
            try:
                pre_torrents = client.get_torrents(filter='all')
                pre_hashes = {t['hash'] for t in pre_torrents}
            except: pass

            display_type = "磁力链" if link.startswith('magnet:') else "种子文件"
            
            if link.startswith('magnet:'):
                success, msg = client.add_torrent(link, is_file=False, **kwargs)
                if not success:
                    await NotificationManager.push_client_push_error(title, client.name, msg)
                    return False, None, msg
            else:
                success, content, error_msg = await Matcher._download_torrent_file(link, title, guid)
                if not success:
                    await NotificationManager.push_torrent_download_error(title, link, error_msg, is_fallback)
                    return False, None, error_msg
                
                success, msg = client.add_torrent(content, is_file=True, **kwargs)
                if not success:
                    await NotificationManager.push_client_push_error(title, client.name, msg)
                    return False, None, msg
            
            if success:
                if not info_hash:
                    try:
                        for _ in range(5):
                            await asyncio.sleep(2.0)
                            post_torrents = client.get_torrents(filter='all')
                            post_hashes = {t['hash'] for t in post_torrents}
                            new_hashes = post_hashes - pre_hashes
                            if new_hashes:
                                info_hash = list(new_hashes)[0]
                                break
                    except: pass

                logger.info(f"✅ {prefix}推送成功: {title} ({display_type}) -> {client.name} (Hash: {info_hash})")
                log_audit("RSS", "推送成功", f"{prefix}已推送 {display_type}: {title} 到 {client.name}", details=f"规则: {rule.name}")
                return True, info_hash, ""
            else:
                logger.error(f"❌ {prefix}推送失败: {title} -> {msg}")
                return False, None, msg or "未知错误"

        try:
            success, result_hash, error_msg = await try_download(download_link)
            if success:
                return True, result_hash, ""
            
            last_error = error_msg
            if fallback_link and fallback_link != download_link:
                logger.info(f"🔄 主链接失败，尝试备用链接: {fallback_link}")
                log_audit("RSS", "重试备用链接", f"主链接失败，尝试备用链接: {title}", details=fallback_link)
                success, result_hash, error_msg = await try_download(fallback_link, is_fallback=True)
                if success:
                    return True, result_hash, ""
                last_error = error_msg
            
            log_audit("RSS", "推送失败", f"主链接和备用链接均失败", level="ERROR", details=title)
            return False, None, last_error or "主链接和备用链接均失败"
                
        except Exception as e:
            logger.error(f"推送任务异常: {e}")
            log_audit("RSS", "推送异常", f"执行过程发生程序异常", level="ERROR", details=f"Title: {title}\nError: {str(e)}")
            await NotificationManager.push_client_error_notification(download_link, client.name, str(e))
            return False, None, str(e)
