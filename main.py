import discord
from discord.ext import tasks
import os
import json
import math
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# --- Configurações ---
TOKEN = os.getenv("TOKEN")
MAX_ENERGY = 100
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

# --- Modal para Digitar a Energia ---
class EnergyModal(discord.ui.Modal, title='Atualizar Energia'):
    energy_input = discord.ui.TextInput(
        label='Qual sua energia atual?',
        placeholder='Digite um número (ex: 45)',
        min_length=1,
        max_length=2,
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            current_energy = int(self.energy_input.value)
            if current_energy >= MAX_ENERGY:
                await interaction.response.send_message("✅ Sua energia já está cheia!", ephemeral=True)
                return

            missing = MAX_ENERGY - current_energy
            minutes_needed = missing * RECHARGE_MINUTES
            finish_time = datetime.now(timezone.utc) + timedelta(minutes=minutes_needed)

            data = load_data()
            data[str(interaction.user.id)] = finish_time.isoformat()
            save_data(data)

            finish_br = finish_time.astimezone(BRASILIA)
            await interaction.response.send_message(
                f"⚡ **Energia registrada: {current_energy}**\n"
                f"🔋 Cheia às: `{finish_br.strftime('%H:%M - %d/%m/%Y')}`", 
                ephemeral=True
            )
        except ValueError:
            await interaction.response.send_message("❌ Erro: Digite apenas números inteiros.", ephemeral=True)

# --- View com Botões Persistentes ---
class EnergyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None) # Isso impede que os botões expirem

    @discord.ui.button(label="Ver Status", style=discord.ButtonStyle.primary, emoji="📊", custom_id="btn_status")
    async def status_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_data()
        user_id = str(interaction.user.id)

        if user_id not in data:
            await interaction.response.send_message("❌ Nenhum contador ativo para você.", ephemeral=True)
            return

        finish_time = datetime.fromisoformat(data[user_id])
        now = datetime.now(timezone.utc)

        if now >= finish_time:
            await interaction.response.send_message("🔋 Sua energia atual é **100**.\nSua energia já está cheia!", ephemeral=True)
            return

        time_left = finish_time - now
        minutes_left = time_left.total_seconds() / 60
        current_energy = math.floor(MAX_ENERGY - (minutes_left / RECHARGE_MINUTES))
        finish_br = finish_time.astimezone(BRASILIA)

        await interaction.response.send_message(
            f"⚡ Sua energia atual é **{current_energy}**.\n"
            f"⌛ Ficará cheia às: `{finish_br.strftime('%H:%M - %d/%m/%Y')}`",
            ephemeral=True
        )

    @discord.ui.button(label="Atualizar Energia", style=discord.ButtonStyle.success, emoji="⚡", custom_id="btn_update")
    async def update_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(EnergyModal())

# --- Classe do Bot ---
class MyBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)

    async def setup_hook(self):
        # Isso faz o bot "lembrar" dos botões mesmo se ele reiniciar
        self.add_view(EnergyView())
        if not check_energy.is_running():
            check_energy.start()

    async def on_ready(self):
        print(f"✅ Bot online: {self.user}")

client = MyBot()

@client.event
async def on_message(message):
    if message.author.bot:
        return

    if message.content.lower() == "!painel":
        embed = discord.Embed(
            title="🎮 Mystery Dungeon - Energia",
            description="Clique nos botões abaixo para gerenciar sua recarga.",
            color=discord.Color.green()
        )
        # Enviamos a mensagem com a View
        await message.channel.send(embed=embed, view=EnergyView())

@tasks.loop(minutes=1)
async def check_energy():
    data = load_data()
    now = datetime.now(timezone.utc)
    changed = False

    for user_id in list(data.keys()):
        finish_time = datetime.fromisoformat(data[user_id])
        if now >= finish_time:
            try:
                user = await client.fetch_user(int(user_id))
                await user.send("🔥 **Energia cheia!** Hora de entrar no Mystery Dungeon!")
                del data[user_id]
                changed = True
            except:
                pass

    if changed:
        save_data(data)

client.run(TOKEN)
