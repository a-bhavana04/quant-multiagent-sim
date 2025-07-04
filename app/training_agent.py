from app.rl.market_env import MarketEnv
from stable_baselines3 import PPO

env = MarketEnv()
model = PPO("MlpPolicy", env, verbose=1)
model.learn(total_timesteps=100_000)  # adjust timesteps if needed
model.save("trained_quant_agent")