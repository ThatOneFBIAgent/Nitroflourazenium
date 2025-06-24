import discord
import time
import random
import re
import asyncio
import math
from discord.ext import commands
from discord import app_commands
from discord import Interaction
import io
import aiohttp
# from pylatex import Document, Math, NoEscape
# from pylatex.utils import escape_latex
# from matplotlib import pyplot as plt

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

    # 🎲 ADVANCED DICE ROLLER 🎲
    @app_commands.command(name="roll", description="Roll dice with advanced options (exploding, keep/drop, modifiers).")
    async def roll(self, interaction: discord.Interaction, dice: str):
        # Regex pattern for dice: Xd!Y, Xd!!Y, Xd!Y+Z, XdYkN, XdYdN, etc.
        pattern = re.compile(
            r"(?P<num>\d+)[dD](?P<explode>!?|!!|!\?)?(?P<sides>\d+)"
            r"(?P<keepdrop>[kdKD]\d+)?"
            r"(?P<modifiers>(?:[&+-]\d+)*)"
        )
        match = pattern.fullmatch(dice.replace(" ", ""))

        if not match:
            await interaction.response.send_message(
                "❌ **Invalid format!** Use `XdY`, `Xd!Y`, `Xd!!Y`, `XdYkN`, `XdYdN`, `XdY+Z`, etc. Examples: `2d6`, `3d!10+5`, `4d8k2+3`, `5d6!!d2-1`.",
                ephemeral=False
            )
            return

        num_dice = int(match.group("num"))
        die_sides = int(match.group("sides"))
        explode_flag = match.group("explode") or ""
        keepdrop = match.group("keepdrop")
        modifiers = match.group("modifiers") or ""

        if num_dice > MAX_DICE or die_sides > MAX_SIDES:
            await interaction.response.send_message(
                f"❌ **Too many dice!** Limit: `{MAX_DICE}d{MAX_SIDES}`.",
                ephemeral=False
            )
            return

        # Exploding dice logic
        def roll_die(sides):
            return random.randint(1, sides)

        def explode_once(rolls, sides, compound=False, show_all=False, depth=0, max_depth=10):
            """Handles single or compounding explosions, returns (final_rolls, all_rolls_for_display)"""
            if depth >= max_depth:
                return rolls, rolls if show_all else [sum(rolls)]
            new_rolls = []
            all_rolls = []
            for roll in rolls:
                if roll == sides:
                    if compound:
                        # Compound: keep rolling and sum all
                        chain = [roll]
                        while True:
                            if len(chain) > max_depth:
                                break
                            next_roll = roll_die(sides)
                            chain.append(next_roll)
                            if next_roll != sides:
                                break
                        new_rolls.append(sum(chain))
                        if show_all:
                            all_rolls.append(chain)
                        else:
                            all_rolls.append([sum(chain)])
                    else:
                        # Normal explode: roll again and add to pool
                        chain = [roll]
                        for _ in range(max_depth):
                            next_roll = roll_die(sides)
                            chain.append(next_roll)
                            if next_roll != sides:
                                break
                        new_rolls.extend(chain)
                        if show_all:
                            all_rolls.append(chain)
                        else:
                            all_rolls.extend(chain)
                else:
                    new_rolls.append(roll)
                    if show_all:
                        all_rolls.append([roll])
                    else:
                        all_rolls.append(roll)
            if compound or show_all:
                # Only one pass needed for compound or show_all
                return new_rolls, all_rolls
            # For normal explode, check for further explosions recursively
            if any(r == sides for r in new_rolls):
                return explode_once(new_rolls, sides, compound, show_all, depth + 1, max_depth)
            return new_rolls, all_rolls

        # Roll initial dice
        rolls = [roll_die(die_sides) for _ in range(num_dice)]
        all_rolls_for_display = [ [r] for r in rolls ]
        mod_details = []
        explosion_type = None

        # Handle explosion flags
        if explode_flag:
            if explode_flag == "!":
                explosion_type = "normal"
                rolls, all_rolls_for_display = explode_once(rolls, die_sides, compound=False, show_all=False)
                mod_details.append("Exploding dice: normal (!)")
            elif explode_flag == "!!":
                explosion_type = "compound"
                rolls, all_rolls_for_display = explode_once(rolls, die_sides, compound=True, show_all=False)
                mod_details.append("Exploding dice: compounding (!!)")
            elif explode_flag == "!?":
                explosion_type = "showall"
                _, all_rolls_for_display = explode_once(rolls, die_sides, compound=False, show_all=True)
                # Flatten for result, but keep all for display
                rolls = [sum(chain) for chain in all_rolls_for_display]
                mod_details.append("Exploding dice: show all rolls (!?)")

        # Handle keep/drop
        kept = None
        dropped = None
        if keepdrop:
            kd = keepdrop.lower()
            if kd.startswith("k"):
                k = int(kd[1:])
                kept = sorted(rolls, reverse=True)[:k]
                mod_details.append(f"Keep highest {k} (k{k})")
            elif kd.startswith("d"):
                d = int(kd[1:])
                dropped = sorted(rolls)[:d]
                mod_details.append(f"Drop lowest {d} (d{d})")

        # Apply modifiers (including & for partial application)
        results = rolls[:]
        if modifiers:
            mods = re.findall(r"([&+-]\d+)", modifiers)
            i = 0
            while i < len(mods):
                mod = mods[i]
                if mod.startswith("&"):
                    try:
                        count = int(mod[1:])
                        if i + 1 < len(mods):
                            next_mod = mods[i + 1]
                            if next_mod.startswith("+") or next_mod.startswith("-"):
                                flat_mod = int(next_mod)
                                results = [r + flat_mod if idx < count else r for idx, r in enumerate(results)]
                                mod_details.append(f"First {count} Rolls: `{flat_mod}`")
                                i += 2
                                continue
                    except ValueError:
                        await interaction.response.send_message(
                            "❌ **Invalid & modifier!** Must be an integer.",
                            ephemeral=False
                        )
                        return
                elif mod.startswith("+") or mod.startswith("-"):
                    try:
                        flat_mod = int(mod)
                        results = [r + flat_mod for r in results]
                        mod_details.append(f"All Rolls: `{flat_mod}`")
                    except ValueError:
                        await interaction.response.send_message(
                            "❌ **Invalid modifier!** Modifiers must be integers.",
                            ephemeral=False
                        )
                        return
                i += 1

        # Prepare display text
        def format_all_rolls(all_rolls):
            # For showall, display each chain
            out = []
            for chain in all_rolls:
                if isinstance(chain, list) and len(chain) > 1:
                    out.append(" + ".join(map(str, chain)))
                else:
                    out.append(str(chain[0]) if isinstance(chain, list) else str(chain))
            return ", ".join(out)

        rolls_text = (
            format_all_rolls(all_rolls_for_display)
            if explosion_type == "showall"
            else ", ".join(map(str, rolls))
        )
        final_text = ", ".join(map(str, results))

        # Show keep/drop results
        if kept is not None:
            kept_text = ", ".join(map(str, kept))
            mod_details.append(f"Kept: `{kept_text}`")
        if dropped is not None:
            dropped_text = ", ".join(map(str, dropped))
            mod_details.append(f"Dropped: `{dropped_text}`")

        mod_text = "\n".join(mod_details) if mod_details else "No modifiers applied"

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

    @app_commands.command(name="hack", description="Hack another user! Totally 100% legit.")
    async def hack(self, interaction: discord.Interaction, target: discord.Member):
        if target == interaction.user:
            return await interaction.response.send_message("❌ You can't hack yourself!", ephemeral=True)

        # Simulate hacking process with an elaborate "animation" and rising percentage
        message = await interaction.response.send_message(f"💻 Hacking {target.mention}... Please wait...")

        steps = [
            "Bypassing firewall...",
            "Accessing mainframe...",
            "Decrypting passwords...",
            "Extracting data...",
            "Uploading virus...",
            "Finalizing hack..."
        ]
        total_steps = len(steps)
        percent_per_step = 100 // (total_steps + 1)
        progress = 0

        # Get the message object to edit
        msg = await interaction.original_response()

        for i, step in enumerate(steps):
            progress += percent_per_step
            bar = "█" * (progress // 10) + "░" * (10 - (progress // 10))
            await msg.edit(content=f"💻 Hacking {target.mention}...\n[{bar}] {progress}%\n{step}")
            await asyncio.sleep(1.2)

        # Finish at 100%
        await msg.edit(content=f"💻 Hacking {target.mention}...\n[██████████] 100%\n✅ Hack complete! All their cookies have been stolen and eaten!🍪")
    
    @app_commands.command(name="info", description="Get information about the bot.")
    async def info_of_bot(self, interaction: discord.Interaction):
        bot = self.bot.user
        embed = discord.Embed(title=f"Bot Info: {bot.name}", color=0x3498db)
        embed.add_field(name="Bot ID", value=bot.id, inline=False)
        embed.add_field(name="Created By", value=f"Iza Carlos (_izacarlos)", inline=True)
        embed.add_field(name="Created At", value=bot.created_at.strftime("%Y-%m-%d %H:%M:%S"), inline=False)
        embed.add_field(name="Commands", value=len(self.bot.commands), inline=True) # this displays 1, becuase well have to fucking hard code it!
        embed.set_thumbnail(url=bot.avatar.url if bot.avatar else None)

        await interaction.response.send_message(embed=embed)
    # stupid dum dum discord reserves bot_ for their own shit, don't do drugs kids!
    
    @app_commands.command(name="serverinfo", description="Get information about current server")
    async def serverinfo(self, interaction: discord.Interaction, hidden: bool = False):
        guild = interaction.guild
        embed = discord.Embed(
            title=f"{guild.name} Info",
            color=0x5865f2
        )

        # Server icon
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        else:
            embed.set_thumbnail(url=discord.Embed.Empty)

        # Owner
        owner = guild.owner
        if not owner:
            try:
                owner = await self.bot.fetch_user(guild.owner_id)
            except Exception:
                owner = None
        owner_display = owner.mention if owner else f"`{guild.owner_id}`"

        embed.add_field(name="Server ID", value=str(guild.id), inline=False)
        embed.add_field(name="Owner", value=owner_display, inline=True)
        embed.add_field(name="Member Count", value=str(guild.member_count), inline=True)
        embed.add_field(
            name="Created At",
            value=guild.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            inline=False
        )
        embed.add_field(name="Roles", value=str(len(guild.roles)), inline=True)
        embed.add_field(name="Channels", value=str(len(guild.channels)), inline=True)
        embed.add_field(name="Boosts", value=str(getattr(guild, "premium_subscription_count", 0)), inline=True)

        # Member counts
        total_members = guild.member_count
        if hasattr(guild, "members") and guild.members:  # Requires members intent!
            bot_count = sum(1 for m in guild.members if m.bot)
            human_count = total_members - bot_count
        else:
            # Fallback if members intent is not enabled
            bot_count = "?"
            human_count = "?"

        embed.add_field(name="Total Members", value=str(total_members), inline=True)
        embed.add_field(name="Humans", value=str(human_count), inline=True)
        embed.add_field(name="Bots", value=str(bot_count), inline=True)

        # User info (just from interaction.user)
        user = interaction.user
        embed.add_field(
            name=f"Your Info ({user.display_name})",
            value=f"• ID: `{user.id}`\n• Joined: {user.joined_at.strftime('%Y-%m-%d %H:%M:%S') if hasattr(user, 'joined_at') and user.joined_at else 'Unknown'}",
            inline=False
        )

        # Permissions
        user = interaction.user
        if isinstance(user, discord.Member):
            perms = user.guild_permissions
            is_admin = perms.administrator
            is_mod = perms.manage_messages or perms.kick_members or perms.ban_members or perms.manage_guild
            is_owner = user.id == guild.owner_id

            perm_text = []
            if is_owner:
                perm_text.append("Owner")
            elif is_admin:
                perm_text.append("Administrator")
            elif is_mod:
                perm_text.append("Moderator")
            else:
                perm_text.append("Member")

            embed.add_field(
                name="Your Permissions",
                value=", ".join(perm_text),
                inline=True
            )
        else:
            embed.add_field(
                name="Your Permissions",
                value="Unknown (not a guild member)",
                inline=True
            )

        embed.set_footer(text=f"Requested by {user.name} ({user.id})")

        await interaction.response.send_message(embed=embed, ephemeral=hidden)

    
    @app_commands.command(name="letter", description="Generate a random letter.")
    async def letter(self, interaction: discord.Interaction):
        letter = random.choice("abcdefghijklmnopqrstuvwxyz")
        embed = discord.Embed(title="🔤 Random Letter", color=0x3498db)
        embed.add_field(name="Generated Letter", value=f"`{letter}`", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="cat", description="Get a random cat image")
    async def cat(self, interaction: discord.Interaction):

        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.thecatapi.com/v1/images/search") as resp:
                if resp.status != 200:
                    await interaction.response.send_message("😿 Failed to fetch a cat image.", ephemeral=True)
                    return
                data = await resp.json()
                if not data or "url" not in data[0]:
                    await interaction.response.send_message("😿 No cat image found.", ephemeral=True)
                    return
                cat_url = data[0]["url"]
                cat_id = data[0].get("id", "unknown")
                embed = discord.Embed(title="🐱 Random Cat", color=0x3498db)
                embed.set_image(url=cat_url)
                embed.set_footer(text=f"Cat ID: {cat_id}")
                await interaction.response.send_message(embed=embed)

    @app_commands.command(name="dog", description="Get a random dog image")
    async def dog(self, interaction: discord.Interaction):
        async with aiohttp.ClientSession() as session:
            async with session.get("https://dog.ceo/api/breeds/image/random") as resp:
                if resp.status != 200:
                    await interaction.response.send_message("🐶 Failed to fetch a dog image.", ephemeral=True)
                    return
                data = await resp.json()
                if "message" not in data or not data["message"]:
                    await interaction.response.send_message("🐶 No dog image found.", ephemeral=True)
                    return
                dog_url = data["message"]
                embed = discord.Embed(title="🐶 Random Dog", color=0x3498db)
                embed.set_image(url=dog_url)
                await interaction.response.send_message(embed=embed)
    

async def setup(bot):
    await bot.add_cog(Fun(bot))
