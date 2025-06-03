import discord
import time
import random
import re
import asyncio
from pyurbandict import UrbanDict
from discord.ext import commands
from discord import app_commands
from discord import Interaction
from database import get_leaderboard


# Constants for dice limits
MAX_DICE = 100
MAX_SIDES = 1000

class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # 🏓 PING COMMAND 🏓
    @app_commands.command(name="ping", description="Check the bot's response time!")
    async def ping(self, interaction: discord.Interaction):
        start_time = time.perf_counter()
        await interaction.response.defer()
        end_time = time.perf_counter()
        thinking_time = (end_time - start_time) * 1000
        latency = round(self.bot.latency * 1000, 2)

        embed = discord.Embed(title="🏓 Pong!", color=0x00FF00)
        embed.add_field(name="📡 API Latency", value=f"`{latency}ms`", inline=True)
        embed.add_field(name="⏳ Thinking Time", value=f"`{thinking_time:.2f}ms`", inline=True)
        await interaction.followup.send(embed=embed)

    # 🎲 DICE ROLLER 🎲
    @app_commands.command(name="roll", description="Roll dice using the XdY format with optional modifiers.")
    async def roll(self, interaction: discord.Interaction, dice: str):
        # Regex pattern for dice: XdY, XdY+Z, XdY&N+Z, etc.
        pattern = re.compile(r"(\d+)[dD](\d+)((?:[&+-]\d+)*)")
        match = pattern.fullmatch(dice.replace(" ", ""))

        if not match:
            await interaction.response.send_message(
                "❌ **Invalid format!** Use `XdY`, `XdY+Z`, `XdY&N+Z`, etc. Examples: `2d6`, `3d10+5`, `4d8&2+3`.",
                ephemeral=False
            )
            return

        num_dice, die_sides = int(match.group(1)), int(match.group(2))
        modifiers = match.group(3) if match.group(3) else ""

        if num_dice > MAX_DICE or die_sides > MAX_SIDES:
            await interaction.response.send_message(
                f"❌ **Too many dice!** Limit: `{MAX_DICE}d{MAX_SIDES}`.",
                ephemeral=False
            )
            return

        rolls = [random.randint(1, die_sides) for _ in range(num_dice)]
        results = rolls[:]
        mod_details = []

        # Simple modifier parsing: +Z or -Z applies to all rolls
        if modifiers:
            mods = re.findall(r"([&+-]\d+)", modifiers)
            for mod in mods:
                if mod.startswith("&"):
                    try:
                        count = int(mod[1:])
                        # Apply next + or - modifier only to the first 'count' rolls
                        # We'll mark this and handle in the next modifier
                        mod_details.append(f"& Modifier: Next modifier applies to first {count} rolls")
                        # Store this info for later use
                        and_count = count
                    except ValueError:
                        await interaction.response.send_message(
                            "❌ **Invalid & modifier!** Must be an integer.",
                            ephemeral=False
                        )
                        return
                elif mod.startswith("+") or mod.startswith("-"):
                    try:
                        flat_mod = int(mod)
                        # Check if previous modifier was '&'
                        if 'and_count' in locals():
                            # Apply to first 'and_count' rolls only
                            results = [r + flat_mod if i < and_count else r for i, r in enumerate(results)]
                            mod_details.append(f"First {and_count} Rolls: `{flat_mod}`")
                            del and_count
                        else:
                            results = [r + flat_mod for r in results]
                            mod_details.append(f"All Rolls: `{flat_mod}`")
                    except ValueError:
                        await interaction.response.send_message(
                            "❌ **Invalid modifier!** Modifiers must be integers.",
                            ephemeral=False
                        )
                        return
                    

        mod_text = "\n".join(mod_details) if mod_details else "No modifiers applied"
        rolls_text = ", ".join(map(str, rolls))
        final_text = ", ".join(map(str, results))

        embed = discord.Embed(title="🎲 Dice Roll", color=0x3498db)
        embed.add_field(name="🎯 Rolls", value=f"`{rolls_text}`", inline=True)
        embed.add_field(name="✨ Modifiers", value=f"`{mod_text}`", inline=True)
        embed.add_field(name="🏆 Final Result", value=f"`{final_text}`", inline=False)
        # Validate embed size to ensure it doesn't exceed Discord's limits
        total_length = sum(len(field.value) for field in embed.fields) + len(embed.title or "") + len(embed.description or "")
        if total_length > 6000:
            embed.clear_fields()
            embed.add_field(name="⚠️ Error", value="Embed content exceeded Discord's size limit. Please simplify your input.", inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="8ball" , description="Ask the magic 8-ball a question!")
    async def eight_ball(self, interaction: discord.Interaction, question: str):
        responses = [
            "Yes", "No", "Maybe", "Definitely", "Absolutely not",
            "Ask again later", "I wouldn't count on it", "It's certain",
            "Don't hold your breath", "Yes, in due time"
        ]
        answer = random.choice(responses)
        embed = discord.Embed(title="🎱 Magic 8-Ball", color=0x3498db)
        embed.add_field(name="Question", value=f"`{question}`", inline=False)
        embed.add_field(name="Answer", value=f"`{answer}`", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leaderboard", description="Returns the top 10 richest people using this app")
    async def leaderboard(self, interaction: discord.Interaction):
        leaderboard = get_leaderboard(limit=10)
        user_id = interaction.user.id

        embed = discord.Embed(
            title="🏆 Top 10 Richest Users",
            color=0xFFD700,
            description="Here are the wealthiest users!"
        )

        user_in_top = False
        for idx, (uid, balance) in enumerate(leaderboard, start=1):
            member = await self.bot.fetch_user(uid)
            name = member.display_name if hasattr(member, "display_name") else member.name
            embed.add_field(
                name=f"#{idx} {name}",
                value=f"Balance: `{balance:,}`",
                inline=False
            )
            if uid == user_id:
                user_in_top = True
                user_balance = balance

        # If user not in top 10, fetch their balance separately
        if not user_in_top:
            # Assuming get_leaderboard can take a user_id to get their balance
            user_balance = next((bal for uid, bal in get_leaderboard() if uid == user_id), None)
            if user_balance is None:
                user_balance = 0

        embed.set_footer(text=f"Your balance: {user_balance:,}")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="urban", description="Returns the requested word from the urban dictionary")
    async def urban(self, interaction: discord.Interaction, word: str):
        urban_dict = UrbanDict()
        try:
            definition = urban_dict[word]
            # Format as a Google search result
            embed = discord.Embed(
                title=f"{word} - Urban Dictionary",
                description=f"User requested word \"{word}\"",
                color=0x3498db
            )
            embed.add_field(
                name="Definition",
                value=f"**{word}**: {definition}",
                inline=False
            )
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            await interaction.response.send_message(f"❌ **Error fetching definition:** {str(e)}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Fun(bot))
