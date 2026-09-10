import os
import json
import requests
import base64
import yfinance as yf
import pandas as pd
import numpy as np
from google import genai
from google.genai import types

# --- CONFIGURACIÓN ---
GITHUB_TOKEN = os.environ.get('GH_PAT')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
GITHUB_REPO = "administracion996/bot-trading-acciones"
FILE_PATH = "cartera_acciones.json"

COMISION_BROKER_EUR = 1.25
MAX_CAPITAL_PER_TRADE_PCT = 0.50 # Compra máximo el 50% del capital líquido
MAX_LOSS_PCT = 0.10              # Vende automáticamente si la pérdida llega al 10% (Stop-Loss)

TICKERS = ["NVDA", "TSLA", "AMD", "META", "AAPL", "MSFT", "AMZN", "GOOGL"]

client = genai.Client(api_key=GEMINI_API_KEY)

def get_github_file():
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{FILE_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    res = requests.get(url, headers=headers)
    if res.status_code == 200:
        content = res.json()
        decoded_bytes = base64.b64decode(content["content"])
        return json.loads(decoded_bytes.decode('utf-8')), content["sha"]
    raise Exception(f"Error al leer GitHub ({res.status_code}): {res.text}")

def save_github_file(data, sha):
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{FILE_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    encoded_content = base64.b64encode(json.dumps(data, indent=2).encode('utf-8')).decode('utf-8')
    payload = {
        "message": "Actualización automática de cartera",
        "content": encoded_content,
        "sha": sha
    }
    res = requests.put(url, headers=payload, json=payload)
    return res.status_code == 200

def get_eurusd_rate() -> float:
    fx = yf.Ticker("EURUSD=X").history(period="1d")
    return float(fx['Close'].iloc[-1])

def calculate_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    log_returns = np.log(df['Close'] / df['Close'].shift(1))
    df['Volatilidad'] = log_returns.rolling(window=20).std() * np.sqrt(252)
    return df

def get_gemini_decision(ticker: str, price: float, rsi: float, vol: float) -> str:
    prompt = f"""
    Actúa como gestor cuantitativo. Analiza las siguientes métricas de {ticker}:
    - Precio actual USD: {price:.2f}
    - RSI (14 periodos): {rsi:.2f}
    - Volatilidad Anualizada (20d): {vol:.2%}

    Reglas de Decisión:
    - Si RSI < 35 y volatilidad no es extrema: responde BUY.
    - Si RSI > 65: responde SELL.
    - En cualquier otro escenario: responde HOLD.
    Responde ÚNICAMENTE con una palabra: BUY, SELL o HOLD.
    """
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.0)
        )
        decision = response.text.strip().upper()
        return decision if decision in ["BUY", "SELL", "HOLD"] else "HOLD"
    except Exception as e:
        print(f"Error al consultar Gemini para {ticker}: {e}")
        return "HOLD"

def run_trading_bot():
    portfolio, sha = get_github_file()
    eurusd = get_eurusd_rate()
    timestamp = pd.Timestamp.now().isoformat()
    
    posiciones = portfolio["posiciones"]
    efectivo_eur = portfolio["efectivo_eur"]
    historial = portfolio["historial"]

    print(f"--- Inicio de ejecucion | Tipo de cambio EUR/USD: {eurusd:.4f} ---")

    for ticker in TICKERS:
        df = yf.Ticker(ticker).history(period="1mo", interval="1h")
        if df.empty or len(df) < 20:
            continue
            
        df = calculate_technical_indicators(df)
        current_price_usd = float(df['Close'].iloc[-1])
        current_rsi = float(df['RSI'].iloc[-1])
        current_vol = float(df['Volatilidad'].iloc[-1])
        
        signal = get_gemini_decision(ticker, current_price_usd, current_rsi, current_vol)
        print(f"[{ticker}] Precio: ${current_price_usd:.2f} | RSI: {current_rsi:.1f} | Decisión IA: {signal}")

        # --- 1. EVALUAR POSICIONES (VENTAS NORMALES O STOP-LOSS) ---
        if ticker in posiciones:
            pos = posiciones[ticker]
            cantidad = pos["cantidad"]
            coste_total_eur = pos["coste_total_eur"]
            
            valor_bruto_usd = cantidad * current_price_usd
            valor_bruto_eur = valor_bruto_usd / eurusd
            ingreso_neto_eur = valor_bruto_eur - COMISION_BROKER_EUR
            
            beneficio_neto_eur = ingreso_neto_eur - coste_total_eur
            porcentaje_beneficio = beneficio_neto_eur / coste_total_eur

            if porcentaje_beneficio <= -MAX_LOSS_PCT:
                efectivo_eur += ingreso_neto_eur
                historial.append({
                    "fecha": timestamp,
                    "ticker": ticker,
                    "tipo": "SELL",
                    "cantidad": cantidad,
                    "precio_usd": current_price_usd,
                    "eurusd": eurusd,
                    "comision_eur": COMISION_BROKER_EUR,
                    "pnl_neto_eur": beneficio_neto_eur
                })
                del posiciones[ticker]
                print(f"🚨 STOP-LOSS EJECUTADO: {ticker} | Venta de emergencia por pérdida del {porcentaje_beneficio:.2%}")

            elif signal == "SELL" and beneficio_neto_eur > 0.00:
                efectivo_eur += ingreso_neto_eur
                historial.append({
                    "fecha": timestamp,
                    "ticker": ticker,
                    "tipo": "SELL",
                    "cantidad": cantidad,
                    "precio_usd": current_price_usd,
                    "eurusd": eurusd,
                    "comision_eur": COMISION_BROKER_EUR,
                    "pnl_neto_eur": beneficio_neto_eur
                })
                del posiciones[ticker]
                print(f"✅ VENTA CON BENEFICIO: {ticker} | Ganancia neta: +{beneficio_neto_eur:.2f} € ({porcentaje_beneficio:.2%})")

            elif signal == "SELL":
                print(f"⛔ VENTA BLOQUEADA: {ticker} | Esperando recuperación (Pérdida actual {porcentaje_beneficio:.2%}).")

        # --- 2. EVALUAR NUEVAS COMPRAS ---
        elif signal == "BUY" and ticker not in posiciones:
            capital_asignado_eur = efectivo_eur * MAX_CAPITAL_PER_TRADE_PCT
            
            if capital_asignado_eur > (COMISION_BROKER_EUR * 2):
                capital_para_acciones_eur = capital_asignado_eur - COMISION_BROKER_EUR
                capital_para_acciones_usd = capital_para_acciones_eur * eurusd
                
                cantidad = capital_para_acciones_usd / current_price_usd
                
                coste_total_eur = capital_asignado_eur
                efectivo_eur -= coste_total_eur
                
                posiciones[ticker] = {
                    "cantidad": cantidad,
                    "precio_compra_usd": current_price_usd,
                    "coste_total_eur": coste_total_eur,
                    "fecha": timestamp
                }
                
                historial.append({
                    "fecha": timestamp,
                    "ticker": ticker,
                    "tipo": "BUY",
                    "cantidad": cantidad,
                    "precio_usd": current_price_usd,
                    "eurusd": eurusd,
                    "comision_eur": COMISION_BROKER_EUR,
                    "pnl_neto_eur": 0.0
                })
                print(f"🛒 COMPRA EJECUTADA: {ticker} | Inversión: {coste_total_eur:.2f} € | Precio: ${current_price_usd:.2f}")

    portfolio["efectivo_eur"] = efectivo_eur
    portfolio["posiciones"] = posiciones
    portfolio["historial"] = historial
    
    if save_github_file(portfolio, sha):
        print("💾 Cartera actualizada correctamente en GitHub.")

if __name__ == "__main__":
    run_trading_bot()
