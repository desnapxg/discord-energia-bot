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

def create_panel_embed():
    return discord.Embed(
        title="🎮 Mystery Dungeon - Energia",
        description=(
            "Gerencie sua recarga de energia abaixo.\n\n"
            "⚡ **Atualizar Energia:** Registra quanto você tem agora.\n"
            "📊 **Ver Status:** Verifica quanto tempo falta para encher."
        ),
        color=discord.Color.green()
    )

# --- Modal para Digitar a Energia ---
class EnergyModal(discord.ui.Modal, title='Atualizar Energia'):
    energy_input = discord.ui.TextInput(
        label='Qual sua energia atual no jogo?',
        placeholder='Digite de 0 a 100...',
        min_length=1,
        max_length=3,
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            current_energy = int(self.energy_input.value)
            user_id = str(interaction.user.id)
            data = load_data()

            if current_energy >= MAX_ENERGY:
                if user_id in data:
                    del data[user_id]
                    save_data(data)
                
                await interaction.response.send_message(
                    "✅ **Energia total registrada!** Como você já está com 100%, não farei contagem agora.", 
                    ephemeral=True
                )
            else:
                missing = MAX_ENERGY - current_energy
                minutes_needed = missing * RECHARGE_MINUTES
                finish_time = datetime.now(timezone.utc) + timedelta(minutes=minutes_needed)

                data[user_id] = finish_time.isoformat()
                save_data(data)

                finish_br = finish_time.astimezone(BRASILIA)
                await interaction.response.send_message(
                    f"⚡ **Energia registrada: {current_energy}**\n"
                    f"🔋 Sua energia deve completar às: `{finish_br.strftime('%H:%M - %d/%m/%Y')}`", 
                    ephemeral=True
                )
            
            await interaction.channel.send(embed=create_panel_embed(), view=EnergyView())

        except ValueError:
            await interaction.response.send_message("❌ Erro: Por favor, use apenas números.", ephemeral=True)

# --- View com Botões Persistentes ---
class EnergyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Ver Status", style=discord.ButtonStyle.primary, emoji="📊", custom_id="btn_status")
    async def status_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_data()
        user_id = str(interaction.user.id)

        if user_id not in data:
            await interaction.response.send_message(
                "👋 **Eu ainda não estou acompanhando sua recarga.**\n"
                "Para começar, clique em **Atualizar Energia** ⚡ e me diga quanto você tem no jogo agora!", 
                ephemeral=True
            )
        else:
            finish_time = datetime.fromisoformat(data[user_id])
            now = datetime.now(timezone.utc)

            if now >= finish_time:
                await interaction.response.send_message(
                    "🔋 **Energia 100/100!**\n"
                    "Sua barra de energia já deve estar cheia no jogo!", 
                    ephemeral=True
                )
            else:
                time_left = finish_time - now
                minutes_left = time_left.total_seconds() / 60
                current_energy = math.floor(MAX_ENERGY - (minutes_left / RECHARGE_MINUTES))
                finish_br = finish_time.astimezone(BRASILIA)

                await interaction.response.send_message(
                    f"⚡ Sua energia atual deve estar em aproximadamente **{current_energy}**.\n"
                    f"⌛ A recarga completa será às: `{finish_br.strftime('%H:%M - %d/%m/%Y')}`",
                    ephemeral=True
                )
        
        await interaction.channel.send(embed=create_panel_embed(), view=EnergyView())

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
        await message.channel.send(embed=create_panel_embed(), view=EnergyView())

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
                await user.send("🔥 **Energia cheia!** Sua recarga de Mystery Dungeon terminou!")
                await user.send(embed=create_panel_embed(), view=EnergyView())
                del data[user_id]
                changed = True
            except:
                pass

    if changed:
        save_data(data)

client.run(TOKEN)
