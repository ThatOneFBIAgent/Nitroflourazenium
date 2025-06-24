import discord
from discord.ext import commands
import config
import asyncio
import random
import sys
import logging
import socket
import aiohttp # straight up useless but whatever


# Import command cogs
from commands.economy import Economy
from commands.shop import Shop
from commands.gambling import Gambling
from commands.fun import Fun

# Intents & Bot Setup
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Load command cogs
async def load_cogs():
    await bot.add_cog(Economy(bot))
    await bot.add_cog(Shop(bot))
    await bot.add_cog(Gambling(bot))
    await bot.add_cog(Fun(bot))

# Sync commands with Discord
@bot.event
async def on_ready():
    await bot.tree.sync()
    print("Commands synced!")

# Run the bot
async def main():
    async with bot:
        await load_cogs()
        await bot.start(config.BOT_TOKEN)

asyncio.run(main())
