import discord
from discord.ext import tasks
import os
import json
import math
import asyncio
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# --- Configurações ---
TOKEN = os.getenv("TOKEN")
DEFAULT_MAX = 100 
RECHARGE_MINUTES = 30
DATA_FILE = "data.json"
BRASILIA = ZoneInfo("America/Sao_Paulo")

def load_data():
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

def create_panel_embed(user_limit):
    embed = discord.Embed(
        title="🎒 Mystery Dungeon - Energia",
        description=(
            f"Seu limite atual é: **{user_limit}**\n\n"
            "⚡ **Atualizar Energia:** Registra sua energia atual.\n"
            "🔍 **Ver Status:** Verifica o progresso da recarga.\n"
            "⚙️ **Alterar Limite:** Muda o seu limite máximo (Upgrades)."
        ),
        color=discord.Color.gold()
    )
    return embed

# --- Modal: Alterar Limite Máximo ---
class LimitModal(discord.ui.Modal, title='⚙️ Alterar Limite de Energia'):
    limit_input = discord.ui.TextInput(
        label='Qual o seu limite máximo agora?',
        placeholder='Ex: 120, 150...',
        min_length=1,
        max_length=3,
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            new_limit = int(self.limit_input.value)
            user_id = str(interaction.user.id)
            data = load_data()
            
            user_data = data.get(user_id, {})
            if isinstance(user_data, str): user_data = {}
            
            user_data["max"] = new_limit
            data[user_id] = user_data
            save_data(data)

            await interaction.response.send_message(f"✅ Seu limite foi atualizado para **{new_limit}**!", ephemeral=True)
            await interaction.channel.send(embed=create_panel_embed(new_limit), view=EnergyView())
        except ValueError:
            await interaction.response.send_message("❌ Use apenas números.", ephemeral=True)

# --- Modal: Atualizar Energia Atual ---
class EnergyModal(discord.ui.Modal):
    def __init__(self, user_limit):
        super().__init__(title="⚡ Atualizar Energia")
        self.user_limit = user_limit
        self.energy_input = discord.ui.TextInput(
            label=f'Energia atual (0 a {user_limit})',
            placeholder=f'Digite quanto você tem agora...',
            min_length=1,
            max_length=3,
        )
        self.add_item(self.energy_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            current = int(self.energy_input.value)
            user_id = str(interaction.user.id)
            data = load_data()

            if current >= self.user_limit:
                data[user_id] = {"status": "FULL", "max": self.user_limit}
                await interaction.response.send_message(f"✅ Energia cheia ({current}/{self.user_limit})!", ephemeral=True)
            else:
                missing = self.user_limit - current
                minutes_needed = missing * RECHARGE_MINUTES
                finish_time = datetime.now(timezone.utc) + timedelta(minutes=minutes_needed)
                data[user_id] = {"finish": finish_time.isoformat(), "max": self.user_limit}
                
                finish_br = finish_time.astimezone(BRASILIA)
                await interaction.response.send_message(
                    f"⚡ Registrado: **{current}/{self.user_limit}**\n⏰ Cheia às: `{finish_br.strftime('%H:%M')}`", 
                    ephemeral=True
                )
            
            save_data(data)
            await interaction.channel.send(embed=create_panel_embed(self.user_limit), view=EnergyView())
        except ValueError:
            await interaction.response.send_message("❌ Use apenas números.", ephemeral=True)

# --- View com 3 Botões ---
class EnergyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Ver Status", style=discord.ButtonStyle.primary, emoji="🔍", custom_id="btn_status")
    async def status_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_data()
        user_data = data.get(str(interaction.user.id), {"max": DEFAULT_MAX})
        if isinstance(user_data, str): user_data = {"status": "FULL", "max": DEFAULT_MAX}
        
        limit = user_data.get("max", DEFAULT_MAX)

        if "finish" not in user_data and user_data.get("status") != "FULL":
            await interaction.response.send_message(f"👋 Sem recarga ativa. Seu limite é **{limit}**.", ephemeral=True)
        elif user_data.get("status") == "FULL":
            await interaction.response.send_message(f"🔋 Energia cheia: **{limit}/{limit}**.", ephemeral=True)
        else:
            finish_time = datetime.fromisoformat(user_data["finish"])
            now = datetime.now(timezone.utc)
            if now >= finish_time:
                await interaction.response.send_message(f"✨ Energia completada: **{limit}/{limit}**!", ephemeral=True)
            else:
                minutes_left = (finish_time - now).total_seconds() / 60
                current = math.floor(limit - (minutes_left / RECHARGE_MINUTES))
                await interaction.response.send_message(f"⚡ Status: **{current}/{limit}**", ephemeral=True)
        
        await interaction.channel.send(embed=create_panel_embed(limit), view=EnergyView())

    @discord.ui.button(label="Atualizar Energia", style=discord.ButtonStyle.success, emoji="⚡", custom_id="btn_update")
    async def update_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_data()
        user_data = data.get(str(interaction.user.id), {"max": DEFAULT_MAX})
        limit = user_data.get("max", DEFAULT_MAX) if isinstance(user_data, dict) else DEFAULT_MAX
        await interaction.response.send_modal(EnergyModal(limit))

    @discord.ui.button(label="Alterar Limite", style=discord.ButtonStyle.secondary, emoji="⚙️", custom_id="btn_limit")
    async def limit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(LimitModal())

# --- Bot e Tasks ---
class MyBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)

    async def setup_hook(self):
        self.add_view(EnergyView())
        check_energy.start()

client = MyBot()

@client.event
async def on_message(message):
    if message.author.bot or not isinstance(message.channel, discord.DMChannel): return
    data = load_data()
    user_limit = data.get(str(message.author.id), {"max": DEFAULT_MAX}).get("max", DEFAULT_MAX) if isinstance(data.get(str(message.author.id)), dict) else DEFAULT_MAX
    await message.channel.send(embed=create_panel_embed(user_limit), view=EnergyView())

@tasks.loop(seconds=10)
async def check_energy():
    data = load_data()
    now = datetime.now(timezone.utc)
    changed = False
    for user_id, user_data in list(data.items()):
        if isinstance(user_data, dict) and "finish" in user_data:
            if now >= datetime.fromisoformat(user_data["finish"]):
                try:
                    user = await client.fetch_user(int(user_id))
                    limit = user_data.get("max", DEFAULT_MAX)
                    await user.send(f"⚡ **Sua energia chegou em {limit}!** Hora de Mystery Dungeon! 🎮")
                    await user.send(embed=create_panel_embed(limit), view=EnergyView())
                    data[user_id] = {"status": "FULL", "max": limit}
                    changed = True
                except: pass
    if changed: save_data(data)

client.run(TOKEN)
