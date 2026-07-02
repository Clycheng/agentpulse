from fastapi import APIRouter, Depends

from app.core.database import Database, get_db
from app.services.templates import list_agent_templates, list_talent_categories

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/talent-market")
def talent_market_catalog(conn: Database = Depends(get_db)) -> dict:
    return {
        "categories": list_talent_categories(conn),
        "templates": list_agent_templates(conn),
        "note": "MVP 已把官方人才类目和模板落到 official_* 表。下一步会补管理员登录、编辑、审核和发布流。",
    }
