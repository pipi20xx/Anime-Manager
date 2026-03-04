import anitopy
import traceback
import sys
from typing import Dict, Any

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
            return {}
