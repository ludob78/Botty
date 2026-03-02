# Botty — Trading Bot Gateway

API gateway that receives trading signals (e.g. from TradingView webhooks) and executes them on a MetaTrader 5 account.

## Architecture

```
TradingView Alert ──▶ POST /webhook ──▶ Botty (FastAPI) ──▶ MetaTrader 5 Terminal
```

| Component | Role |
|---|---|
| **main.py** | FastAPI application — routes, authentication, request validation |
| **mt5_service.py** | MetaTrader 5 connection service — login, order execution, position management |
| **Procfile** | Heroku process declaration |
| **Dockerfile** | Container build for local/Docker deployment |

## Quick start

### Prerequisites

- Python 3.12+
- MetaTrader 5 terminal installed (Windows only)
- An MT5 account (demo or live)

### Installation

```bash
pip install -r requirements.txt
```

### Configuration

Create a `.env` file at the project root (already in `.gitignore`):

```env
API_SECRET_KEY=your_secret_key_here

MT5_LOGIN=12345678
MT5_PASSWORD=your_mt5_password
MT5_SERVER=YourBroker-Server
MT5_PATH=C:\Program Files\MetaTrader 5\terminal64.exe
```

| Variable | Required | Description |
|---|---|---|
| `API_SECRET_KEY` | Yes | Secret key that must match the `key` field in every webhook request |
| `MT5_LOGIN` | Yes | MT5 account number |
| `MT5_PASSWORD` | Yes | MT5 account password |
| `MT5_SERVER` | Yes | Broker server name (visible in MT5 → File → Login) |
| `MT5_PATH` | No | Full path to `terminal64.exe` (auto-detected if omitted) |

### Run locally

```bash
python main.py
```

The server starts on `http://localhost:8000`.

## API documentation (Swagger)

FastAPI generates interactive documentation automatically:

| URL | Format |
|---|---|
| `/docs` | Swagger UI (interactive, try-it-out) |
| `/redoc` | ReDoc (read-only, clean layout) |
| `/openapi.json` | Raw OpenAPI 3.1 spec (JSON) |

## API routes

### General

#### `GET /` — Root

Returns a status message confirming the gateway is running.

**Response**
```json
{ "message": "Trading Bot Gateway — MT5 connected" }
```

---

#### `GET /health` — Health check

Reports MT5 connection status and account balance.

**Response (connected)**
```json
{ "status": "healthy", "mt5": "connected", "balance": 10000.0 }
```

**Response (disconnected)**
```json
{ "status": "degraded", "mt5": "disconnected" }
```

### Trading

#### `GET /positions` — List open positions

Returns all open positions on the MT5 account.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `symbol` | query string | No | Filter by symbol (e.g. `EURUSD`) |

**Example**: `GET /positions?symbol=EURUSD`

**Response**
```json
[
  {
    "ticket": 123456,
    "symbol": "EURUSD",
    "type": 0,
    "volume": 0.1,
    "price_open": 1.08550,
    "sl": 1.08000,
    "tp": 1.09000,
    "profit": 12.50
  }
]
```

---

#### `POST /webhook` — Receive a trading signal

Main endpoint for incoming alerts. Requires authentication via the `key` field.

**Request body**

| Field | Type | Required | Description |
|---|---|---|---|
| `key` | string | Yes | Must match `API_SECRET_KEY` |
| `symbol` | string | Yes | Instrument (e.g. `EURUSD`) |
| `action` | string | Yes | `buy`, `sell`, `buy_limit`, `sell_limit`, `buy_stop`, `sell_stop`, or `close_all` |
| `quantity` | float | Yes | Volume in lots (e.g. `0.1`) |
| `price` | float | No | Limit/stop price. Omit for market orders |
| `sl` | float | No | Stop-loss price |
| `tp` | float | No | Take-profit price |
| `position` | string | No | Reserved for future use |
| `timestamp` | string | No | Timestamp from the alert source |

**Example — Market buy**
```json
{
  "key": "your_api_secret_key",
  "symbol": "EURUSD",
  "action": "buy",
  "quantity": 0.1,
  "sl": 1.08000,
  "tp": 1.09000
}
```

**Response (success)**
```json
{
  "status": "success",
  "order": {
    "success": true,
    "ticket": 789012,
    "price": 1.08550,
    "volume": 0.1
  }
}
```

**Example — Close all positions on a symbol**
```json
{
  "key": "your_api_secret_key",
  "symbol": "EURUSD",
  "action": "close_all",
  "quantity": 0
}
```

**Response**
```json
{
  "status": "success",
  "closed": [
    { "success": true, "ticket": 789013, "price": 1.08600 }
  ]
}
```

**Error responses**

| Code | Reason |
|---|---|
| `403` | Invalid API key |
| `400` | Order execution failed (symbol not found, insufficient margin, etc.) |

## MT5 service (`mt5_service.py`)

The service module manages the full lifecycle of the MetaTrader 5 connection:

| Function | Description |
|---|---|
| `connect()` | Initializes the MT5 terminal and logs in. Called automatically on app startup |
| `disconnect()` | Cleanly shuts down the MT5 connection. Called on app shutdown |
| `account_info()` | Returns account details (balance, equity, margin, currency) |
| `get_symbol_info(symbol)` | Returns symbol specifications (spread, tick size, lot step) |
| `open_order(...)` | Places a market or pending order with optional SL/TP |
| `close_position(ticket)` | Closes a single position by ticket number |
| `close_all_positions(symbol)` | Closes all open positions, optionally filtered by symbol |
| `get_positions(symbol)` | Lists all open positions |

Supported order types: `buy`, `sell`, `buy_limit`, `sell_limit`, `buy_stop`, `sell_stop`.

## TradingView webhook setup

1. Create an alert in TradingView
2. Set the webhook URL to `https://your-domain/webhook`
3. Use this JSON template as the alert message:

```json
{
  "key": "your_api_secret_key",
  "symbol": "{{ticker}}",
  "action": "{{strategy.order.action}}",
  "quantity": {{strategy.order.contracts}},
  "price": {{strategy.order.price}},
  "position": "{{strategy.position_size}}",
  "timestamp": "{{time}}"
}
```

## Deployment

### Local (Windows required for MT5)

```bash
pip install -r requirements.txt
python main.py
```

### Docker

```bash
docker build -t botty .
docker run -p 8000:8000 --env-file .env botty
```

> **Note**: the Docker image runs on Linux where the MT5 Python package is not available.
> Use Docker only if you plan a hybrid architecture with a separate MT5 bridge.
