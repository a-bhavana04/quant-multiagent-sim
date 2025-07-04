import gym
import numpy as np

class MarketEnv(gym.Env):
    metadata = {"render.modes": ["human"]}

    def __init__(self):
        super(MarketEnv, self).__init__()
        self.observation_space = gym.spaces.Box(low=-np.inf, high=np.inf, shape=(5,), dtype=np.float32)
        self.action_space = gym.spaces.Discrete(3)  # 0=Buy, 1=Hold, 2=Sell
        self.reset()

    def reset(self):
        self.position = 0
        self.cash = 10000
        self.prices = [100.0]
        return self._get_obs()

    def _get_obs(self):
        recent = self.prices[-5:]
        while len(recent) < 5:
            recent.insert(0, 100.0)  # pad to ensure 5 prices
        returns = np.diff(recent) / np.array(recent[:-1])
        obs = np.concatenate([[recent[-1]], returns])
        return obs.astype(np.float32)

    def step(self, action):
        reward = 0
        next_price = self.prices[-1] + np.random.normal(0, 1)  # simulate price
        self.prices.append(next_price)

        if action == 0:  # Buy
            self.position += 1
            self.cash -= next_price
        elif action == 2:  # Sell
            self.position -= 1
            self.cash += next_price

        unrealized_pnl = self.position * next_price
        total_value = self.cash + unrealized_pnl
        reward = total_value - 10000  # reward = net profit

        done = False
        return self._get_obs(), reward, done, {}

    def render(self, mode="human"):
        print(f"Price: {self.prices[-1]:.2f}, Position: {self.position}, Cash: {self.cash:.2f}")
