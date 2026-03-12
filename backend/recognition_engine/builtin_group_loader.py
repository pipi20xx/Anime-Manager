import os
from typing import Set
import logging

logger = logging.getLogger(__name__)

class BuiltinGroupLoader:
    """内置制作组加载器"""
    
    _instance = None
    _builtin_groups: Set[str] = set()
    _loaded = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def load(cls) -> None:
        """加载内置制作组"""
        if cls._loaded:
            return
        
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            txt_path = os.path.join(current_dir, "builtin_groups.txt")
            
            with open(txt_path, 'r', encoding='utf-8') as f:
                groups = [line.strip() for line in f if line.strip()]
            
            cls._builtin_groups = set(groups)
            cls._loaded = True
            logger.info(f"已加载 {len(cls._builtin_groups)} 个内置制作组")
            
        except FileNotFoundError:
            logger.warning(f"内置制作组文件不存在: {txt_path}")
            cls._loaded = True
        except Exception as e:
            logger.error(f"加载内置制作组失败: {e}")
            cls._loaded = True
    
    @classmethod
    def get_builtin_groups(cls) -> Set[str]:
        """获取所有内置制作组"""
        if not cls._loaded:
            cls.load()
        return cls._builtin_groups
    
    @classmethod
    def is_builtin_group(cls, name: str) -> bool:
        """检查是否是内置制作组"""
        if not cls._loaded:
            cls.load()
        return name in cls._builtin_groups
    
    @classmethod
    def reload(cls) -> None:
        """重新加载内置制作组"""
        cls._loaded = False
        cls.load()
