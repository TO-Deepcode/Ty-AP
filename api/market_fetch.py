"""Fetch market data from Bybit, Binance, and CoinMarketCap."""
from __future__ import annotations

from http import HTTPStatus
from datetime import datetime, timezone
from typing import Any, Dict, List

from src.api_utils import BaseJsonHandler, HttpError, parse_json
from src.config import get_settings
from src.http_clients import request_json
from src.logging_setup import get_logger
from src.schemas import Candle, MarketFetchRequest, MarketFetchResponse, MarketSnapshot
from src.storage import get_storage

logger = get_logger(__name__)

ORIGIN = "aws-webse"
BYBIT_INTERVALS = {"1m": "1", "5m": "5", "15m": "15", "1h": "60", "4h": "240", "1d": "D"}
BINANCE_INTERVALS = {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "1h", "4h": "4h", "1d": "1d"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _store_snapshot(exchange: str, symbol: str, snapshot: MarketSnapshot) -> None:
    storage = get_storage()
    timestamp_key = snapshot.fetched_at.strftime("%Y%m%d%H")
    key = f"market/{exchange}/{symbol}/{timestamp_key}/snapshot.json"
    payload = snapshot.dict()
    payload.update(
        {
            "created_at": snapshot.fetched_at.isoformat(),
            "ttl_days": 14,
        }
    )
    try:
        storage.put_json(key, payload)
    except Exception as exc:  # pragma: no cover - storage failures should not break response
        logger.warning(
            "store_snapshot_failed",
            exchange=exchange,
            symbol=symbol,
            key=key,
            error=str(exc),
        )


def _fetch_binance(symbol: str, granularity: str, limit: int) -> MarketSnapshot:
    interval = BINANCE_INTERVALS[granularity]
    klines = request_json(
        "GET",
        "https://api.binance.com/api/v3/klines",
        params={"symbol": symbol, "interval": interval, "limit": limit},
    )
    candles: List[Candle] = []
    for entry in klines:
        open_time = datetime.fromtimestamp(entry[0] / 1000, tz=timezone.utc)
        candle = Candle(
            open_time=open_time,
            open=float(entry[1]),
            high=float(entry[2]),
            low=float(entry[3]),
            close=float(entry[4]),
            volume=float(entry[5]),
        )
        candles.append(candle)
    ticker = request_json(
        "GET",
        "https://api.binance.com/api/v3/ticker/24hr",
        params={"symbol": symbol},
    )
    fetched_at = _now()
    snapshot = MarketSnapshot(
        origin=ORIGIN,
        source="binance",
        symbol=symbol,
        timeframe=granularity,
        fetched_at=fetched_at,
        from_time=candles[0].open_time if candles else fetched_at,
        to_time=candles[-1].open_time if candles else fetched_at,
        candles=candles,
        last_price=float(ticker.get("lastPrice", 0.0)) if ticker else None,
        change_24h=float(ticker.get("priceChangePercent", 0.0)) if ticker else None,
    )
    return snapshot


def _fetch_bybit(symbol: str, granularity: str, limit: int) -> MarketSnapshot:
    interval = BYBIT_INTERVALS[granularity]
    klines = request_json(
        "GET",
        "https://api.bybit.com/v5/market/kline",
        params={"category": "spot", "symbol": symbol, "interval": interval, "limit": limit},
    )
    data = klines.get("result", {}).get("list") or []
    candles: List[Candle] = []
    for entry in data:
        open_time = datetime.fromtimestamp(int(entry[0]) / 1000, tz=timezone.utc)
        candle = Candle(
            open_time=open_time,
            open=float(entry[1]),
            high=float(entry[2]),
            low=float(entry[3]),
            close=float(entry[4]),
            volume=float(entry[5]),
        )
        candles.append(candle)
    tickers = request_json(
        "GET",
        "https://api.bybit.com/v5/market/tickers",
        params={"category": "spot", "symbol": symbol},
    )
    last_price = None
    change = None
    if tickers.get("result", {}).get("list"):
        ticker = tickers["result"]["list"][0]
        last_price = float(ticker.get("lastPrice", 0.0))
        change = float(ticker.get("price24hPcnt", 0.0)) * 100
    fetched_at = _now()
    snapshot = MarketSnapshot(
        origin=ORIGIN,
        source="bybit",
        symbol=symbol,
        timeframe=granularity,
        fetched_at=fetched_at,
        from_time=candles[0].open_time if candles else fetched_at,
        to_time=candles[-1].open_time if candles else fetched_at,
        candles=candles,
        last_price=last_price,
        change_24h=change,
    )
    return snapshot


def _fetch_cmc(symbol: str, granularity: str, limit: int) -> MarketSnapshot:
    settings = get_settings()
    if not settings.cmc_api_key:
        raise HttpError(HTTPStatus.BAD_REQUEST, "CMC_API_KEY must be configured")

    base_symbol = symbol.replace("USDT", "")
    response = request_json(
        "GET",
        "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest",
        params={"symbol": base_symbol},
        headers={"X-CMC_PRO_API_KEY": settings.cmc_api_key},
    )
    data = next(iter(response.get("data", {}).values()), {})
    quote = data.get("quote", {}).get("USD", {})
    price = float(quote.get("price", 0.0))
    percent_change = float(quote.get("percent_change_24h", 0.0))
    timestamp = quote.get("last_updated")
    if timestamp:
        open_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    else:
        open_time = _now()
    candle = Candle(
        open_time=open_time,
        open=price,
        high=price,
        low=price,
        close=price,
        volume=float(quote.get("volume_24h", 0.0)),
    )
    fetched_at = _now()
    snapshot = MarketSnapshot(
        origin=ORIGIN,
        source="cmc",
        symbol=symbol,
        timeframe=granularity,
        fetched_at=fetched_at,
        from_time=open_time,
        to_time=open_time,
        candles=[candle],
        last_price=price,
        change_24h=percent_change,
    )
    return snapshot


FETCHERS = {
    "binance": _fetch_binance,
    "bybit": _fetch_bybit,
    "cmc": _fetch_cmc,
}


def process_request(payload: Dict[str, Any]) -> Dict[str, Any]:
    request = MarketFetchRequest(**payload)
    snapshots: List[MarketSnapshot] = []
    for exchange in request.exchanges:
        for symbol in request.symbols:
            fetcher = FETCHERS[exchange]
            snapshot = fetcher(symbol, request.granularity, request.limit)
            snapshots.append(snapshot)
            _store_snapshot(exchange, symbol, snapshot)
    response = MarketFetchResponse(origin=ORIGIN, snapshots=snapshots)
    return response.dict()


class handler(BaseJsonHandler):
    def handle_post(self, context, body: bytes) -> Dict[str, Any]:  # type: ignore[override]
        payload = parse_json(body)
        logger.info("market_fetch_request", request_id=context.request_id, exchanges=payload.get("exchanges"), symbols=payload.get("symbols"))
        return process_request(payload)
