import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import requests
import yfinance as yf

st.set_page_config(page_title="Dashboard Acciones", layout="wide")

RAW_JSON_URL = "https://raw.githubusercontent.com/administracion996/bot-trading-acciones/main/cartera_acciones.json"

@st.cache_data(ttl=30)
def load_data():
    res = requests.get(RAW_JSON_URL)
    return res.json() if res.status_code == 200 else None

data = load_data()

if not data:
    st.error("No se pudo cargar la cartera desde GitHub.")
    st.stop()

eurusd = float(yf.Ticker("EURUSD=X").history(period="1d")['Close'].iloc[-1])

posiciones = data.get("posiciones", {})
efectivo_eur = data.get("efectivo_eur", 0.0)
capital_inicial = data.get("capital_inicial_eur", 10000.0)

valor_posiciones_eur = 0.0
posiciones_tabla = []

for ticker, info in posiciones.items():
    price_usd = float(yf.Ticker(ticker).history(period="1d")['Close'].iloc[-1])
    valor_usd = info["cantidad"] * price_usd
    valor_eur = valor_usd / eurusd
    pnl_eur = valor_eur - info["coste_total_eur"]
    pnl_pct = (pnl_eur / info["coste_total_eur"]) * 100
    
    valor_posiciones_eur += valor_eur
    posiciones_tabla.append({
        "Ticker": ticker,
        "Cantidad": round(info["cantidad"], 4),
        "Precio Compra ($)": round(info["precio_compra_usd"], 2),
        "Precio Actual ($)": round(price_usd, 2),
        "Valor Actual (€)": round(valor_eur, 2),
        "PnL Neto (€)": round(pnl_eur, 2),
        "Rentabilidad (%)": round(pnl_pct, 2)
    })

capital_total_eur = efectivo_eur + valor_posiciones_eur
pnl_global_eur = capital_total_eur - capital_inicial
pnl_global_pct = (pnl_global_eur / capital_inicial) * 100

st.title("📈 Bot de Trading - Mercado Acciones")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Capital Total", f"{capital_total_eur:,.2f} €", f"{pnl_global_pct:+.2f}%")
col2.metric("Efectivo Libre", f"{efectivo_eur:,.2f} €")
col3.metric("Valor en Posiciones", f"{valor_posiciones_eur:,.2f} €")
col4.metric("Posiciones Abiertas", len(posiciones))

st.markdown("---")

st.subheader("Historial y Puntos de Entradas/Salidas")
historial_df = pd.DataFrame(data.get("historial", []))

fig = go.Figure()

if not historial_df.empty:
    historial_df['fecha'] = pd.to_datetime(historial_df['fecha'])
    
    spy = yf.Ticker("SPY").history(period="1mo", interval="1d").reset_index()
    spy['Date'] = spy['Date'].dt.tz_localize(None)
    spy['Rendimiento_%'] = ((spy['Close'] / spy['Close'].iloc[0]) - 1) * 100
    
    fig.add_trace(go.Scatter(x=spy['Date'], y=spy['Rendimiento_%'], mode='lines', name='Benchmark S&P500 (%)', line=dict(color='gray', dash='dash')))

    buys = historial_df[historial_df['tipo'] == 'BUY']
    sells = historial_df[historial_df['tipo'] == 'SELL']

    if not buys.empty:
        fig.add_trace(go.Scatter(
            x=buys['fecha'], 
            y=[0] * len(buys), 
            mode='markers+text',
            name='Compra (BUY)',
            text=buys['ticker'],
            textposition="top center",
            marker=dict(color='limegreen', size=12, symbol='triangle-up')
        ))

    if not sells.empty:
        fig.add_trace(go.Scatter(
            x=sells['fecha'], 
            y=[0] * len(sells), 
            mode='markers+text',
            name='Venta (SELL)',
            text=sells['ticker'],
            textposition="bottom center",
            marker=dict(color='red', size=12, symbol='triangle-down')
        ))

fig.update_layout(template="plotly_dark", height=400, margin=dict(l=10, r=10, t=10, b=10))
st.plotly_chart(fig, use_container_width=True)

st.subheader("Posiciones Activas")
if posiciones_tabla:
    st.dataframe(pd.DataFrame(posiciones_tabla), use_container_width=True)
else:
    st.info("No hay operaciones abiertas en este momento.")

st.subheader("Historial Completo")
if not historial_df.empty:
    st.dataframe(historial_df.sort_values(by="fecha", ascending=False), use_container_width=True)
else:
    st.info("Historial vacío por ahora.")
