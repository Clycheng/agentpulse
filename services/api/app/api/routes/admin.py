from fastapi import APIRouter

from app.services.templates import AGENT_TEMPLATES, TALENT_CATEGORIES

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/talent-market")
def talent_market_catalog() -> dict:
    return {
        "categories": TALENT_CATEGORIES,
        "templates": AGENT_TEMPLATES,
        "note": "MVP uses seeded official templates. Admin auth and persistence will be added before production.",
    }
