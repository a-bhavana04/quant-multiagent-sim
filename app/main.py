# app/main.py

import os
import asyncio
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel

from app.agents.agent_base import Agent
from app.services.market_data import MarketDataFeed
from app.state import order_book  # shared order book

load_dotenv()  # load API keys from .env

app = FastAPI(title="Quant Multi-Agent Trading Simulator")

agents = {}

API_KEY = os.getenv("ALPHA_VANTAGE_KEY")
market_feed = MarketDataFeed(symbol="AAPL", api_key=API_KEY)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(market_feed.run())

class AgentConfig(BaseModel):
    strategy: str = "momentum"

@app.post("/start/{agent_name}")
async def start_agent(agent_name: str, config: AgentConfig):
    agent = Agent(agent_name)
    agents[agent_name] = agent
    market_feed.subscribe(agent)
    asyncio.create_task(agent.run())
    return {"status": f"Agent {agent_name} started with strategy {config.strategy}"}

@app.post("/stop/{agent_name}")
async def stop_agent(agent_name: str):
    agent = agents.get(agent_name)
    if not agent:
        return {"error": "Agent not found"}
    agent.stop()
    return {"status": f"Agent {agent_name} stopped"}