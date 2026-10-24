import anitopy
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class AnitopyWrapper:
    @staticmethod
    def parse(filename: str, options: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Pure wrapper around Anitopy with crash protection.
        """
        try:
            if options is None:
                options = {
                    "allow_extended_episode_numbering": True,
                    "parse_release_group": False,
                    "parse_file_extension": False,
                    "parse_episode_title": True
                }
            return anitopy.parse(filename, options=options)
        except Exception:
            # If anitopy crashes, return empty dict to let fallback logic handle it
            # [Fix] 崩溃必须留痕, 否则会被伪装成"解析成功但无结果"
            logger.exception("Anitopy 内核解析崩溃: %s", filename)
            return {}
