from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any, Optional
from fastapi.responses import JSONResponse
from sqlmodel import select, or_, col, String
from datetime import datetime
from pydantic import BaseModel

from database import db
from tmdbmatefull.models import RefGenre, RefCompany, RefKeyword, UserGenreMapping, UserCompanyMapping, UserKeywordMapping, UserLanguageMapping, UserCountryMapping
from tmdbmatefull.database import TmdbFullDB
from recognition.renderer import refresh_mapping_cache

router = APIRouter(prefix="/api/user_mapping", tags=["用户自定义映射"])

class MappingItem(BaseModel):
    id: int
    name_zh: Optional[str] = ""
    name_en: Optional[str] = ""
    name: Optional[str] = ""
    country: Optional[str] = ""

class CodeMappingItem(BaseModel):
    code: str
    name_zh: Optional[str] = ""
    name_en: Optional[str] = ""

@router.get("/genres", summary="获取用户流派映射")
async def get_genre_mappings(q: str = ""):
    async with await TmdbFullDB.get_session() as session:
        base_query = select(UserGenreMapping)
        if q:
            base_query = base_query.where(
                (UserGenreMapping.name_zh.ilike(f"%{q}%")) |
                (UserGenreMapping.name_en.ilike(f"%{q}%")) |
                (UserGenreMapping.id.cast(String).ilike(f"%{q}%"))
            )
        result = await session.execute(base_query)
        return result.scalars().all()

@router.post("/genres", summary="保存流派映射")
async def save_genre_mapping(item: MappingItem):
    async with await TmdbFullDB.get_session() as session:
        existing = await session.get(UserGenreMapping, item.id)
        if existing:
            existing.name_zh = item.name_zh or ""
            existing.name_en = item.name_en or ""
            existing.updated_at = datetime.now()
        else:
            existing = UserGenreMapping(
                id=item.id,
                name_zh=item.name_zh or "",
                name_en=item.name_en or ""
            )
            session.add(existing)
        await session.commit()
    await refresh_mapping_cache()
    return {"status": "success"}

@router.delete("/genres/{item_id}", summary="删除流派映射")
async def delete_genre_mapping(item_id: int):
    async with await TmdbFullDB.get_session() as session:
        existing = await session.get(UserGenreMapping, item_id)
        if existing:
            await session.delete(existing)
            await session.commit()
    await refresh_mapping_cache()
    return {"status": "success"}

@router.get("/companies", summary="获取用户公司映射")
async def get_company_mappings(page: int = 1, page_size: int = 100, q: str = ""):
    async with await TmdbFullDB.get_session() as session:
        offset = (page - 1) * page_size
        base_query = select(UserCompanyMapping)
        if q:
            base_query = base_query.where(
                (UserCompanyMapping.name.ilike(f"%{q}%")) |
                (UserCompanyMapping.id.cast(String).ilike(f"%{q}%")) |
                (UserCompanyMapping.country.ilike(f"%{q}%"))
            )
        result = await session.execute(base_query.offset(offset).limit(page_size))
        count_result = await session.execute(base_query)
        total = len(count_result.scalars().all())
        return {"items": result.scalars().all(), "total": total, "page": page, "page_size": page_size}

@router.post("/companies", summary="保存公司映射")
async def save_company_mapping(item: MappingItem):
    async with await TmdbFullDB.get_session() as session:
        existing = await session.get(UserCompanyMapping, item.id)
        if existing:
            existing.name = item.name or ""
            existing.country = item.country or ""
            existing.updated_at = datetime.now()
        else:
            existing = UserCompanyMapping(
                id=item.id,
                name=item.name or "",
                country=item.country or ""
            )
            session.add(existing)
        await session.commit()
        return {"status": "success"}

@router.delete("/companies/{item_id}", summary="删除公司映射")
async def delete_company_mapping(item_id: int):
    async with await TmdbFullDB.get_session() as session:
        existing = await session.get(UserCompanyMapping, item_id)
        if existing:
            await session.delete(existing)
            await session.commit()
        return {"status": "success"}

@router.get("/keywords", summary="获取用户关键词映射")
async def get_keyword_mappings(page: int = 1, page_size: int = 100, q: str = ""):
    async with await TmdbFullDB.get_session() as session:
        offset = (page - 1) * page_size
        base_query = select(UserKeywordMapping)
        if q:
            base_query = base_query.where(
                (UserKeywordMapping.name_zh.ilike(f"%{q}%")) |
                (UserKeywordMapping.name_en.ilike(f"%{q}%")) |
                (UserKeywordMapping.id.cast(String).ilike(f"%{q}%"))
            )
        result = await session.execute(base_query.offset(offset).limit(page_size))
        count_result = await session.execute(base_query)
        total = len(count_result.scalars().all())
        return {"items": result.scalars().all(), "total": total, "page": page, "page_size": page_size}

@router.post("/keywords", summary="保存关键词映射")
async def save_keyword_mapping(item: MappingItem):
    async with await TmdbFullDB.get_session() as session:
        existing = await session.get(UserKeywordMapping, item.id)
        if existing:
            existing.name_zh = item.name_zh or ""
            existing.name_en = item.name_en or ""
            existing.updated_at = datetime.now()
        else:
            existing = UserKeywordMapping(
                id=item.id,
                name_zh=item.name_zh or "",
                name_en=item.name_en or ""
            )
            session.add(existing)
        await session.commit()
        return {"status": "success"}

@router.delete("/keywords/{item_id}", summary="删除关键词映射")
async def delete_keyword_mapping(item_id: int):
    async with await TmdbFullDB.get_session() as session:
        existing = await session.get(UserKeywordMapping, item_id)
        if existing:
            await session.delete(existing)
            await session.commit()
        return {"status": "success"}

@router.get("/languages", summary="获取用户语言映射")
async def get_language_mappings(q: str = ""):
    async with await TmdbFullDB.get_session() as session:
        base_query = select(UserLanguageMapping)
        if q:
            base_query = base_query.where(
                (UserLanguageMapping.name_zh.ilike(f"%{q}%")) |
                (UserLanguageMapping.name_en.ilike(f"%{q}%")) |
                (UserLanguageMapping.code.ilike(f"%{q}%"))
            )
        result = await session.execute(base_query)
        return result.scalars().all()

@router.post("/languages", summary="保存语言映射")
async def save_language_mapping(item: CodeMappingItem):
    async with await TmdbFullDB.get_session() as session:
        existing = await session.get(UserLanguageMapping, item.code)
        if existing:
            existing.name_zh = item.name_zh or ""
            existing.name_en = item.name_en or ""
            existing.updated_at = datetime.now()
        else:
            existing = UserLanguageMapping(
                code=item.code,
                name_zh=item.name_zh or "",
                name_en=item.name_en or ""
            )
            session.add(existing)
        await session.commit()
    await refresh_mapping_cache()
    return {"status": "success"}

@router.delete("/languages/{code}", summary="删除语言映射")
async def delete_language_mapping(code: str):
    async with await TmdbFullDB.get_session() as session:
        existing = await session.get(UserLanguageMapping, code)
        if existing:
            await session.delete(existing)
            await session.commit()
    await refresh_mapping_cache()
    return {"status": "success"}

@router.get("/countries", summary="获取用户国家映射")
async def get_country_mappings(q: str = ""):
    async with await TmdbFullDB.get_session() as session:
        base_query = select(UserCountryMapping)
        if q:
            base_query = base_query.where(
                (UserCountryMapping.name_zh.ilike(f"%{q}%")) |
                (UserCountryMapping.name_en.ilike(f"%{q}%")) |
                (UserCountryMapping.code.ilike(f"%{q}%"))
            )
        result = await session.execute(base_query)
        return result.scalars().all()

@router.post("/countries", summary="保存国家映射")
async def save_country_mapping(item: CodeMappingItem):
    async with await TmdbFullDB.get_session() as session:
        existing = await session.get(UserCountryMapping, item.code)
        if existing:
            existing.name_zh = item.name_zh or ""
            existing.name_en = item.name_en or ""
            existing.updated_at = datetime.now()
        else:
            existing = UserCountryMapping(
                code=item.code,
                name_zh=item.name_zh or "",
                name_en=item.name_en or ""
            )
            session.add(existing)
        await session.commit()
    await refresh_mapping_cache()
    return {"status": "success"}

@router.delete("/countries/{code}", summary="删除国家映射")
async def delete_country_mapping(code: str):
    async with await TmdbFullDB.get_session() as session:
        existing = await session.get(UserCountryMapping, code)
        if existing:
            await session.delete(existing)
            await session.commit()
    await refresh_mapping_cache()
    return {"status": "success"}

@router.get("/search", summary="搜索映射 (优先用户自定义)")
async def search_mapping(q: str = "", type: str = "all"):
    results = []
    is_id_search = q.isdigit()
    async with await TmdbFullDB.get_session() as session:
        if type in ["all", "genre"]:
            if q:
                if is_id_search:
                    user_genres = await session.execute(
                        select(UserGenreMapping).where(col(UserGenreMapping.id).cast(String).contains(q))
                    )
                else:
                    user_genres = await session.execute(
                        select(UserGenreMapping).where(
                            or_(col(UserGenreMapping.name_zh).contains(q), col(UserGenreMapping.name_en).contains(q))
                        )
                    )
            else:
                user_genres = await session.execute(select(UserGenreMapping))
            for item in user_genres.scalars().all():
                results.append({
                    "id": str(item.id),
                    "name": item.name_zh or item.name_en,
                    "type": "流派",
                    "source": "用户自定义"
                })
            if q:
                if is_id_search:
                    ref_genres = await session.execute(
                        select(RefGenre).where(col(RefGenre.id).cast(String).contains(q))
                    )
                else:
                    ref_genres = await session.execute(
                        select(RefGenre).where(
                            or_(col(RefGenre.name_zh).contains(q), col(RefGenre.name_en).contains(q))
                        )
                    )
            else:
                ref_genres = await session.execute(select(RefGenre))
            existing_ids = {r["id"] for r in results if r["type"] == "流派"}
            for item in ref_genres.scalars().all():
                if str(item.id) not in existing_ids:
                    results.append({
                        "id": str(item.id),
                        "name": item.name_zh or item.name_en,
                        "type": "流派",
                        "source": "TMDB"
                    })

        if type in ["all", "company"]:
            if q:
                if is_id_search:
                    user_companies = await session.execute(
                        select(UserCompanyMapping).where(col(UserCompanyMapping.id).cast(String).contains(q))
                    )
                else:
                    user_companies = await session.execute(
                        select(UserCompanyMapping).where(col(UserCompanyMapping.name).contains(q))
                    )
            else:
                user_companies = await session.execute(select(UserCompanyMapping))
            for item in user_companies.scalars().all():
                results.append({
                    "id": str(item.id),
                    "name": item.name,
                    "type": "公司",
                    "source": "用户自定义"
                })
            if q:
                if is_id_search:
                    ref_companies = await session.execute(
                        select(RefCompany).where(col(RefCompany.id).cast(String).contains(q))
                    )
                else:
                    ref_companies = await session.execute(
                        select(RefCompany).where(col(RefCompany.name).contains(q))
                    )
            else:
                ref_companies = await session.execute(select(RefCompany))
            existing_ids = {r["id"] for r in results if r["type"] == "公司"}
            for item in ref_companies.scalars().all():
                if str(item.id) not in existing_ids:
                    results.append({
                        "id": str(item.id),
                        "name": item.name,
                        "type": "公司",
                        "source": "TMDB"
                    })

        if type in ["all", "keyword"]:
            if q:
                if is_id_search:
                    user_keywords = await session.execute(
                        select(UserKeywordMapping).where(col(UserKeywordMapping.id).cast(String).contains(q))
                    )
                else:
                    user_keywords = await session.execute(
                        select(UserKeywordMapping).where(
                            or_(col(UserKeywordMapping.name_zh).contains(q), col(UserKeywordMapping.name_en).contains(q))
                        )
                    )
            else:
                user_keywords = await session.execute(select(UserKeywordMapping))
            for item in user_keywords.scalars().all():
                results.append({
                    "id": str(item.id),
                    "name": item.name_zh or item.name_en,
                    "type": "关键词",
                    "source": "用户自定义"
                })
            if q:
                if is_id_search:
                    ref_keywords = await session.execute(
                        select(RefKeyword).where(col(RefKeyword.id).cast(String).contains(q))
                    )
                else:
                    ref_keywords = await session.execute(
                        select(RefKeyword).where(col(RefKeyword.name_en).contains(q))
                    )
            else:
                ref_keywords = await session.execute(select(RefKeyword))
            existing_ids = {r["id"] for r in results if r["type"] == "关键词"}
            for item in ref_keywords.scalars().all():
                if str(item.id) not in existing_ids:
                    results.append({
                        "id": str(item.id),
                        "name": item.name_en,
                        "type": "关键词",
                        "source": "TMDB"
                    })

        if type in ["all", "language"]:
            if q:
                user_languages = await session.execute(
                    select(UserLanguageMapping).where(
                        or_(col(UserLanguageMapping.name_zh).contains(q), col(UserLanguageMapping.name_en).contains(q), col(UserLanguageMapping.code).contains(q))
                    )
                )
            else:
                user_languages = await session.execute(select(UserLanguageMapping))
            for item in user_languages.scalars().all():
                results.append({
                    "id": item.code,
                    "name": f"{item.name_zh or item.name_en or item.code}",
                    "type": "语言",
                    "source": "用户自定义"
                })

        if type in ["all", "country"]:
            if q:
                user_countries = await session.execute(
                    select(UserCountryMapping).where(
                        or_(col(UserCountryMapping.name_zh).contains(q), col(UserCountryMapping.name_en).contains(q), col(UserCountryMapping.code).contains(q))
                    )
                )
            else:
                user_countries = await session.execute(select(UserCountryMapping))
            for item in user_countries.scalars().all():
                results.append({
                    "id": item.code,
                    "name": f"{item.name_zh or item.name_en or item.code}",
                    "type": "国家",
                    "source": "用户自定义"
                })

    return results

@router.post("/import_from_ref", summary="从 TMDB 参考表导入数据")
async def import_from_ref(type: str = "all"):
    imported = {"genres": 0, "companies": 0, "keywords": 0}
    async with await TmdbFullDB.get_session() as session:
        if type in ["all", "genre"]:
            ref_genres = await session.execute(select(RefGenre))
            for item in ref_genres.scalars().all():
                existing = await session.get(UserGenreMapping, item.id)
                if not existing:
                    session.add(UserGenreMapping(
                        id=item.id,
                        name_zh=item.name_zh or "",
                        name_en=item.name_en or ""
                    ))
                    imported["genres"] += 1
            await session.commit()

        if type in ["all", "company"]:
            ref_companies = await session.execute(select(RefCompany))
            for item in ref_companies.scalars().all():
                existing = await session.get(UserCompanyMapping, item.id)
                if not existing:
                    session.add(UserCompanyMapping(
                        id=item.id,
                        name=item.name or "",
                        country=item.country or ""
                    ))
                    imported["companies"] += 1
            await session.commit()

        if type in ["all", "keyword"]:
            ref_keywords = await session.execute(select(RefKeyword))
            for item in ref_keywords.scalars().all():
                existing = await session.get(UserKeywordMapping, item.id)
                if not existing:
                    session.add(UserKeywordMapping(
                        id=item.id,
                        name_zh="",
                        name_en=item.name_en or ""
                    ))
                    imported["keywords"] += 1
            await session.commit()

    return {"status": "success", "imported": imported}

@router.get("/ref_counts", summary="获取参考表数据统计")
async def get_ref_counts():
    async with await TmdbFullDB.get_session() as session:
        genres = await session.execute(select(RefGenre))
        companies = await session.execute(select(RefCompany))
        keywords = await session.execute(select(RefKeyword))
        
        user_genres = await session.execute(select(UserGenreMapping))
        user_companies = await session.execute(select(UserCompanyMapping))
        user_keywords = await session.execute(select(UserKeywordMapping))
        user_languages = await session.execute(select(UserLanguageMapping))
        user_countries = await session.execute(select(UserCountryMapping))
        
        return {
            "ref": {
                "genres": len(genres.scalars().all()),
                "companies": len(companies.scalars().all()),
                "keywords": len(keywords.scalars().all())
            },
            "user": {
                "genres": len(user_genres.scalars().all()),
                "companies": len(user_companies.scalars().all()),
                "keywords": len(user_keywords.scalars().all()),
                "languages": len(user_languages.scalars().all()),
                "countries": len(user_countries.scalars().all())
            }
        }

@router.get("/export", summary="导出所有用户映射")
async def export_mappings():
    async with await TmdbFullDB.get_session() as session:
        genres = await session.execute(select(UserGenreMapping))
        companies = await session.execute(select(UserCompanyMapping))
        keywords = await session.execute(select(UserKeywordMapping))
        languages = await session.execute(select(UserLanguageMapping))
        countries = await session.execute(select(UserCountryMapping))
        
        data = {
            "genres": [{"id": g.id, "name_zh": g.name_zh, "name_en": g.name_en} for g in genres.scalars().all()],
            "companies": [{"id": c.id, "name": c.name, "country": c.country} for c in companies.scalars().all()],
            "keywords": [{"id": k.id, "name_zh": k.name_zh, "name_en": k.name_en} for k in keywords.scalars().all()],
            "languages": [{"code": l.code, "name_zh": l.name_zh, "name_en": l.name_en} for l in languages.scalars().all()],
            "countries": [{"code": c.code, "name_zh": c.name_zh, "name_en": c.name_en} for c in countries.scalars().all()]
        }
        return JSONResponse(content=data)

@router.post("/import", summary="导入用户映射")
async def import_mappings(data: Dict[str, Any], mode: str = "append"):
    imported = {"genres": 0, "companies": 0, "keywords": 0, "languages": 0, "countries": 0}
    async with await TmdbFullDB.get_session() as session:
        if mode == "replace":
            for table in [UserGenreMapping, UserCompanyMapping, UserKeywordMapping, UserLanguageMapping, UserCountryMapping]:
                await session.execute(f"DELETE FROM {table.__table__.fullname}")
        
        if "genres" in data:
            for item in data["genres"]:
                existing = await session.get(UserGenreMapping, item["id"])
                if not existing:
                    session.add(UserGenreMapping(
                        id=item["id"],
                        name_zh=item.get("name_zh", ""),
                        name_en=item.get("name_en", "")
                    ))
                    imported["genres"] += 1
        
        if "companies" in data:
            for item in data["companies"]:
                existing = await session.get(UserCompanyMapping, item["id"])
                if not existing:
                    session.add(UserCompanyMapping(
                        id=item["id"],
                        name=item.get("name", ""),
                        country=item.get("country", "")
                    ))
                    imported["companies"] += 1
        
        if "keywords" in data:
            for item in data["keywords"]:
                existing = await session.get(UserKeywordMapping, item["id"])
                if not existing:
                    session.add(UserKeywordMapping(
                        id=item["id"],
                        name_zh=item.get("name_zh", ""),
                        name_en=item.get("name_en", "")
                    ))
                    imported["keywords"] += 1
        
        if "languages" in data:
            for item in data["languages"]:
                existing = await session.get(UserLanguageMapping, item["code"])
                if not existing:
                    session.add(UserLanguageMapping(
                        code=item["code"],
                        name_zh=item.get("name_zh", ""),
                        name_en=item.get("name_en", "")
                    ))
                    imported["languages"] += 1
        
        if "countries" in data:
            for item in data["countries"]:
                existing = await session.get(UserCountryMapping, item["code"])
                if not existing:
                    session.add(UserCountryMapping(
                        code=item["code"],
                        name_zh=item.get("name_zh", ""),
                        name_en=item.get("name_en", "")
                    ))
                    imported["countries"] += 1
        
        await session.commit()
    
    await refresh_mapping_cache()
    return {"status": "success", "imported": imported}
