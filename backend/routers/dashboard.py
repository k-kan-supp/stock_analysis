from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from backend.db.database import get_db
from backend.models.schemas import DashboardSummary, StockSummary, IndustrySummary

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_SUMMARY_COLS = """
    s.stock_code, s.company_name_ja, s.market_section::text AS market_section,
    s.industry_code, s.market_cap_jpy, s.price_latest,
    s.per_ttm, s.pbr, s.dividend_yield, s.roe, s.rsi_14
"""
_FROM_STOCKS = "FROM stocks s"


@router.get("/summary", response_model=DashboardSummary)
async def dashboard_summary(db: AsyncSession = Depends(get_db)):
    total = (await db.execute(
        text("SELECT COUNT(*) FROM stocks WHERE is_active = TRUE")
    )).scalar_one()

    by_market_rows = (await db.execute(text(
        "SELECT market_section::text, COUNT(*)::int AS count "
        "FROM stocks WHERE is_active = TRUE "
        "GROUP BY market_section ORDER BY count DESC"
    ))).mappings().all()

    by_industry_rows = (await db.execute(text(
        """
        SELECT im.industry_code, im.industry_name_ja,
               COUNT(s.stock_code)::int AS stock_count,
               ROUND(AVG(s.roe)::numeric, 4) AS avg_roe,
               ROUND(AVG(s.pbr)::numeric, 3) AS avg_pbr,
               ROUND(AVG(s.dividend_yield)::numeric, 4) AS avg_dividend_yield,
               SUM(s.market_cap_jpy) AS total_market_cap_jpy
        FROM industry_master im
        LEFT JOIN stocks s ON s.industry_code = im.industry_code AND s.is_active = TRUE
        GROUP BY im.industry_code, im.industry_name_ja
        ORDER BY total_market_cap_jpy DESC NULLS LAST
        LIMIT 10
        """
    ))).mappings().all()

    top_gainers_rows = (await db.execute(text(
        f"SELECT {_SUMMARY_COLS} {_FROM_STOCKS} "
        "WHERE s.is_active = TRUE ORDER BY s.price_vs_52w_high DESC NULLS LAST LIMIT 5"
    ))).mappings().all()

    top_losers_rows = (await db.execute(text(
        f"SELECT {_SUMMARY_COLS} {_FROM_STOCKS} "
        "WHERE s.is_active = TRUE ORDER BY s.price_vs_52w_high ASC NULLS LAST LIMIT 5"
    ))).mappings().all()

    high_dividend_rows = (await db.execute(text(
        f"SELECT {_SUMMARY_COLS} {_FROM_STOCKS} "
        "WHERE s.is_active = TRUE AND s.dividend_yield IS NOT NULL "
        "ORDER BY s.dividend_yield DESC NULLS LAST LIMIT 5"
    ))).mappings().all()

    return DashboardSummary(
        total_stocks=total,
        by_market=[dict(r) for r in by_market_rows],
        by_industry=[IndustrySummary(**r) for r in by_industry_rows],
        top_gainers=[StockSummary(**r) for r in top_gainers_rows],
        top_losers=[StockSummary(**r) for r in top_losers_rows],
        high_dividend=[StockSummary(**r) for r in high_dividend_rows],
    )
