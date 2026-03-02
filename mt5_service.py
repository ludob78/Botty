import os
import logging
from datetime import datetime

import MetaTrader5 as mt5

logger = logging.getLogger(__name__)

MT5_LOGIN = int(os.environ.get("MT5_LOGIN", "0"))
MT5_PASSWORD = os.environ.get("MT5_PASSWORD", "")
MT5_SERVER = os.environ.get("MT5_SERVER", "")
MT5_PATH = os.environ.get("MT5_PATH", "")


def connect() -> bool:
    kwargs = {}
    if MT5_PATH:
        kwargs["path"] = MT5_PATH

    if not mt5.initialize(**kwargs):
        logger.error("MT5 initialize failed: %s", mt5.last_error())
        return False

    if MT5_LOGIN and MT5_PASSWORD and MT5_SERVER:
        if not mt5.login(MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER):
            logger.error("MT5 login failed: %s", mt5.last_error())
            mt5.shutdown()
            return False

    info = mt5.account_info()
    if info is None:
        logger.error("Cannot retrieve account info: %s", mt5.last_error())
        mt5.shutdown()
        return False

    logger.info(
        "Connected to MT5 — account=%s  server=%s  balance=%.2f %s",
        info.login, info.server, info.balance, info.currency,
    )
    return True


def disconnect():
    mt5.shutdown()
    logger.info("MT5 disconnected")


def account_info() -> dict | None:
    info = mt5.account_info()
    if info is None:
        logger.error("account_info failed: %s", mt5.last_error())
        return None
    return info._asdict()


def get_symbol_info(symbol: str) -> dict | None:
    info = mt5.symbol_info(symbol)
    if info is None:
        logger.error("symbol_info(%s) failed: %s", symbol, mt5.last_error())
        return None
    if not info.visible:
        mt5.symbol_select(symbol, True)
    return info._asdict()


def open_order(
    symbol: str,
    action: str,
    volume: float,
    price: float | None = None,
    sl: float | None = None,
    tp: float | None = None,
    comment: str = "botty",
    magic: int = 123456,
) -> dict:
    sym = mt5.symbol_info(symbol)
    if sym is None:
        return {"success": False, "error": f"Symbol {symbol} not found"}
    if not sym.visible:
        mt5.symbol_select(symbol, True)

    order_type_map = {
        "buy":        mt5.ORDER_TYPE_BUY,
        "sell":       mt5.ORDER_TYPE_SELL,
        "buy_limit":  mt5.ORDER_TYPE_BUY_LIMIT,
        "sell_limit": mt5.ORDER_TYPE_SELL_LIMIT,
        "buy_stop":   mt5.ORDER_TYPE_BUY_STOP,
        "sell_stop":  mt5.ORDER_TYPE_SELL_STOP,
    }

    order_type = order_type_map.get(action.lower())
    if order_type is None:
        return {"success": False, "error": f"Unknown action: {action}"}

    if price is None:
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return {"success": False, "error": "Cannot get tick price"}
        price = tick.ask if "buy" in action.lower() else tick.bid

    request = {
        "action": mt5.TRADE_ACTION_DEAL if order_type in (mt5.ORDER_TYPE_BUY, mt5.ORDER_TYPE_SELL) else mt5.TRADE_ACTION_PENDING,
        "symbol": symbol,
        "volume": float(volume),
        "type": order_type,
        "price": float(price),
        "magic": magic,
        "comment": comment,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    if sl is not None:
        request["sl"] = float(sl)
    if tp is not None:
        request["tp"] = float(tp)

    result = mt5.order_send(request)
    if result is None:
        return {"success": False, "error": str(mt5.last_error())}
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        return {"success": False, "retcode": result.retcode, "error": result.comment}

    logger.info(
        "Order placed: %s %s %.2f lots @ %.5f  ticket=%s",
        action, symbol, volume, price, result.order,
    )
    return {"success": True, "ticket": result.order, "price": result.price, "volume": result.volume}


def close_position(ticket: int, comment: str = "botty_close") -> dict:
    position = None
    for pos in (mt5.positions_get() or []):
        if pos.ticket == ticket:
            position = pos
            break

    if position is None:
        return {"success": False, "error": f"Position {ticket} not found"}

    close_type = mt5.ORDER_TYPE_SELL if position.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
    tick = mt5.symbol_info_tick(position.symbol)
    if tick is None:
        return {"success": False, "error": "Cannot get tick price"}
    close_price = tick.bid if position.type == mt5.ORDER_TYPE_BUY else tick.ask

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": position.symbol,
        "volume": position.volume,
        "type": close_type,
        "position": position.ticket,
        "price": close_price,
        "comment": comment,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    if result is None:
        return {"success": False, "error": str(mt5.last_error())}
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        return {"success": False, "retcode": result.retcode, "error": result.comment}

    logger.info("Position %s closed @ %.5f", ticket, result.price)
    return {"success": True, "ticket": result.order, "price": result.price}


def close_all_positions(symbol: str | None = None, comment: str = "botty_close_all") -> list[dict]:
    positions = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
    if not positions:
        return []
    return [close_position(pos.ticket, comment) for pos in positions]


def get_positions(symbol: str | None = None) -> list[dict]:
    positions = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
    if positions is None:
        return []
    return [p._asdict() for p in positions]
