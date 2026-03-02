from contextlib import asynccontextmanager
import json
import logging
import os

from fastapi import FastAPI, HTTPException, Depends, Query, Request
from pydantic import BaseModel, Field, ValidationError
import uvicorn

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

API_SECRET_KEY = os.environ.get("API_SECRET_KEY", "VOTRE_CLE_SUPER_SECRETE")


@asynccontextmanager
async def lifespan(application: FastAPI):
    yield


app = FastAPI(
    title="Botty — Trading Bot Gateway",
    description=(
        "API gateway that receives trading signals (e.g. from TradingView webhooks) "
        "and executes them on a MetaTrader 5 account.\n\n"
        "**Authentication**: every POST request must include a `key` field matching "
        "the server-side `API_SECRET_KEY` environment variable."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "General", "description": "Health check and status endpoints"},
        {"name": "Trading", "description": "Order execution and position management via MetaTrader 5"},
    ],
)


# ── Request / Response models ────────────────────────────────────────

class TradeSignal(BaseModel):
    key: str = Field(description="API secret key for authentication")
    symbol: str = Field(examples=["EURUSD"], description="Trading instrument symbol")
    action: str = Field(
        examples=["buy"],
        description="Order action: buy, sell, buy_limit, sell_limit, buy_stop, sell_stop, or close_all",
    )
    quantity: float = Field(examples=[0.1], description="Volume in lots")
    price: float | None = Field(default=None, examples=[1.08550], description="Limit/stop price (omit for market orders)")
    sl: float | None = Field(default=None, examples=[1.08000], description="Stop-loss price")
    tp: float | None = Field(default=None, examples=[1.09000], description="Take-profit price")
    position: str | None = Field(default=None, description="Position identifier (reserved for future use)")
    timestamp: str | None = Field(default=None, description="Signal timestamp from the alert source")

    model_config = {"json_schema_extra": {
        "examples": [{
            "key": "your_api_secret_key",
            "symbol": "EURUSD",
            "action": "buy",
            "quantity": 0.1,
            "price": None,
            "sl": 1.08000,
            "tp": 1.09000,
        }]
    }}


class StatusResponse(BaseModel):
    message: str


class HealthResponse(BaseModel):
    status: str = Field(examples=["healthy"])
    mt5: str = Field(examples=["connected"])
    balance: float | None = Field(default=None, examples=[10000.0])


class OrderResult(BaseModel):
    success: bool
    ticket: int | None = None
    price: float | None = None
    volume: float | None = None


class WebhookResponse(BaseModel):
    status: str = Field(examples=["success"])
    order: OrderResult | None = None
    closed: list[OrderResult] | None = None


class PositionItem(BaseModel):
    ticket: int
    symbol: str
    type: int
    volume: float
    price_open: float
    sl: float
    tp: float
    profit: float
    comment: str | None = None


# ── Auth dependency ──────────────────────────────────────────────────

async def get_webhook_body(request: Request) -> TradeSignal:
    """Parse JSON body from request. Accepts application/json or raw JSON string (e.g. text/plain from TradingView)."""
    body = await request.body()
    if isinstance(body, bytes):
        body = body.decode("utf-8")
    if isinstance(body, str):
        try:
            data = json.loads(body)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=422, detail=f"Invalid JSON: {e}")
    else:
        data = body
    try:
        return TradeSignal.model_validate(data)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors())


def verify_request(signal: TradeSignal = Depends(get_webhook_body)) -> TradeSignal:
    if signal.key != API_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Clé API invalide")
    return signal


# ── Routes ───────────────────────────────────────────────────────────

@app.get(
    "/",
    tags=["General"],
    summary="Root",
    response_model=StatusResponse,
)
async def root():
    """Returns a simple status message confirming the gateway is running."""
    return {"message": "Trading Bot Gateway — MT5 service disabled"}


@app.get(
    "/health",
    tags=["General"],
    summary="Health check",
    response_model=HealthResponse,
)
async def health():
    """Reports the health of the service. MT5 integration is currently disabled."""
    return {"status": "healthy", "mt5": "disabled", "balance": None}


@app.get(
    "/positions",
    tags=["Trading"],
    summary="List open positions",
    response_model=list[PositionItem],
)
async def positions(
    symbol: str | None = Query(default=None, description="Filter by symbol (e.g. EURUSD). Omit for all positions."),
):
    """MT5 integration is currently disabled; positions endpoint is unavailable."""
    raise HTTPException(status_code=503, detail="MT5 service is currently disabled")


@app.post(
    "/webhook",
    tags=["Trading"],
    summary="Receive a trading signal",
    response_model=WebhookResponse,
    responses={
        400: {"description": "Order execution failed"},
        403: {"description": "Invalid API key"},
    },
)
async def receive_signal(signal: TradeSignal = Depends(verify_request)):
    """
    Main endpoint for incoming trading signals (designed for TradingView webhooks).

    Supported actions:
    - **buy** / **sell** — market order at current price
    - **buy_limit** / **sell_limit** — pending limit order (requires `price`)
    - **buy_stop** / **sell_stop** — pending stop order (requires `price`)
    - **close_all** — close every open position on the given `symbol`
    """
    logger.info("Signal received: %s %s %.2f lots", signal.action, signal.symbol, signal.quantity)
    raise HTTPException(status_code=503, detail="MT5 service is currently disabled")

if __name__ == "__main__":
    import os
    # HTTPS: set SSL_CERTFILE and SSL_KEYFILE (e.g. in .env or environment)
    # Example: SSL_CERTFILE=/path/to/fullchain.pem SSL_KEYFILE=/path/to/privkey.pem
    ssl_certfile = os.environ.get("SSL_CERTFILE")
    ssl_keyfile = os.environ.get("SSL_KEYFILE")
    if ssl_certfile and ssl_keyfile:
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=int(os.environ.get("PORT", 8443)),
            ssl_certfile=ssl_certfile,
            ssl_keyfile=ssl_keyfile,
        )
    else:
        uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))