# app/services/market_data.py

import asyncio
import requests

class MarketDataFeed:
    def __init__(self, symbol="AAPL", api_key=None):
        self.price = None
        self.subscribers = []
        self.symbol = symbol
        self.api_key = api_key

    def subscribe(self, agent):
        self.subscribers.append(agent)

    async def run(self):
        while True:
            try:
                response = requests.get(
                    "https://www.alphavantage.co/query",
                    params={
                        "function": "GLOBAL_QUOTE",
                        "symbol": self.symbol,
                        "apikey": self.api_key,
                    },
                )
                data = response.json()
                price_str = data.get("Global Quote", {}).get("05. price")
                if price_str:
                    self.price = float(price_str)
                    print(f"[Market] Real price for {self.symbol}: {self.price:.2f}")
                    for agent in self.subscribers:
                        agent.receive_market_data(self.price)
                else:
                    print("[Market] Failed to get price data, retrying...")

            except Exception as e:
                print(f"[Market] Error fetching data: {e}")

            await asyncio.sleep(60)  # Alpha Vantage free plan: 1 request per minute
