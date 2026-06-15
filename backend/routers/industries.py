from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from backend.db.database import get_db
from backend.models.schemas import IndustrySummary

router = APIRouter(prefix="/industries", tags=["industries"])


@router.get("/", response_model=list[IndustrySummary])
async def list_industries(db: AsyncSession = Depends(get_db)):
    sql = text(
        """
        SELECT
            im.industry_code,
            im.industry_name_ja,
            COUNT(s.stock_code)::int AS stock_count,
            ROUND(AVG(s.roe)::numeric, 4) AS avg_roe,
            ROUND(AVG(s.pbr)::numeric, 3) AS avg_pbr,
            ROUND(AVG(s.dividend_yield)::numeric, 4) AS avg_dividend_yield,
            SUM(s.market_cap_jpy) AS total_market_cap_jpy
        FROM industry_master im
        LEFT JOIN stocks s
            ON s.industry_code = im.industry_code AND s.is_active = TRUE
        GROUP BY im.industry_code, im.industry_name_ja
        ORDER BY total_market_cap_jpy DESC NULLS LAST
        """
    )
    rows = (await db.execute(sql)).mappings().all()
    return [IndustrySummary(**r) for r in rows]
