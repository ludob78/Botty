from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel
import uvicorn
import hmac
import hashlib

app = FastAPI(title="Trading Bot Gateway 2026")

# --- Sécurité ---
import os
API_SECRET_KEY = os.environ.get("API_SECRET_KEY", "VOTRE_CLE_SUPER_SECRETE")
TRADINGVIEW_IPS = ["52.32.178.7", "54.218.243.192"] # IPs officielles TV

class TradeSignal(BaseModel):
    action: str
    symbol: str
    sl: float
    key: str

def verify_request(signal: TradeSignal):
    # 1. Vérification de la clé secrète
    if signal.key != API_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Clé API invalide")
    return True

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/webhook")
async def receive_signal(signal: TradeSignal, verified: bool = Depends(verify_request)):
    """
    Endpoint qui reçoit l'alerte de TradingView
    """
    print(f"Signal Reçu: {signal.action} sur {signal.symbol} | SL: {signal.sl}")
    
    # Ici, vous intégreriez la librairie de votre exchange (ccxt, ib_insync, etc.)
    # Exemple de gestion du risque : 
    # if position_size > max_allowed: return "Risk Limit Exceeded"
    
    return {"status": "success", "message": f"Ordre {signal.action} exécuté"}

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