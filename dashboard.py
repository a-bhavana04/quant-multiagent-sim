import streamlit as st
import pandas as pd
import asyncio
import threading
import requests
import os
from dotenv import load_dotenv

from app.models.db import SessionLocal
from app.models.models import User, Portfolio
from app.agents.agent_base import (
    TrendFollowerAgent, MeanReverterAgent, SentimentAgent,
    ArbitrageAgent, MarketMakerAgent, PPOAgent
)
from app.services.market_data import MarketDataFeed
from app.state import order_book

# Load API key
load_dotenv()
API_KEY = os.getenv("ALPHA_VANTAGE_KEY")
if not API_KEY:
    st.error("❌ ALPHA_VANTAGE_KEY missing! Add it to your .env file.")
    st.stop()

st.set_page_config(page_title="Quant Trading Simulator", layout="wide")
st.title("📈 Real-Time Quant Trading Simulator")

db = SessionLocal()

# --- User authentication ---
if "user" not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    tab1, tab2 = st.tabs(["Login", "Register"])

    with tab1:
        st.subheader("🔐 Login")
        username = st.text_input("Username", key="login_user")
        password = st.text_input("Password", type="password", key="login_pass")
        if st.button("Login"):
            user = db.query(User).filter_by(username=username, hashed_password=password).first()
            if user:
                st.session_state.user = user
                st.success(f"✅ Logged in as {username}")
                st.rerun()
            else:
                st.error("Invalid credentials")

    with tab2:
        st.subheader("📝 Register")
        new_username = st.text_input("New Username", key="reg_user")
        new_email = st.text_input("Email", key="reg_email")
        new_password = st.text_input("Password", type="password", key="reg_pass")
        if st.button("Register"):
            existing = db.query(User).filter_by(username=new_username).first()
            if existing:
                st.error("Username already exists")
            else:
                user = User(username=new_username, email=new_email, hashed_password=new_password)
                db.add(user)
                db.commit()
                st.success("Account created. Please log in.")
else:
    st.success(f"Welcome, {st.session_state.user.username}!")

    # --- User portfolio ---
    st.header("📂 Your Portfolio")

    user_portfolio = db.query(Portfolio).filter_by(user_id=st.session_state.user.id).all()
    symbols = [p.symbol for p in user_portfolio]

    if user_portfolio:
        cols = st.columns(len(user_portfolio))
        for i, stock in enumerate(user_portfolio):
            cols[i].markdown(
                f"<div style='padding:8px 16px;border-radius:20px;"
                f"background:linear-gradient(90deg, #a1c4fd, #c2e9fb);"
                f"display:inline-block;font-weight:bold;color:#000;text-align:center;'>"
                f"{stock.symbol}</div>",
                unsafe_allow_html=True
            )
    else:
        st.info("Your portfolio is empty. Add stocks below!")

    # --- Add new stocks with live symbol search ---
    st.subheader("🆕 Add Stocks to Your Portfolio (with Validation)")

    symbol_input = st.text_input("Type company name or symbol (e.g., 'Tesla' or 'TSLA')", key="symbol_input")

    if st.button("Search & Add Symbol"):
        if not symbol_input:
            st.warning("⚠️ Please enter a company name or ticker symbol.")
        else:
            search_url = "https://www.alphavantage.co/query"
            params = {
                "function": "SYMBOL_SEARCH",
                "keywords": symbol_input,
                "apikey": API_KEY
            }
            response = requests.get(search_url, params=params)
            if response.status_code == 200:
                results = response.json().get("bestMatches", [])
                if results:
                    best_match = results[0]
                    validated_symbol = best_match["1. symbol"]
                    company_name = best_match["2. name"]
                    region = best_match["4. region"]
                    st.success(f"✅ Found: {validated_symbol} - {company_name} ({region})")

                    existing = db.query(Portfolio).filter_by(user_id=st.session_state.user.id, symbol=validated_symbol).first()
                    if not existing:
                        db.add(Portfolio(user_id=st.session_state.user.id, symbol=validated_symbol))
                        db.commit()
                        st.success(f"✅ Symbol {validated_symbol} added to your portfolio!")
                        st.rerun()
                    else:
                        st.info(f"ℹ️ Symbol {validated_symbol} is already in your portfolio.")
                else:
                    st.error(f"❌ No matches found for '{symbol_input}'. Try a different name or ticker.")
            else:
                st.error("❌ Error calling Alpha Vantage SYMBOL_SEARCH API. Check your API key or internet connection.")

    # --- Initialize market feeds dict ---
    if "market_feeds" not in st.session_state:
        st.session_state.market_feeds = {}

    # Copy feeds dict for threads
    market_feeds_copy = dict(st.session_state.market_feeds)

    # --- Start market feeds for portfolio symbols ---
    async def start_feeds(feeds_dict):
        for i, symbol in enumerate(symbols):
            if symbol not in feeds_dict:
                feed = MarketDataFeed(symbol=symbol, api_key=API_KEY)
                feeds_dict[symbol] = feed
                asyncio.create_task(feed.run())
                st.success(f"✅ Feed started for {symbol}")
                await asyncio.sleep(15)  # avoid rate limit

    threading.Thread(target=asyncio.run, args=(start_feeds(market_feeds_copy),), daemon=True).start()

    # --- Agent control ---
    if "agents" not in st.session_state:
        st.session_state.agents = {}

    st.sidebar.header("🤖 Agent Control")
    agent_type = st.sidebar.selectbox(
        "Agent Type",
        ["TrendFollower", "MeanReverter", "Sentiment", "Arbitrage", "MarketMaker", "PPO"]
    )

    if st.sidebar.button("Start Agent"):
        agent_name = f"{agent_type}_{len(st.session_state.agents) + 1}"

        if agent_type == "TrendFollower":
            agent = TrendFollowerAgent(agent_name)
        elif agent_type == "MeanReverter":
            agent = MeanReverterAgent(agent_name)
        elif agent_type == "Sentiment":
            agent = SentimentAgent(agent_name)
        elif agent_type == "Arbitrage":
            agent = ArbitrageAgent(agent_name)
        elif agent_type == "MarketMaker":
            agent = MarketMakerAgent(agent_name)
        elif agent_type == "PPO":
            agent = PPOAgent(agent_name)
        else:
            st.sidebar.error("Unknown agent type selected.")
            agent = None

        if agent:
            st.session_state.agents[agent_name] = agent
            for symbol in symbols:
                if symbol in market_feeds_copy:
                    market_feeds_copy[symbol].subscribe(agent)
            threading.Thread(target=asyncio.run, args=(agent.run(),), daemon=True).start()
            st.sidebar.success(f"✅ Agent '{agent_name}' started on symbols: {symbols}")

    if st.sidebar.button("Stop Agent"):
        agent_names = list(st.session_state.agents.keys())
        if agent_names:
            agent_to_stop = agent_names[-1]
            agent = st.session_state.agents.get(agent_to_stop)
            if agent:
                agent.stop()
                st.sidebar.warning(f"🛑 Agent '{agent_to_stop}' stopped.")
            else:
                st.sidebar.error("Agent not found!")
        else:
            st.sidebar.info("ℹ️ No agents to stop.")

    # --- Show live trades ---
    st.subheader("📊 Live Trades")
    trade_placeholder = st.empty()

    if st.button("🔄 Refresh Trades"):
        st.rerun()

    trades = order_book.trade_history
    if trades:
        df = pd.DataFrame(trades)
        trade_placeholder.dataframe(df, use_container_width=True)
    else:
        trade_placeholder.info("No trades yet... agents warming up!")