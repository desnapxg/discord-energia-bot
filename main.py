import discord
from discord.ext import tasks
import os
import json
from datetime import datetime, timedelta

TOKEN = os.getenv("TOKEN")

MAX_ENERGY = 100
RECHARGE_MINUTES = 30
DATA_FILE = "data.json"

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

def load_data():
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

@client.event
async def on_ready():
    print(f"Bot online como {client.user}")
    check_energy.start()

@client.event
async def on_message(message):
    if message.author.bot:
        return

    if isinstance(message.channel, discord.DMChannel):

        try:
            current_energy = int(message.content.strip())
        except:
            await message.channel.send("Envie apenas o número da sua energia atual. Ex: 0 ou 45")
            return

        if current_energy >= MAX_ENERGY:
            await message.channel.send("Sua energia já está cheia.")
            return

        missing = MAX_ENERGY - current_energy
        minutes_needed = missing * RECHARGE_MINUTES
        finish_time = datetime.utcnow() + timedelta(minutes=minutes_needed)

        data = load_data()
        data[str(message.author.id)] = finish_time.isoformat()
        save_data(data)

        await message.channel.send(
            f"Energia registrada.\n"
            f"Faltam {missing} energias.\n"
            f"Vai encher em aproximadamente {minutes_needed} minutos."
        )

@tasks.loop(minutes=1)
async def check_energy():
    data = load_data()
    now = datetime.utcnow()

    for user_id in list(data.keys()):
        finish_time = datetime.fromisoformat(data[user_id])

        if now >= finish_time:
            user = await client.fetch_user(int(user_id))
            await user.send("🔋 Sua energia está cheia (100)!")
            del data[user_id]
            save_data(data)

client.run(TOKEN)
