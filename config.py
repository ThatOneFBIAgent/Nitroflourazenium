import os
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("DISCORD_TOKEN")
DB_PATH = "data/economy.db"

# Replace with actual bot token or env token
