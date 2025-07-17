import asyncio
import numpy as np
import os
import requests
from collections import deque
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
from stable_baselines3 import PPO
import numpy as np

from app.services.order_book import Order
from app.state import order_book  

def fetch_latest_headline(symbol):
    api_key = os.getenv("NEWSAPI_KEY")
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": symbol,
        "apiKey": api_key,
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": 1,
    }
    response = requests.get(url, params=params)
    data = response.json()
    if "articles" in data and len(data["articles"]) > 0:
        return data["articles"][0]["title"]
    else:
        print(f"[SentimentAgent] No recent news found for {symbol}")
        return None

# ---- FinBERT Sentiment Analyzer ----

class FinBertSentiment:
    def __init__(self):
        print("🔍 Loading FinBERT model...")
        self.tokenizer = AutoTokenizer.from_pretrained("ProsusAI/finbert")
        self.model = AutoModelForSequenceClassification.from_pretrained("ProsusAI/finbert")
        print("✅ FinBERT ready!")

    def analyze(self, text):
        inputs = self.tokenizer(text, return_tensors="pt", truncation=True, padding=True)
        outputs = self.model(**inputs)
        probs = torch.softmax(outputs.logits, dim=1).detach().numpy()[0]
        classes = ["Positive", "Negative", "Neutral"]
        return dict(zip(classes, probs))

sentiment_analyzer = FinBertSentiment()



class BaseAgent:
    def __init__(self, name: str, window_size=5):
        self.name = name
        self.running = False
        self.current_price = None
        self.price_history = deque(maxlen=window_size)
        self.position = 0
        self.cash = 10000

    async def run(self):
        self.running = True
        while self.running:
            await asyncio.sleep(1)

    def receive_market_data(self, price: float):
        self.current_price = price
        self.price_history.append(price)
        if len(self.price_history) >= self.price_history.maxlen:
            features = self.compute_features()
            action = self.decide(features)
            if action:
                print(f"[{self.name}] {action} @ {self.current_price:.2f} | Pos: {self.position} | Cash: {self.cash:.2f}")

    def compute_features(self):
        prices = np.array(self.price_history)
        returns = np.diff(prices) / prices[:-1]
        momentum = np.sum(returns)
        volatility = np.std(returns)
        mean_price = np.mean(prices)
        return {"momentum": momentum, "volatility": volatility, "mean_price": mean_price}

    def buy(self):
        order = Order(agent_name=self.name, side="BUY", price=self.current_price)
        order_book.place_order(order)
        self.position += 1
        self.cash -= self.current_price
        return "BUY"

    def sell(self):
        order = Order(agent_name=self.name, side="SELL", price=self.current_price)
        order_book.place_order(order)
        self.position -= 1
        self.cash += self.current_price
        return "SELL"

    def stop(self):
        self.running = False

    def decide(self, features):
        raise NotImplementedError("Each specialized agent must implement decide()")



class TrendFollowerAgent(BaseAgent):
    """
    Buys when momentum positive, sells when momentum negative.
    """
    def decide(self, features):
        if features["momentum"] > 0.01:
            return self.buy()
        elif features["momentum"] < -0.01:
            return self.sell()
        return None

class MeanReverterAgent(BaseAgent):
    """
    Buys when price below average, sells when price above average.
    """
    def decide(self, features):
        deviation = features["mean_price"] - self.current_price
        if deviation > 1:  
            return self.buy()
        elif deviation < -1:  
            return self.sell()
        return None

class SentimentAgent(BaseAgent):
    """
    Uses real news headlines + FinBERT sentiment to decide.
    """
    def decide(self, features):
        symbol = self.name.split("_")[0]
        headline = fetch_latest_headline(symbol)
        if headline:
            sentiment = sentiment_analyzer.analyze(headline)
            print(f"[{self.name}] Headline: '{headline}' → Sentiment: {sentiment}")
            if sentiment["Positive"] > 0.6:
                return self.buy()
            elif sentiment["Negative"] > 0.6:
                return self.sell()
        return None

class ArbitrageAgent(BaseAgent):
    """
    Compares current price to a synthetic 'other market price'.
    If current price is lower, buys; if higher, sells.
    """
    def decide(self, features):
        synthetic_other_price = self.current_price + np.random.normal(0, 0.5)
        price_diff = synthetic_other_price - self.current_price
        if price_diff > 0.5:
            return self.buy()
        elif price_diff < -0.5:
            return self.sell()
        return None

class MarketMakerAgent(BaseAgent):
    """
    Provides liquidity: places both buy and sell orders periodically.
    """
    def decide(self, features):
        if np.random.rand() < 0.5:
            return self.buy()
        else:
            return self.sell()
class PPOAgent(BaseAgent):
    """
    Uses a trained PPO policy to decide actions.
    """
    def __init__(self, name: str, window_size=5):
        super().__init__(name, window_size)
        print("[PPOAgent] Loading trained PPO policy...")
        self.model = PPO.load("trained_quant_agent")
        print("[PPOAgent] PPO policy loaded successfully.")

    def decide(self, features):
        obs = np.array([
            features["mean_price"],
            features["momentum"],
            features["volatility"],
            0, 0  
        ]).reshape(1, -1)

        action, _ = self.model.predict(obs, deterministic=True)
        if action == 0:
            return self.buy()
        elif action == 2:
            return self.sell()
        return None
