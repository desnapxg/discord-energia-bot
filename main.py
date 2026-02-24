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
        content = message.content.lower().strip()
        data = load_data()

        # STATUS COMMAND
        if content == "status":
            if str(message.author.id) not in data:
                await message.channel.send("Nenhum contador ativo. Envie sua energia atual.")
                return

            finish_time = datetime.fromisoformat(data[str(message.author.id)])
            now = datetime.utcnow()

            if now >= finish_time:
                await message.channel.send("🔋 Sua energia já está cheia!")
                return

            remaining_time = finish_time - now
            minutes_left = int(remaining_time.total_seconds() / 60)
            energy_left = minutes_left // RECHARGE_MINUTES
            current_energy = MAX_ENERGY - energy_left

            await message.channel.send(
                f"⚡ Energia atual estimada: {current_energy}\n"
                f"Faltam aproximadamente {minutes_left} minutos.\n"
                f"Vai encher às {finish_time.strftime('%H:%M')} (UTC)."
            )
            return

        # NUMBER INPUT
        try:
            current_energy = int(content)
        except:
            await message.channel.send("Envie um número (ex: 0 ou 45) ou digite 'status'.")
            return

        if current_energy >= MAX_ENERGY:
            await message.channel.send("Sua energia já está cheia.")
            return

        missing = MAX_ENERGY - current_energy
        minutes_needed = missing * RECHARGE_MINUTES
        finish_time = datetime.utcnow() + timedelta(minutes=minutes_needed)

        data[str(message.author.id)] = finish_time.isoformat()
        save_data(data)

        await message.channel.send(
            f"⚡ Energia registrada: {current_energy}\n"
            f"Faltam {missing} energias.\n"
            f"⏳ Vai encher às {finish_time.strftime('%H:%M')} (UTC).\n"
            f"Aproximadamente {minutes_needed} minutos."
        )

@tasks.loop(minutes=1)
async def check_energy():
    data = load_data()
    now = datetime.utcnow()

    for user_id in list(data.keys()):
        finish_time = datetime.fromisoformat(data[user_id])

        if now >= finish_time:
            user = await client.fetch_user(int(user_id))
            await user.send("🔥 Energia cheia! Hora de fazer Mistery Dungeon!")
            del data[user_id]
            save_data(data)

client.run(TOKEN)
