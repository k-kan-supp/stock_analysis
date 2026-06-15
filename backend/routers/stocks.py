from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, func
from backend.db.database import get_db
from backend.models.schemas import (
    StockDetail, DailyPrice, TechnicalDaily,
    ScreeningParams, ScreeningResponse, StockSummary,
)

router = APIRouter(prefix="/stocks", tags=["stocks"])

# v_stock_screening は industry_code / price_latest を含まないため stocks テーブルを直接参照する
_SCREENING_COLS = """
    s.stock_code, s.company_name_ja, s.market_section::text AS market_section,
    s.industry_code, s.market_cap_jpy, s.price_latest,
    s.per_ttm, s.pbr, s.dividend_yield, s.roe, s.rsi_14
"""
_SCREENING_FROM = "FROM stocks s"

_ALLOWED_SORT = {
    "market_cap_jpy", "per_ttm", "pbr", "dividend_yield",
    "roe", "rsi_14", "price_latest",
}


@router.get("/screening", response_model=ScreeningResponse)
async def screening(
    market_section: str | None = None,
    industry_code: str | None = None,
    is_topix: bool | None = None,
    is_nikkei225: bool | None = None,
    per_min: float | None = None,
    per_max: float | None = None,
    pbr_min: float | None = None,
    pbr_max: float | None = None,
    dividend_yield_min: float | None = None,
    roe_min: float | None = None,
    market_cap_min: int | None = None,
    market_cap_max: int | None = None,
    rsi_min: float | None = None,
    rsi_max: float | None = None,
    theme_tag: str | None = None,
    sort_by: str = "market_cap_jpy",
    sort_order: str = "desc",
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    if sort_by not in _ALLOWED_SORT:
        raise HTTPException(status_code=422, detail=f"sort_by must be one of {_ALLOWED_SORT}")
    if sort_order not in ("asc", "desc"):
        raise HTTPException(status_code=422, detail="sort_order must be asc or desc")

    conditions = ["s.is_active = TRUE"]
    params: dict = {}

    if market_section:
        conditions.append("s.market_section::text = :market_section")
        params["market_section"] = market_section
    if industry_code:
        conditions.append("s.industry_code = :industry_code")
        params["industry_code"] = industry_code
    if is_topix is not None:
        conditions.append("s.is_topix = :is_topix")
        params["is_topix"] = is_topix
    if is_nikkei225 is not None:
        conditions.append("s.is_nikkei225 = :is_nikkei225")
        params["is_nikkei225"] = is_nikkei225
    if per_min is not None:
        conditions.append("s.per_ttm >= :per_min")
        params["per_min"] = per_min
    if per_max is not None:
        conditions.append("s.per_ttm <= :per_max")
        params["per_max"] = per_max
    if pbr_min is not None:
        conditions.append("s.pbr >= :pbr_min")
        params["pbr_min"] = pbr_min
    if pbr_max is not None:
        conditions.append("s.pbr <= :pbr_max")
        params["pbr_max"] = pbr_max
    if dividend_yield_min is not None:
        conditions.append("s.dividend_yield >= :dividend_yield_min")
        params["dividend_yield_min"] = dividend_yield_min
    if roe_min is not None:
        conditions.append("s.roe >= :roe_min")
        params["roe_min"] = roe_min
    if market_cap_min is not None:
        conditions.append("s.market_cap_jpy >= :market_cap_min")
        params["market_cap_min"] = market_cap_min
    if market_cap_max is not None:
        conditions.append("s.market_cap_jpy <= :market_cap_max")
        params["market_cap_max"] = market_cap_max
    if rsi_min is not None:
        conditions.append("s.rsi_14 >= :rsi_min")
        params["rsi_min"] = rsi_min
    if rsi_max is not None:
        conditions.append("s.rsi_14 <= :rsi_max")
        params["rsi_max"] = rsi_max
    if theme_tag:
        conditions.append(":theme_tag = ANY(s.custom_theme_tags)")
        params["theme_tag"] = theme_tag

    where = " AND ".join(conditions)
    order = f"s.{sort_by} {sort_order} NULLS LAST"

    count_sql = text(f"SELECT COUNT(*) {_SCREENING_FROM} WHERE {where}")
    total = (await db.execute(count_sql, params)).scalar_one()

    data_sql = text(
        f"SELECT {_SCREENING_COLS} {_SCREENING_FROM} WHERE {where}"
        f" ORDER BY {order} LIMIT :limit OFFSET :offset"
    )
    rows = (await db.execute(data_sql, {**params, "limit": limit, "offset": offset})).mappings().all()

    return ScreeningResponse(total=total, items=[StockSummary(**r) for r in rows])


@router.get("/{code}", response_model=StockDetail)
async def get_stock(code: str, db: AsyncSession = Depends(get_db)):
    sql = text("SELECT * FROM stocks WHERE stock_code = :code AND is_active = TRUE")
    row = (await db.execute(sql, {"code": code})).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Stock not found")
    return StockDetail(**row)


@router.get("/{code}/prices", response_model=list[DailyPrice])
async def get_prices(
    code: str,
    days: int = Query(default=365, le=1825),
    db: AsyncSession = Depends(get_db),
):
    sql = text(
        "SELECT trade_date, open, high, low, close, volume "
        "FROM stock_daily_prices "
        "WHERE stock_code = :code "
        "  AND trade_date >= CURRENT_DATE - :days * INTERVAL '1 day' "
        "ORDER BY trade_date ASC"
    )
    rows = (await db.execute(sql, {"code": code, "days": days})).mappings().all()
    return [DailyPrice(**r) for r in rows]


@router.get("/{code}/technicals", response_model=list[TechnicalDaily])
async def get_technicals(
    code: str,
    days: int = Query(default=365, le=1825),
    db: AsyncSession = Depends(get_db),
):
    sql = text(
        "SELECT trade_date, rsi_14, macd, macd_signal, macd_hist, "
        "       bb_upper, bb_mid, bb_lower, "
        "       ma7, ma25, ma49, ma75, ma98, ma200, "
        "       std_49, sigma3_upper_49, sigma3_lower_49, is_outlier_49, "
        "       std_98, sigma3_upper_98, sigma3_lower_98, is_outlier_98 "
        "FROM stock_technical_daily "
        "WHERE stock_code = :code "
        "  AND trade_date >= CURRENT_DATE - :days * INTERVAL '1 day' "
        "ORDER BY trade_date ASC"
    )
    rows = (await db.execute(sql, {"code": code, "days": days})).mappings().all()
    return [TechnicalDaily(**r) for r in rows]
