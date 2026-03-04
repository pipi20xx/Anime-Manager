import httpx
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
from config_manager import ConfigManager
import logging

logger = logging.getLogger("JackettClient")

class JackettClient:
    @staticmethod
    def _get_headers(base_url: str):
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'X-Requested-With': 'XMLHttpRequest',
            'Origin': base_url
        }

    @staticmethod
    async def _try_login(client: httpx.AsyncClient, base_url: str, password: str) -> bool:
        """
        Match logic from jackeet api 控制.py: Login via /UI/Dashboard
        """
        if not password:
            return False
        
        # Strip /api/... from URL to get base UI path
        ui_base = base_url.split('/api')[0]
        login_url = f"{ui_base}/UI/Dashboard"
        
        try:
            resp = await client.post(login_url, data={"password": password}, timeout=10)
            if "Jackett" in client.cookies:
                return True
        except Exception as e:
            logger.error(f"Jackett login exception: {e}")
        return False

    @staticmethod
    async def get_indexers() -> List[Dict[str, str]]:
        """
        Fetch only CONFIGURED indexers from Jackett using JSON API.
        """
        config = ConfigManager.get_config()
        base_url = config.get("jackett_url", "").rstrip("/")
        api_key = config.get("jackett_api_key", "")
        password = config.get("jackett_password", "")
        
        if not base_url or not api_key:
            return []

        url = f"{base_url}/api/v2.0/indexers"
        params = {"apikey": api_key}
        headers = JackettClient._get_headers(base_url)
        
        proxy = ConfigManager.get_proxy("jackett")
        async with httpx.AsyncClient(timeout=10, proxy=proxy, follow_redirects=True, headers=headers) as client:
            try:
                async def do_request():
                    return await client.get(url, params=params)

                resp = await do_request()
                
                # Check for 401 or HTML response (redirection to login)
                if resp.status_code == 401 or (resp.status_code == 200 and "<html" in resp.text[:100].lower()):
                    if await JackettClient._try_login(client, base_url, password):
                        resp = await do_request()

                if resp.status_code == 200 and "application/json" in resp.headers.get("content-type", ""):
                    data = resp.json()
                    return [
                        {"id": item.get("id"), "name": item.get("name")}
                        for item in data 
                        if item.get("configured") is True
                    ]
            except Exception as e:
                logger.error(f"Failed to fetch Jackett indexers: {e}")
        return []

    @staticmethod
    async def search(keyword: str, indexer: str = "all") -> List[Dict[str, str]]:
        """
        Search Jackett using Torznab API (RSS XML).
        """
        config = ConfigManager.get_config()
        base_url = config.get("jackett_url", "").rstrip("/")
        api_key = config.get("jackett_api_key", "")
        password = config.get("jackett_password", "")
        
        if not base_url or not api_key:
            return []

        target = indexer if indexer else "all"
        url = f"{base_url}/api/v2.0/indexers/{target}/results/torznab/api"
        params = {"apikey": api_key, "t": "search", "q": keyword}
        headers = JackettClient._get_headers(base_url)

        proxy = ConfigManager.get_proxy("jackett")
        async with httpx.AsyncClient(timeout=30, proxy=proxy, follow_redirects=True, headers=headers) as client:
            try:
                async def do_request():
                    return await client.get(url, params=params)

                resp = await do_request()
                
                if resp.status_code == 401 or (resp.status_code == 200 and "<html" in resp.text[:100].lower()):
                    if await JackettClient._try_login(client, base_url, password):
                        resp = await do_request()

                if resp.status_code == 200:
                    return JackettClient._parse_rss(resp.text)
            except Exception as e:
                logger.error(f"Jackett search error: {e}")
        return []

    @staticmethod
    def _parse_rss(xml_content: str) -> List[Dict[str, str]]:
        results = []
        try:
            root = ET.fromstring(xml_content)
            for item in root.findall(".//item"):
                title = item.findtext("title")
                # Torznab link is usually in <link> or <enclosure url="...">
                link = item.findtext("link")
                enclosure = item.find("enclosure")
                if enclosure is not None:
                    link = enclosure.get("url")
                
                guid = item.findtext("guid")
                size = item.findtext("size") or "0"
                description = item.findtext("description")
                indexer = item.findtext("jackettindexer") or item.findtext("author")
                
                if title and link:
                    results.append({
                        "title": title,
                        "link": link,
                        "guid": guid or link,
                        "size": size,
                        "description": description,
                        "indexer": indexer
                    })
        except Exception as e:
            logger.error(f"Failed to parse Jackett XML: {e}")
        return results
