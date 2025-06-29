# Secrets & others
# config.py
BOT_TOKEN = "YOUR TOKEN HERE"
BOT_OWNER = YOUR_USER_ID_HERE
FORBIDDEN_GUILDS = {

}
# 1234874643892: {"reason": "being annoying"}

# look at the dumma code in main.py for the rest of the config
# This file is used to store configuration settings for the bot.
# it does not mean you'll get my bot's token, i'm not that dumb
# and you shouldn't be either.

# Do not host config.py on your repository, instead use environment variables or a secure vault, or just host it on your pc.

# still doesn't stop me from putting code here.
 
import time, discord
from functools import wraps
from discord import Interaction

# user id: cooldown
_user_cooldowns = {}

def cooldown(seconds: int):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # If this is a method, args[0] is self, args[1] is interaction
            # If this is a function, args[0] is interaction
            if isinstance(args[0], Interaction):
                interaction = args[0]
                rest_args = args[1:]
            else:
                interaction = args[1]
                rest_args = args[2:]

            user_id = interaction.user.id
            now = time.time()

            if user_id in _user_cooldowns:
                elapsed = now - _user_cooldowns[user_id]
                if elapsed < seconds:
                    await interaction.response.send_message(
                        f"🕒 You're on cooldown! Try again in {round(seconds - elapsed, 1)}s.",
                        ephemeral=True
                    )
                    return
            _user_cooldowns[user_id] = now
            return await func(*args, **kwargs)
        return wrapper
    return decorator

# Cooldown wrapper, at any point in any code for commands you can do @cooldown(int) AFTER @app_command.commands such as:
# @app_commands.command(name="example", description="An example command")
# @cooldown(10)  # 10 seconds cooldown
# (rest of code)...
# Calculated in seconds. 1m = 60s, 10m = 600s, 1h = 3600s
