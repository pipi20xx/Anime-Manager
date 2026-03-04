import os
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, text, select
from database import get_engine as get_global_engine

_async_session = None

KEYWORDS_JSON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "keywords.json")

def _load_keyword_mappings():
    try:
        if os.path.exists(KEYWORDS_JSON_PATH):
            with open(KEYWORDS_JSON_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return []

DEFAULT_GENRE_MAPPINGS = [
    {"id": 28, "name_zh": "动作", "name_en": "Action"},
    {"id": 12, "name_zh": "冒险", "name_en": "Adventure"},
    {"id": 16, "name_zh": "动画", "name_en": "Animation"},
    {"id": 35, "name_zh": "喜剧", "name_en": "Comedy"},
    {"id": 80, "name_zh": "犯罪", "name_en": "Crime"},
    {"id": 99, "name_zh": "纪录", "name_en": "Documentary"},
    {"id": 18, "name_zh": "剧情", "name_en": "Drama"},
    {"id": 10751, "name_zh": "家庭", "name_en": "Family"},
    {"id": 14, "name_zh": "奇幻", "name_en": "Fantasy"},
    {"id": 36, "name_zh": "历史", "name_en": "History"},
    {"id": 27, "name_zh": "恐怖", "name_en": "Horror"},
    {"id": 10402, "name_zh": "音乐", "name_en": "Music"},
    {"id": 9648, "name_zh": "悬疑", "name_en": "Mystery"},
    {"id": 10749, "name_zh": "爱情", "name_en": "Romance"},
    {"id": 878, "name_zh": "科幻", "name_en": "Science Fiction"},
    {"id": 10770, "name_zh": "电视电影", "name_en": "TV Movie"},
    {"id": 53, "name_zh": "惊悚", "name_en": "Thriller"},
    {"id": 10752, "name_zh": "战争", "name_en": "War"},
    {"id": 37, "name_zh": "西部", "name_en": "Western"},
    {"id": 10765, "name_zh": "科幻奇幻", "name_en": "Sci-Fi & Fantasy"},
    {"id": 10768, "name_zh": "战争政治", "name_en": "War & Politics"},
    {"id": 10759, "name_zh": "动作冒险", "name_en": "Action & Adventure"},
    {"id": 10762, "name_zh": "儿童", "name_en": "Kids"},
    {"id": 10764, "name_zh": "真人秀", "name_en": "Reality"},
    {"id": 10767, "name_zh": "脱口秀", "name_en": "Talk"},
    {"id": 10766, "name_zh": "肥皂剧", "name_en": "Soap"},
]

DEFAULT_LANGUAGE_MAPPINGS = [
    {"code": "af", "name_zh": "南非语", "name_en": "Afrikaans"},
    {"code": "ar", "name_zh": "阿拉伯语", "name_en": "Arabic"},
    {"code": "az", "name_zh": "阿塞拜疆语", "name_en": "Azerbaijani"},
    {"code": "be", "name_zh": "比利时语", "name_en": "Belarusian"},
    {"code": "bg", "name_zh": "保加利亚语", "name_en": "Bulgarian"},
    {"code": "ca", "name_zh": "加泰隆语", "name_en": "Catalan"},
    {"code": "cs", "name_zh": "捷克语", "name_en": "Czech"},
    {"code": "cy", "name_zh": "威尔士语", "name_en": "Welsh"},
    {"code": "da", "name_zh": "丹麦语", "name_en": "Danish"},
    {"code": "de", "name_zh": "德语", "name_en": "German"},
    {"code": "dv", "name_zh": "第维埃语", "name_en": "Dhivehi"},
    {"code": "el", "name_zh": "希腊语", "name_en": "Greek"},
    {"code": "en", "name_zh": "英语", "name_en": "English"},
    {"code": "eo", "name_zh": "世界语", "name_en": "Esperanto"},
    {"code": "es", "name_zh": "西班牙语", "name_en": "Spanish"},
    {"code": "et", "name_zh": "爱沙尼亚语", "name_en": "Estonian"},
    {"code": "eu", "name_zh": "巴士克语", "name_en": "Basque"},
    {"code": "fa", "name_zh": "法斯语", "name_en": "Persian"},
    {"code": "fi", "name_zh": "芬兰语", "name_en": "Finnish"},
    {"code": "fo", "name_zh": "法罗语", "name_en": "Faroese"},
    {"code": "fr", "name_zh": "法语", "name_en": "French"},
    {"code": "gl", "name_zh": "加里西亚语", "name_en": "Galician"},
    {"code": "gu", "name_zh": "古吉拉特语", "name_en": "Gujarati"},
    {"code": "he", "name_zh": "希伯来语", "name_en": "Hebrew"},
    {"code": "hi", "name_zh": "印地语", "name_en": "Hindi"},
    {"code": "hr", "name_zh": "克罗地亚语", "name_en": "Croatian"},
    {"code": "hu", "name_zh": "匈牙利语", "name_en": "Hungarian"},
    {"code": "hy", "name_zh": "亚美尼亚语", "name_en": "Armenian"},
    {"code": "id", "name_zh": "印度尼西亚语", "name_en": "Indonesian"},
    {"code": "is", "name_zh": "冰岛语", "name_en": "Icelandic"},
    {"code": "it", "name_zh": "意大利语", "name_en": "Italian"},
    {"code": "ja", "name_zh": "日语", "name_en": "Japanese"},
    {"code": "ka", "name_zh": "格鲁吉亚语", "name_en": "Georgian"},
    {"code": "kk", "name_zh": "哈萨克语", "name_en": "Kazakh"},
    {"code": "kn", "name_zh": "卡纳拉语", "name_en": "Kannada"},
    {"code": "ko", "name_zh": "朝鲜语", "name_en": "Korean"},
    {"code": "kok", "name_zh": "孔卡尼语", "name_en": "Konkani"},
    {"code": "ky", "name_zh": "吉尔吉斯语", "name_en": "Kyrgyz"},
    {"code": "lt", "name_zh": "立陶宛语", "name_en": "Lithuanian"},
    {"code": "lv", "name_zh": "拉脱维亚语", "name_en": "Latvian"},
    {"code": "mi", "name_zh": "毛利语", "name_en": "Maori"},
    {"code": "mk", "name_zh": "马其顿语", "name_en": "Macedonian"},
    {"code": "mn", "name_zh": "蒙古语", "name_en": "Mongolian"},
    {"code": "mr", "name_zh": "马拉地语", "name_en": "Marathi"},
    {"code": "ms", "name_zh": "马来语", "name_en": "Malay"},
    {"code": "mt", "name_zh": "马耳他语", "name_en": "Maltese"},
    {"code": "nb", "name_zh": "挪威语", "name_en": "Norwegian Bokmål"},
    {"code": "nl", "name_zh": "荷兰语", "name_en": "Dutch"},
    {"code": "ns", "name_zh": "北梭托语", "name_en": "Northern Sotho"},
    {"code": "pa", "name_zh": "旁遮普语", "name_en": "Punjabi"},
    {"code": "pl", "name_zh": "波兰语", "name_en": "Polish"},
    {"code": "pt", "name_zh": "葡萄牙语", "name_en": "Portuguese"},
    {"code": "qu", "name_zh": "克丘亚语", "name_en": "Quechua"},
    {"code": "ro", "name_zh": "罗马尼亚语", "name_en": "Romanian"},
    {"code": "ru", "name_zh": "俄语", "name_en": "Russian"},
    {"code": "sa", "name_zh": "梵文", "name_en": "Sanskrit"},
    {"code": "se", "name_zh": "北萨摩斯语", "name_en": "Northern Sami"},
    {"code": "sk", "name_zh": "斯洛伐克语", "name_en": "Slovak"},
    {"code": "sl", "name_zh": "斯洛文尼亚语", "name_en": "Slovenian"},
    {"code": "sq", "name_zh": "阿尔巴尼亚语", "name_en": "Albanian"},
    {"code": "sv", "name_zh": "瑞典语", "name_en": "Swedish"},
    {"code": "sw", "name_zh": "斯瓦希里语", "name_en": "Swahili"},
    {"code": "syr", "name_zh": "叙利亚语", "name_en": "Syriac"},
    {"code": "ta", "name_zh": "泰米尔语", "name_en": "Tamil"},
    {"code": "te", "name_zh": "泰卢固语", "name_en": "Telugu"},
    {"code": "th", "name_zh": "泰语", "name_en": "Thai"},
    {"code": "tl", "name_zh": "塔加路语", "name_en": "Tagalog"},
    {"code": "tn", "name_zh": "茨瓦纳语", "name_en": "Tswana"},
    {"code": "tr", "name_zh": "土耳其语", "name_en": "Turkish"},
    {"code": "ts", "name_zh": "宗加语", "name_en": "Tsonga"},
    {"code": "tt", "name_zh": "鞑靼语", "name_en": "Tatar"},
    {"code": "uk", "name_zh": "乌克兰语", "name_en": "Ukrainian"},
    {"code": "ur", "name_zh": "乌都语", "name_en": "Urdu"},
    {"code": "uz", "name_zh": "乌兹别克语", "name_en": "Uzbek"},
    {"code": "vi", "name_zh": "越南语", "name_en": "Vietnamese"},
    {"code": "xh", "name_zh": "班图语", "name_en": "Xhosa"},
    {"code": "zh", "name_zh": "中文", "name_en": "Chinese"},
    {"code": "cn", "name_zh": "中文", "name_en": "Chinese"},
    {"code": "zu", "name_zh": "祖鲁语", "name_en": "Zulu"},
]

DEFAULT_COUNTRY_MAPPINGS = [
    {"code": "AR", "name_zh": "阿根廷", "name_en": "Argentina"},
    {"code": "AU", "name_zh": "澳大利亚", "name_en": "Australia"},
    {"code": "BE", "name_zh": "比利时", "name_en": "Belgium"},
    {"code": "BR", "name_zh": "巴西", "name_en": "Brazil"},
    {"code": "CA", "name_zh": "加拿大", "name_en": "Canada"},
    {"code": "CH", "name_zh": "瑞士", "name_en": "Switzerland"},
    {"code": "CL", "name_zh": "智利", "name_en": "Chile"},
    {"code": "CO", "name_zh": "哥伦比亚", "name_en": "Colombia"},
    {"code": "CZ", "name_zh": "捷克", "name_en": "Czech Republic"},
    {"code": "DE", "name_zh": "德国", "name_en": "Germany"},
    {"code": "DK", "name_zh": "丹麦", "name_en": "Denmark"},
    {"code": "EG", "name_zh": "埃及", "name_en": "Egypt"},
    {"code": "ES", "name_zh": "西班牙", "name_en": "Spain"},
    {"code": "FR", "name_zh": "法国", "name_en": "France"},
    {"code": "GB", "name_zh": "英国", "name_en": "United Kingdom"},
    {"code": "GR", "name_zh": "希腊", "name_en": "Greece"},
    {"code": "HK", "name_zh": "中国香港", "name_en": "Hong Kong"},
    {"code": "IL", "name_zh": "以色列", "name_en": "Israel"},
    {"code": "IN", "name_zh": "印度", "name_en": "India"},
    {"code": "IQ", "name_zh": "伊拉克", "name_en": "Iraq"},
    {"code": "IR", "name_zh": "伊朗", "name_en": "Iran"},
    {"code": "IT", "name_zh": "意大利", "name_en": "Italy"},
    {"code": "JP", "name_zh": "日本", "name_en": "Japan"},
    {"code": "KP", "name_zh": "朝鲜", "name_en": "North Korea"},
    {"code": "KR", "name_zh": "韩国", "name_en": "South Korea"},
    {"code": "LA", "name_zh": "老挝", "name_en": "Laos"},
    {"code": "MM", "name_zh": "缅甸", "name_en": "Myanmar"},
    {"code": "MN", "name_zh": "蒙古", "name_en": "Mongolia"},
    {"code": "MO", "name_zh": "澳门", "name_en": "Macau"},
    {"code": "MX", "name_zh": "墨西哥", "name_en": "Mexico"},
    {"code": "MY", "name_zh": "马来西亚", "name_en": "Malaysia"},
    {"code": "NL", "name_zh": "荷兰", "name_en": "Netherlands"},
    {"code": "NO", "name_zh": "挪威", "name_en": "Norway"},
    {"code": "NZ", "name_zh": "新西兰", "name_en": "New Zealand"},
    {"code": "PH", "name_zh": "菲律宾", "name_en": "Philippines"},
    {"code": "PK", "name_zh": "巴基斯坦", "name_en": "Pakistan"},
    {"code": "PL", "name_zh": "波兰", "name_en": "Poland"},
    {"code": "PT", "name_zh": "葡萄牙", "name_en": "Portugal"},
    {"code": "RU", "name_zh": "俄罗斯", "name_en": "Russia"},
    {"code": "SA", "name_zh": "沙特阿拉伯", "name_en": "Saudi Arabia"},
    {"code": "SE", "name_zh": "瑞典", "name_en": "Sweden"},
    {"code": "SG", "name_zh": "新加坡", "name_en": "Singapore"},
    {"code": "TH", "name_zh": "泰国", "name_en": "Thailand"},
    {"code": "TR", "name_zh": "土耳其", "name_en": "Turkey"},
    {"code": "TW", "name_zh": "中国台湾", "name_en": "Taiwan"},
    {"code": "US", "name_zh": "美国", "name_en": "United States"},
    {"code": "VN", "name_zh": "越南", "name_en": "Vietnam"},
    {"code": "CN", "name_zh": "中国", "name_en": "China"},
]

def get_engine():
    return get_global_engine()

def get_session_maker():
    global _async_session
    if _async_session is None:
        engine = get_engine()
        _async_session = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
    return _async_session

class TmdbFullDB:
    @staticmethod
    async def init_db():
        """初始化，只创建该模块定义的表"""
        engine = get_engine()
        
        async with engine.begin() as conn:
            await conn.execute(text("CREATE SCHEMA IF NOT EXISTS metadata;"))

            from .models import TmdbDeepMeta, MediaTitleIndex, RefGenre, RefCompany, RefKeyword, UserGenreMapping, UserCompanyMapping, UserKeywordMapping, UserLanguageMapping, UserCountryMapping
            
            target_tables = [
                TmdbDeepMeta.__table__,
                MediaTitleIndex.__table__,
                RefGenre.__table__,
                RefCompany.__table__,
                RefKeyword.__table__,
                UserGenreMapping.__table__,
                UserCompanyMapping.__table__,
                UserKeywordMapping.__table__,
                UserLanguageMapping.__table__,
                UserCountryMapping.__table__
            ]
            
            def create_tables(sync_conn):
                for table in target_tables:
                    table.create(sync_conn, checkfirst=True)
            
            await conn.run_sync(create_tables)

        await TmdbFullDB._init_default_mappings()

    @staticmethod
    async def _init_default_mappings():
        """初始化默认映射数据（仅当表为空时）"""
        from .models import UserCountryMapping, UserLanguageMapping, UserGenreMapping, UserKeywordMapping
        
        async with await TmdbFullDB.get_session() as session:
            existing_genres = await session.execute(select(UserGenreMapping))
            if len(existing_genres.scalars().all()) == 0:
                for item in DEFAULT_GENRE_MAPPINGS:
                    session.add(UserGenreMapping(**item))
                await session.commit()
            
            existing_countries = await session.execute(select(UserCountryMapping))
            if len(existing_countries.scalars().all()) == 0:
                for item in DEFAULT_COUNTRY_MAPPINGS:
                    session.add(UserCountryMapping(**item))
                await session.commit()
            
            existing_languages = await session.execute(select(UserLanguageMapping))
            if len(existing_languages.scalars().all()) == 0:
                for item in DEFAULT_LANGUAGE_MAPPINGS:
                    session.add(UserLanguageMapping(**item))
                await session.commit()
            
            existing_keywords = await session.execute(select(UserKeywordMapping))
            if len(existing_keywords.scalars().all()) == 0:
                keyword_mappings = _load_keyword_mappings()
                for item in keyword_mappings:
                    session.add(UserKeywordMapping(**item))
                await session.commit()

    @staticmethod
    async def get_session() -> AsyncSession:
        """获取异步 Session"""
        maker = get_session_maker()
        return maker()

    @staticmethod
    async def save(obj: SQLModel):
        """通用保存方法"""
        maker = get_session_maker()
        async with maker() as session:
            session.add(obj)
            await session.commit()
            await session.refresh(obj)
            return obj
