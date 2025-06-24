import sqlite3
import shutil
import os
import logging
import asyncio
import sys
from functools import wraps

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

def log_db_call(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        logging.info(f"ECON DB CALL: {func.__name__} called with args={args}, kwargs={kwargs}")
        return func(*args, **kwargs)
    return wrapper

logging.info("Economy DB Logging begin")

# Get the absolute path to the directory where this file is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Ensure 'data' directory exists relative to this file
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# Paths for databases (relative to script location)
ECONOMY_DB_PATH = os.path.join(DATA_DIR, "economy.db")

SHOP_ITEMS = [
    {"id": 1, "name": "Bragging Rights", "price": 10000, "effect": "Nothing. Just flex.", "uses_left": 1},
    {"id": 2, "name": "Financial Drain", "price": 5000, "effect": "Drains one percent of your balance per hour, I wonder where that money goes..", "uses_left": 1},
    {"id": 3, "name": "Bolt Cutters", "price": 3000, "effect": "Improves robbery success", "uses_left": 4},
    {"id": 4, "name": "Padlocked Wallet", "price": 2000, "effect": "Protects against robbery", "uses_left": 10},
    {"id": 5, "name": "Taser", "price": 3500, "effect": "Stuns robbers", "uses_left": 2},
    {"id": 6, "name": "Lucky Coin", "price": 1500, "effect": "Boosts gambling odds.. or just a really expensive paperweight", "uses_left": 4},
    {"id": 7, "name": "VIP Pass", "price": 50000, "effect": "Grants VIP access", "uses_left": 1},
    {"id": 8, "name": "Hackatron 9900", "price": 7000, "effect": "Increases heist efficiency", "uses_left": 5},
    {"id": 9, "name": "Resintantoinem Sample", "price": 4000, "effect": "Probaably a bad idea, increases heist efficiency but once effect wears off you'll be more susceptible", "uses_left": 1},
    {"id": 10, "name": "Loaded Gun", "price": 9000, "effect": "You remembered your 2nd amendment rights, self defense agaist robbers", "uses_left": 19},
    {"id": 11, "name": "Watermelon", "price": 500, "effect": "Doctors approve! Does nothing", "uses_left": 500},
]

# Connect to economy.db (for user balances and everything)
econ_conn = sqlite3.connect(ECONOMY_DB_PATH)
econ_cursor = econ_conn.cursor()

# Create tables if they don't exist

econ_cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT NOT NULL,
    balance INTEGER NOT NULL DEFAULT 0
)
""")

# god why the fuck am i making 2 tables, this is shit.
# fuck you that's why.
# User items table (tracks owned items & uses)
econ_cursor.execute("""
CREATE TABLE IF NOT EXISTS user_items (
    user_id INTEGER,
    item_id TEXT,
    item_name TEXT NOT NULL,
    uses_left INTEGER DEFAULT 0,
    effect_modifier INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, item_id)
)
""")

# Financial drain table (tracks deducted money)
econ_cursor.execute("""
CREATE TABLE IF NOT EXISTS financial_drain (
    user_id INTEGER PRIMARY KEY,
    drained_amount INTEGER DEFAULT 0
)
""")

# Commit table creations
econ_conn.commit()

@log_db_call
def modify_robber_multiplier(user_id, change, duration=None):
    """Modifies the user's robbery success/failure rate"""
    current_modifier = get_robbery_modifier(user_id)  # Get current modifier
    new_modifier = max(min(current_modifier + change, 100), -100)  # Cap between -100% and +100%

    # Update the database
    econ_cursor.execute("UPDATE user_items SET effect_modifier = ? WHERE user_id = ?",
                        (new_modifier, user_id))
    econ_conn.commit()

    logging.info(f"Updated robbery modifier for {user_id}: {new_modifier}%")

    # If it's temporary (like Resin Sample), schedule decay
    if duration:
        asyncio.create_task(schedule_effect_decay(user_id, current_modifier, duration))

@log_db_call
def get_robbery_modifier(user_id):
    """Gets the total robbery modifier for a user (from items)"""
    econ_cursor.execute("SELECT SUM(effect_modifier) FROM user_items WHERE user_id = ?", (user_id,))
    result = econ_cursor.fetchone()
    return result[0] if result and result[0] else 0  # Default to 0 modifier

@log_db_call
async def schedule_effect_decay(user_id, original_value, duration):
    """Waits for the effect duration to expire and then reverts the modifier"""
    await asyncio.sleep(duration)  # Wait X seconds
    econ_cursor.execute("UPDATE user_items SET effect_modifier = ? WHERE user_id = ?",
                        (original_value, user_id))
    econ_conn.commit()

    logging.info(f"Restored robbery modifier for {user_id} to {original_value}%")

# ----------- Economy Functions -----------

@log_db_call
def update_balance(user_id, amount):
    """ Updates user balance and syncs to backup """
    logging.info(f"Updating balance for {user_id}: {amount} coins")
    econ_cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    econ_conn.commit()

@log_db_call
def get_balance(user_id):
    """ Fetches user balance """
    logging.info(f"Getting balance for {user_id}")
    econ_cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    result = econ_cursor.fetchone()
    return result[0] if result else 0

@log_db_call
def add_user(user_id, username):
    """ Adds a user to the economy database if they don't exist """
    logging.info(f"Adding user {user_id} in economy database, {username}")
    econ_cursor.execute("INSERT OR IGNORE INTO users (user_id, username, balance) VALUES (?, ?, 0)", (user_id, username))
    econ_conn.commit()

# ----------- Item Handling Functions -----------

@log_db_call
def add_user_item(user_id, item_id, item_name, uses_left=1, effect_modifier=0):
    """ Adds an item to the user's inventory """
    logging.info(f"Adding item {item_name} (ID: {item_id}) to {user_id}'s inventory")
    econ_cursor.execute("""
        INSERT INTO user_items (user_id, item_id, item_name, uses_left, effect_modifier) 
        VALUES (?, ?, ?, ?, ?) 
        ON CONFLICT(user_id, item_id) DO UPDATE 
        SET uses_left = uses_left + ?""",
        (user_id, item_id, item_name, uses_left, effect_modifier, uses_left)
    )
    econ_conn.commit()

@log_db_call
def get_user_items(user_id):
    """ Fetches all items a user owns """
    econ_cursor.execute("SELECT item_id, item_name, uses_left FROM user_items WHERE user_id = ?", (user_id,))
    items = econ_cursor.fetchall()

    return [{"item_id": row[0], "item_name": row[1], "uses_left": row[2]} for row in items] if items else []

@log_db_call
def use_item(user_id, item_id):
    """ Decreases item uses left by 1 if it has remaining uses """
    logging.info(f"User {user_id} is using item {item_id}")
    econ_cursor.execute("UPDATE user_items SET uses_left = uses_left - 1 WHERE user_id = ? AND item_id = ? AND uses_left > 0",
                        (user_id, item_id))
    econ_conn.commit()

@log_db_call
def remove_item_from_user(user_id, item_id):
        """Removes an item completely from the user's inventory."""
        econ_cursor.execute("DELETE FROM user_items WHERE user_id = ? AND item_id = ?", (user_id, item_id))
        econ_conn.commit()

@log_db_call
def update_item_uses(user_id, item_id, uses_left):
        """Updates the number of uses left for a user's item."""
        econ_cursor.execute("UPDATE user_items SET uses_left = ? WHERE user_id = ? AND item_id = ?", (uses_left, user_id, item_id))
        econ_conn.commit()

@log_db_call
def add_item_to_user(user_id, item_id, item_name, uses_left=1, effect_modifier=0):
        """Adds an item to the user's inventory or updates uses if it exists."""
        econ_cursor.execute("""
            INSERT INTO user_items (user_id, item_id, item_name, uses_left, effect_modifier)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, item_id) DO UPDATE SET uses_left = user_items.uses_left + ?
        """, (user_id, item_id, item_name, uses_left, effect_modifier, uses_left))
        econ_conn.commit()

# ----------- Shop Functions -----------

@log_db_call
def buy_item(user_id, item_id, item_name, price, uses_left=1, effect_modifier=0):
    """Buys an item from the shop and deducts balance, using sqlite3 for all operations."""
    logging.info(f"User {user_id} is buying {item_name} for {price} coins")

    # Check if user exists
    econ_cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    user = econ_cursor.fetchone()
    if not user:
        return False  # User does not exist

    current_balance = user[0]
    if current_balance < price:
        return False  # Not enough money

    # Deduct balance
    econ_cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (price, user_id))

    # Add or update item in inventory
    econ_cursor.execute("""
        INSERT INTO user_items (user_id, item_id, item_name, uses_left, effect_modifier)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id, item_id) DO UPDATE SET uses_left = user_items.uses_left + ?
    """, (user_id, item_id, item_name, uses_left, effect_modifier, uses_left))

    econ_conn.commit()
    return True


# ----------- Special Item Effects -----------

@log_db_call
def use_item(user_id, item_id):
    """Handles item use and applies effects dynamically."""
    # Fetch user items
    econ_cursor.execute("SELECT uses_left FROM user_items WHERE user_id = ? AND item_id = ?", (user_id, item_id))
    result = econ_cursor.fetchone()
    
    if not result:
        return f"❌ You don't have this item!"

    uses_left = result[0]
    if uses_left <= 0:
        return f"❌ You have no uses left for this item!"

    # Fetch item details from hardcoded shop list
    item_data = next((item for item in SHOP_ITEMS if item["id"] == item_id), None)
    if not item_data:
        return f"❌ Item does not exist!"

    # Handle last use case
    last_use_warning = ""
    if uses_left == 1:
        last_use_warning = f"⚠️ **This is the last use of your {item_data['name']}!**\n"

    # Define item effects dynamically
    item_effects = {
        1: {"robbery_modifier": 0, "uses": 1},        # Bragging Rights: no effect, 1 use
        2: {"robbery_modifier": 20, "uses": 3},      # Robber's Mask: +20% robbery, 3 uses
        3: {"robbery_modifier": 50, "uses": 4},      # Bolt Cutters: +50% robbery, 4 uses
        4: {"robbery_modifier": -40, "uses": 10},    # Padlocked Wallet: -40% robbery, 10 uses
        5: {"robbery_modifier": -90, "taser": True, "uses": 2},               # Taser: blocks robbery, 2 uses
        6: {"Gambling_odds_mul": 0, "uses": 4},      # Lucky coin: placebo effect goes insane, 4 uses
        8: {"robbery_modifier": 75, "uses": 5},      # Hackatron 9900™: +75% robbery, 5 uses
        9: {  # Resin Sample: +100% robbery, then -40% after effect wears off
            "robbery_modifier": 100,
            "temporary_effect": -40,
            "duration": 3600,  # 1 hour in seconds
            "uses": 1
        },
        10: {"gun_defense": True, "uses": 8},        # Loaded Gun: blocks robbery, 8 uses
        11: {"uses": 500}                            # Watermelon: no effect, 500 uses
    }

    # SHOP_ITEMS
    #    {"id": 1, "name": "Bragging Rights", "price": 10000, "effect": "Nothing. Just flex.", "uses_left": 1},
    #    {"id": 2, "name": "Robber's Mask", "price": 5000, "effect": "Increases robbery success", "uses_left": 3},
    #    {"id": 3, "name": "Bolt Cutters", "price": 3000, "effect": "Improves robbery success", "uses_left": 4},
    #    {"id": 4, "name": "Padlocked Wallet", "price": 2000, "effect": "Protects against robbery", "uses_left": 10},
    #    {"id": 5, "name": "Taser", "price": 3500, "effect": "Stuns robbers", "uses_left": 2},
    #    {"id": 6, "name": "Lucky Coin", "price": 1500, "effect": "Boosts gambling odds.. or just a really expensive paperweight", "uses_left": 4},
    #    {"id": 7, "name": "VIP Pass", "price": 50000, "effect": "Grants VIP access", "uses_left": 1},
    #    {"id": 8, "name": "Hackatron 9900™", "price": 7000, "effect": "Increases heist efficiency", "uses_left": 5},
    #    {"id": 9, "name": "Resintantoinem Sample", "price": 4000, "effect": "Probaably a bad idea, increases heist efficiency but once effect wears off you'll be more susceptible", "uses_left": 1},
    #    {"id": 10, "name": "Loaded Gun", "price": 9000, "effect": "You remembered your 4th amendment rights, self defense agaist robbers", "uses_left": 19},
    #    {"id": 11, "name": "Watermelon", "price": 500, "effect": "Doctors approve! Does nothing", "uses_left": 500},

    # Apply effect if item has one
    effect_applied = ""
    if item_id in item_effects:
        effect_data = item_effects[item_id]

        # Apply Robbery Modifiers
        if "robbery_modifier" in effect_data:
            modify_robber_multiplier(user_id, effect_data["robbery_modifier"])
            effect_applied = f"🔧 **Your robbery success rate changed by {effect_data['robbery_modifier']}%!**"

        # Apply temporary effects (like Resin Sample)
        if "temporary_effect" in effect_data:
            schedule_effect_decay(user_id, effect_data["temporary_effect"])

        # Apply defensive effects
        if "taser" in effect_data:
            modify_robber_multiplier(user_id, effect_data["robbery_modifier"])
            effect_applied = "⚡ **You are now protected from robbery for one attempt!**"
        
        if "gun_defense" in effect_data:
            effect_applied = "🔫 **You are armed. Good luck, robber.**"

    # Reduce item uses
    econ_cursor.execute("UPDATE user_items SET uses_left = uses_left - 1 WHERE user_id = ? AND item_id = ?", (user_id, item_id))
    econ_conn.commit()

    return f"{last_use_warning}✅ **You used {item_data['name']}!** {effect_applied}"

@log_db_call
def check_gun_defense(victim_id):
    econ_cursor.execute("SELECT uses_left FROM user_items WHERE user_id = ? AND item_id = 10", (victim_id,))
    result = econ_cursor.fetchone()
    return result[0] if result and result[0] > 0 else 0

@log_db_call
def decrement_gun_use(victim_id):
    econ_cursor.execute("UPDATE user_items SET uses_left = uses_left - 1 WHERE user_id = ? AND item_id = 10 AND uses_left > 0", (victim_id,))
    econ_conn.commit()
