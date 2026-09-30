"""
Stock Market Analytics Dashboard
---------------------------------
A Streamlit app that pulls live stock data (Yahoo Finance), cleans it
with Pandas/NumPy, computes key trading indicators, and visualizes
trends with interactive Plotly charts.

Run with:  streamlit run app.py
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta

# ----------------------------------------------------------------------
# PAGE CONFIG
# ----------------------------------------------------------------------
st.set_page_config(page_title="Stock Market Dashboard", page_icon="📈", layout="wide")

# ----------------------------------------------------------------------
# DATA FETCHING & CLEANING
# ----------------------------------------------------------------------
@st.cache_data(ttl=1800, show_spinner=False)
def fetch_data(tickers, start, end, interval):
    """Download OHLCV data for each ticker individually (avoids messy
    multi-index columns that come from batch downloads)."""
    data = {}
    for t in tickers:
        df = yf.download(t, start=start, end=end, interval=interval,
                          auto_adjust=True, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        if not df.empty:
            data[t] = df
    return data


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """Basic cleaning: drop fully-empty rows, forward/back-fill small gaps."""
    df = df.dropna(how="all")
    df = df.ffill().bfill()
    return df


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add derived analytical columns using Pandas/NumPy."""
    df = df.copy()
    df["Daily Return"] = df["Close"].pct_change()
    df["Cumulative Return"] = (1 + df["Daily Return"]).cumprod() - 1
    df["SMA20"] = df["Close"].rolling(20).mean()
    df["SMA50"] = df["Close"].rolling(50).mean()
    df["Volatility20"] = df["Daily Return"].rolling(20).std() * np.sqrt(252)

    # RSI (14-day) - classic momentum indicator
    delta = df["Close"].diff()
    gain = delta.where(delta > 0, 0.0).rolling(14).mean()
    loss = -delta.where(delta < 0, 0.0).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    df["RSI"] = 100 - (100 / (1 + rs))
    return df


# ----------------------------------------------------------------------
# SIDEBAR CONTROLS
# ----------------------------------------------------------------------
st.sidebar.title("⚙️ Settings")

tickers_input = st.sidebar.text_input(
    "Tickers (comma separated)", "AAPL, MSFT, GOOGL"
)
tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]

period_choice = st.sidebar.selectbox(
    "Date Range", ["1mo", "3mo", "6mo", "1y", "2y", "5y"], index=3
)
interval = st.sidebar.selectbox("Interval", ["1d", "1wk", "1mo"], index=0)

period_map = {"1mo": 30, "3mo": 90, "6mo": 180, "1y": 365, "2y": 730, "5y": 1825}
end_date = datetime.today()
start_date = end_date - timedelta(days=period_map[period_choice])

st.sidebar.markdown("---")
main_ticker = st.sidebar.selectbox(
    "Primary ticker (detailed view)", tickers if tickers else ["AAPL"]
)

st.title("📈 Stock Market Analytics Dashboard")
st.caption("Live data via Yahoo Finance • Cleaned with Pandas/NumPy • Charts via Plotly")

if not tickers:
    st.warning("Enter at least one ticker symbol in the sidebar.")
    st.stop()

# ----------------------------------------------------------------------
# FETCH + CLEAN
# ----------------------------------------------------------------------
with st.spinner("Fetching live market data..."):
    raw_data = fetch_data(tuple(tickers), start_date, end_date, interval)

if not raw_data or main_ticker not in raw_data:
    st.error("No data returned. Check that the ticker symbols are valid (e.g. AAPL, MSFT).")
    st.stop()

df = clean_data(raw_data[main_ticker])
df = compute_indicators(df)

# ----------------------------------------------------------------------
# KEY METRICS ROW
# ----------------------------------------------------------------------
latest = df.iloc[-1]
prev = df.iloc[-2] if len(df) > 1 else latest
change = latest["Close"] - prev["Close"]
pct_change = (change / prev["Close"]) * 100 if prev["Close"] else 0

col1, col2, col3, col4 = st.columns(4)
col1.metric(f"{main_ticker} Price", f"${latest['Close']:.2f}", f"{pct_change:+.2f}%")
col2.metric("Period High", f"${df['Close'].max():.2f}")
col3.metric("Period Low", f"${df['Close'].min():.2f}")
vol_val = df["Volatility20"].iloc[-1]
col4.metric("Annualized Volatility", f"{vol_val*100:.2f}%" if pd.notna(vol_val) else "N/A")

st.markdown("---")

# ----------------------------------------------------------------------
# PRICE TREND + MOVING AVERAGES
# ----------------------------------------------------------------------
st.subheader(f"{main_ticker} Price Trend with Moving Averages")
fig_price = go.Figure()
fig_price.add_trace(go.Scatter(x=df.index, y=df["Close"], name="Close", line=dict(color="#1f77b4")))
fig_price.add_trace(go.Scatter(x=df.index, y=df["SMA20"], name="SMA 20", line=dict(color="orange", dash="dot")))
fig_price.add_trace(go.Scatter(x=df.index, y=df["SMA50"], name="SMA 50", line=dict(color="green", dash="dot")))
fig_price.update_layout(height=450, xaxis_title="Date", yaxis_title="Price ($)",
                         legend=dict(orientation="h", y=1.02))
st.plotly_chart(fig_price, use_container_width=True)

# ----------------------------------------------------------------------
# CANDLESTICK CHART
# ----------------------------------------------------------------------
st.subheader(f"{main_ticker} Candlestick Chart")
fig_candle = go.Figure(data=[go.Candlestick(
    x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"]
)])
fig_candle.update_layout(height=450, xaxis_rangeslider_visible=False)
st.plotly_chart(fig_candle, use_container_width=True)

# ----------------------------------------------------------------------
# VOLUME + RSI SIDE BY SIDE
# ----------------------------------------------------------------------
col_a, col_b = st.columns(2)

with col_a:
    st.subheader("Trading Volume")
    fig_vol = px.bar(df, x=df.index, y="Volume")
    fig_vol.update_layout(height=350, xaxis_title="Date", yaxis_title="Volume")
    st.plotly_chart(fig_vol, use_container_width=True)

with col_b:
    st.subheader("RSI (14-day)")
    fig_rsi = go.Figure()
    fig_rsi.add_trace(go.Scatter(x=df.index, y=df["RSI"], line=dict(color="purple")))
    fig_rsi.add_hline(y=70, line_dash="dash", line_color="red", annotation_text="Overbought")
    fig_rsi.add_hline(y=30, line_dash="dash", line_color="green", annotation_text="Oversold")
    fig_rsi.update_layout(height=350, yaxis_title="RSI", yaxis_range=[0, 100])
    st.plotly_chart(fig_rsi, use_container_width=True)

# ----------------------------------------------------------------------
# DAILY RETURNS DISTRIBUTION
# ----------------------------------------------------------------------
st.subheader("Daily Returns Distribution")
fig_hist = px.histogram(df, x="Daily Return", nbins=50)
fig_hist.update_layout(height=350, xaxis_title="Daily Return", yaxis_title="Frequency")
st.plotly_chart(fig_hist, use_container_width=True)

# ----------------------------------------------------------------------
# MULTI-TICKER COMPARISON (only if more than 1 ticker entered)
# ----------------------------------------------------------------------
if len(raw_data) > 1:
    st.markdown("---")
    st.header("📊 Multi-Stock Comparison")

    comp_returns = pd.DataFrame()
    for t, tdf in raw_data.items():
        tdf = clean_data(tdf)
        daily_ret = tdf["Close"].pct_change()
        comp_returns[t] = (1 + daily_ret).cumprod() - 1

    st.subheader("Cumulative Returns Comparison")
    fig_comp = px.line(comp_returns, x=comp_returns.index, y=comp_returns.columns)
    fig_comp.update_layout(height=450, xaxis_title="Date", yaxis_title="Cumulative Return",
                            yaxis_tickformat=".0%", legend_title="Ticker")
    st.plotly_chart(fig_comp, use_container_width=True)

    st.subheader("Correlation Heatmap (Daily Returns)")
    returns_matrix = pd.DataFrame()
    for t, tdf in raw_data.items():
        tdf = clean_data(tdf)
        returns_matrix[t] = tdf["Close"].pct_change()
    corr = returns_matrix.corr()
    fig_corr = px.imshow(corr, text_auto=".2f", color_continuous_scale="RdBu_r",
                          zmin=-1, zmax=1, aspect="auto")
    fig_corr.update_layout(height=450)
    st.plotly_chart(fig_corr, use_container_width=True)

# ----------------------------------------------------------------------
# RAW DATA TABLE + DOWNLOAD
# ----------------------------------------------------------------------
st.markdown("---")
st.subheader("Raw / Processed Data")
st.dataframe(df.tail(100), use_container_width=True)

csv_bytes = df.to_csv().encode("utf-8")
st.download_button(
    "⬇️ Download this data as CSV",
    data=csv_bytes,
    file_name=f"{main_ticker}_data.csv",
    mime="text/csv",
)

st.caption("Data source: Yahoo Finance (via yfinance). For educational/portfolio use only — not financial advice.")
