import discord
import os
import asyncio
from datetime import datetime, timedelta

TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

client = discord.Client(intents=intents)

MAX_ENERGY = 100
RECHARGE_MINUTES = 30

user_energy = {}
user_task = {}

async def start_timer(user):
    while user_energy[user.id] < MAX_ENERGY:
        await asyncio.sleep(RECHARGE_MINUTES * 60)
        user_energy[user.id] += 1

    await user.send("🔋 Sua energia está cheia (100)!")

@client.event
async def on_ready():
    print(f"Bot online como {client.user}")

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if isinstance(message.channel, discord.DMChannel):
        content = message.content.lower()

        if content.startswith("gastei"):
            user_energy[message.author.id] = 0
            await message.channel.send("Energia resetada para 0. Vou avisar quando chegar em 100 🔄")

            if message.author.id in user_task:
                user_task[message.author.id].cancel()

            task = asyncio.create_task(start_timer(message.author))
            user_task[message.author.id] = task

client.run(TOKEN)
