import discord
from discord.ext import tasks
import os
import json
import math
from datetime import datetime, timedelta, timezone
import zoneinfo

# --- Configurações ---
TOKEN = os.getenv("TOKEN")
DEFAULT_MAX = 100 
RECHARGE_MINUTES = 30
DATA_FILE = "data.json"

TIMEZONES = {
    "Brasília (UTC-3)": "America/Sao_Paulo",
    "Manaus (UTC-4)": "America/Manaus",
    "Acre (UTC-5)": "America/Rio_Branco",
    "Fernando de Noronha (UTC-2)": "America/Noronha",
    "Lisboa/Londres (UTC+0)": "Europe/Lisbon",
    "Açores (UTC-1)": "Atlantic/Azores"
}

# --- Sistema de Dados ---
def load_data():
    if not os.path.exists(DATA_FILE): return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            return json.loads(content) if content else {}
    except: return {}

def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e: print(f"Erro ao salvar: {e}")

def get_user_config(data, user_id):
    user_info = data.get(str(user_id))
    if not isinstance(user_info, dict):
        return {"max": DEFAULT_MAX, "tz": "America/Sao_Paulo", "last_msg": None}
    return {
        "max": user_info.get("max", DEFAULT_MAX),
        "tz": user_info.get("tz", "America/Sao_Paulo"),
        "last_msg": user_info.get("last_msg")
    }

def create_panel_embed(user_limit, user_tz_code):
    tz_display = next((name for name, tz in TIMEZONES.items() if tz == user_tz_code), user_tz_code)
    return discord.Embed(
        title="🎒 Mystery Dungeon - Energia Azul 🔹",
        description=(
            f"📍 Fuso Atual: **{tz_display}**\n"
            f"🔋 Limite de **energia azul**: **{user_limit}**\n\n"
            "⚡ **Atualizar Energia:** Registra sua energia azul atual.\n"
            "🔍 **Ver Status:** Confira o status da sua energia azul.\n"
            "⚙️ **Configurações:** Altera limite azul ou fuso horário."
        ),
        color=discord.Color.blue()
    )

# --- Navegação ---

class TimezoneOptionsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        select = discord.ui.Select(
            placeholder="Escolha um fuso comum...", 
            options=[discord.SelectOption(label=name, value=tz) for name, tz in TIMEZONES.items()],
            row=0
        )
        select.callback = self.tz_callback
        self.add_item(select)

    async def tz_callback(self, interaction: discord.Interaction):
        data = load_data()
        user_id = str(interaction.user.id)
        user_info = get_user_config(data, user_id)
        user_info["tz"] = interaction.data['values'][0]
        data[user_id] = user_info
        save_data(data)
        await interaction.response.send_message(f"✅ Fuso de **energia azul** alterado!", ephemeral=True)

    @discord.ui.button(label="Digitar Manualmente", style=discord.ButtonStyle.primary, emoji="⌨️", row=1)
    async def custom_tz(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CustomTimeZoneModal())

    @discord.ui.button(label="Voltar", style=discord.ButtonStyle.danger, emoji="⬅️", row=1)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="⚙️ Configurações da **Energia Azul**:", view=MainConfigView(), embed=None)

class MainConfigView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)

    @discord.ui.button(label="Alterar Limite Azul", style=discord.ButtonStyle.secondary, emoji="📏")
    async def go_limit(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(LimitModal())

    @discord.ui.button(label="Alterar Fuso Horário", style=discord.ButtonStyle.secondary, emoji="🌐")
    async def go_tz(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="🌐 Escolha seu fuso horário:", view=TimezoneOptionsView())

    @discord.ui.button(label="Voltar ao Início", style=discord.ButtonStyle.danger, emoji="🏠")
    async def back_to_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_data()
        config = get_user_config(data, interaction.user.id)
        await interaction.response.edit_message(content=None, embed=create_panel_embed(config["max"], config["tz"]), view=EnergyView())

# --- Modais ---

class CustomTimeZoneModal(discord.ui.Modal, title='📍 Configurar Fuso Horário'):
    tz_input = discord.ui.TextInput(label='Cidade ou Fuso (Continent/City)', placeholder='Ex: Tokyo, Paris, New_York...', min_length=3, max_length=50)
    async def on_submit(self, interaction: discord.Interaction):
        # Lógica de salvar fuso...
        await interaction.response.send_message("✅ Fuso atualizado!", ephemeral=True)

class LimitModal(discord.ui.Modal, title='📏 Limite de Energia Azul 🔹'):
    limit_input = discord.ui.TextInput(label='Novo limite máximo (Azul):', placeholder='Ex: 120', min_length=1, max_length=3)
    async def on_submit(self, interaction: discord.Interaction):
        # Lógica de salvar limite...
        await interaction.response.send_message("✅ Limite atualizado!", ephemeral=True)

class EnergyModal(discord.ui.Modal):
    def __init__(self, limit, tz_code):
        super().__init__(title="⚡ Atualizar Energia Azul 🔹")
        self.limit, self.tz_code = limit, tz_code
        self.energy_input = discord.ui.TextInput(label=f'Energia AZUL atual (0 a {limit})', min_length=1, max_length=3)
        self.add_item(self.energy_input)

    async def on_submit(self, interaction: discord.Interaction):
        # Lógica de registrar energia...
        await interaction.response.send_message("⚡ Energia registrada!", ephemeral=True)

# --- View Principal ---

class EnergyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Status da Energia Azul", style=discord.ButtonStyle.primary, emoji="🔍", custom_id="p:status")
    async def status_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_data()
        config = get_user_config(data, interaction.user.id)
        user_data = data.get(str(interaction.user.id))
        limit = config["max"]
        
        # Lógica de cálculo de status...
        await interaction.response.send_message(f"🔹 **Status verificado!**", ephemeral=True)

    @discord.ui.button(label="Atualizar Energia Azul", style=discord.ButtonStyle.success, emoji="⚡", custom_id="p:update")
    async def update_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_data()
        config = get_user_config(data, interaction.user.id)
        await interaction.response.send_modal(EnergyModal(config["max"], config["tz"]))

    @discord.ui.button(label="Configurações", style=discord.ButtonStyle.secondary, emoji="⚙️", custom_id="p:config")
    async def config_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Menu de configuração agora é efêmero para não poluir
        await interaction.response.send_message("⚙️ Configurações da **Energia Azul**:", view=MainConfigView(), ephemeral=True)

# --- Bot Core ---

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
        print(f"✅ Bot online como {self.user}")

client = MyBot()

@client.event
async def on_message(message):
    if message.author.bot or not isinstance(message.channel, discord.DMChannel): return

    data = load_data()
    user_id = str(message.author.id)
    config = get_user_config(data, user_id)

    # --- Lógica de Auto-Limpeza ---
    # Tenta apagar o menu anterior se ele existir
    if config["last_msg"]:
        try:
            old_msg = await message.channel.fetch_message(config["last_msg"])
            await old_msg.delete()
        except:
            pass # Mensagem já foi apagada ou não existe

    # Envia o novo menu
    new_msg = await message.channel.send(
        embed=create_panel_embed(config["max"], config["tz"]), 
        view=EnergyView()
    )

    # Salva o ID da nova mensagem para apagar depois
    config["last_msg"] = new_msg.id
    data[user_id] = config
    save_data(data)

@tasks.loop(seconds=10)
async def check_energy():
    # ... (mesma lógica de checagem anterior)
    pass

client.run(TOKEN)
