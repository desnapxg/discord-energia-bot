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

# Lista de Fusos Horários Populares
TIMEZONES = {
    "Brasília (UTC-3)": "America/Sao_Paulo",
    "Manaus (UTC-4)": "America/Manaus",
    "Acre (UTC-5)": "America/Rio_Branco",
    "Fernando de Noronha (UTC-2)": "America/Noronha",
    "Lisboa/Londres (UTC+0)": "Europe/Lisbon",
    "Açores (UTC-1)": "Atlantic/Azores"
}

# --- Funções de Dados ---
def load_data():
    if not os.path.exists(DATA_FILE): return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except: return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def get_user_config(data, user_id):
    user_info = data.get(str(user_id))
    if not isinstance(user_info, dict):
        return {"max": DEFAULT_MAX, "tz": "America/Sao_Paulo"}
    return {
        "max": user_info.get("max", DEFAULT_MAX),
        "tz": user_info.get("tz", "America/Sao_Paulo")
    }

def create_panel_embed(user_limit, user_tz_code):
    # Procura o nome amigável ou usa o próprio código do fuso
    tz_display = next((name for name, tz in TIMEZONES.items() if tz == user_tz_code), user_tz_code)
    
    return discord.Embed(
        title="🎒 Mystery Dungeon - Energia",
        description=(
            f"📍 Fuso Atual: **{tz_display}**\n"
            f"🔋 Limite de energia: **{user_limit}**\n\n"
            "⚡ **Atualizar Energia:** Registra sua energia atual.\n"
            "🔍 **Ver Status:** Verifica o progresso da recarga.\n"
            "⚙️ **Configurações:** Altera limite ou fuso horário."
        ),
        color=discord.Color.gold()
    )

# --- Modais ---

class CustomTimeZoneModal(discord.ui.Modal, title='📍 Configurar Fuso Horário'):
    tz_input = discord.ui.TextInput(
        label='Sua Cidade ou Fuso (Ex: Continent/City)',
        placeholder='Tente: Asia/Tokyo, Europe/Paris, America/Cuiaba...',
        min_length=3, max_length=50
    )

    async def on_submit(self, interaction: discord.Interaction):
        input_value = self.tz_input.value.strip()
        
        # Tenta formatar a entrada caso o utilizador esqueça o continente
        # Ex: "Tokyo" -> "Asia/Tokyo" (ajuda básica)
        search_value = input_value.replace(" ", "_").title()
        
        found_tz = None
        try:
            # Tenta validar o que foi digitado
            zoneinfo.ZoneInfo(input_value)
            found_tz = input_value
        except:
            # Se falhou, tenta procurar na lista completa do sistema
            for tz in zoneinfo.available_timezones():
                if search_value in tz:
                    found_tz = tz
                    break
        
        if found_tz:
            data = load_data()
            user_id = str(interaction.user.id)
            user_info = data.get(user_id, {})
            if not isinstance(user_info, dict): user_info = {}
            
            user_info["tz"] = found_tz
            data[user_id] = user_info
            save_data(data)

            await interaction.response.send_message(f"✅ Fuso horário reconhecido e definido como: **{found_tz}**", ephemeral=True)
            await interaction.channel.send(embed=create_panel_embed(user_info.get("max", DEFAULT_MAX), found_tz), view=EnergyView())
        else:
            await interaction.response.send_message(
                "❌ Não consegui encontrar esse fuso.\n"
                "**Dica:** Tente o formato `Continente/Cidade` (ex: `Asia/Tokyo` ou `Europe/Madrid`).", 
                ephemeral=True
            )

class LimitModal(discord.ui.Modal, title='📏 Limite de Energia'):
    limit_input = discord.ui.TextInput(label='Qual seu novo limite?', placeholder='Ex: 120', min_length=1, max_length=3)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            new_limit = int(self.limit_input.value)
            if new_limit <= 0: raise ValueError
            data = load_data()
            user_id = str(interaction.user.id)
            user_info = data.get(user_id, {})
            if not isinstance(user_info, dict): user_info = {}
            
            user_info["max"] = new_limit
            data[user_id] = user_info
            save_data(data)

            config = get_user_config(data, user_id)
            await interaction.response.send_message(f"✅ Limite de energia atualizado para **{new_limit}**!", ephemeral=True)
            await interaction.channel.send(embed=create_panel_embed(new_limit, config["tz"]), view=EnergyView())
        except:
            await interaction.response.send_message("❌ Por favor, use apenas números inteiros maiores que 0.", ephemeral=True)

class EnergyModal(discord.ui.Modal):
    def __init__(self, limit, tz_code):
        super().__init__(title="⚡ Atualizar Energia")
        self.limit, self.tz_code = limit, tz_code
        self.energy_input = discord.ui.TextInput(label=f'Energia atual (0 a {limit})', min_length=1, max_length=3)
        self.add_item(self.energy_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            current = int(self.energy_input.value)
            data = load_data()
            user_id = str(interaction.user.id)
            
            if current >= self.limit:
                data[user_id] = {"status": "FULL", "max": self.limit, "tz": self.tz_code}
                msg = "✅ Energia registrada como cheia!"
            else:
                missing = self.limit - current
                finish_time = datetime.now(timezone.utc) + timedelta(minutes=missing * RECHARGE_MINUTES)
                data[user_id] = {"finish": finish_time.isoformat(), "max": self.limit, "tz": self.tz_code}
                
                user_tz = zoneinfo.ZoneInfo(self.tz_code)
                finish_local = finish_time.astimezone(user_tz)
                msg = f"⚡ Registrado: **{current}/{self.limit}**\n⏰ Cheia às: `{finish_local.strftime('%H:%M')}`"
            
            save_data(data)
            await interaction.response.send_message(msg, ephemeral=True)
            await interaction.channel.send(embed=create_panel_embed(self.limit, self.tz_code), view=EnergyView())
        except:
            await interaction.response.send_message("❌ Erro ao processar o número digitado.", ephemeral=True)

# --- Views ---

class ConfigView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        
        select = discord.ui.Select(
            placeholder="Escolha um fuso comum...",
            options=[discord.SelectOption(label=name, value=tz) for name, tz in TIMEZONES.items()]
        )
        select.callback = self.tz_callback
        self.add_item(select)

    async def tz_callback(self, interaction: discord.Interaction):
        data = load_data()
        user_id = str(interaction.user.id)
        user_info = data.get(user_id, {})
        if not isinstance(user_info, dict): user_info = {}
        
        user_info["tz"] = interaction.data['values'][0]
        data[user_id] = user_info
        save_data(data)
        
        await interaction.response.send_message(f"✅ Fuso alterado com sucesso!", ephemeral=True)
        await interaction.channel.send(embed=create_panel_embed(user_info.get("max", DEFAULT_MAX), user_info["tz"]), view=EnergyView())

    @discord.ui.button(label="Alterar Limite de Energia", style=discord.ButtonStyle.secondary, emoji="📏", row=1)
    async def change_limit(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(LimitModal())

    @discord.ui.button(label="Digitar Manualmente (Outros)", style=discord.ButtonStyle.primary, emoji="⌨️", row=1)
    async def custom_tz(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CustomTimeZoneModal())

class EnergyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Ver Status", style=discord.ButtonStyle.primary, emoji="🔍", custom_id="btn_status")
    async def status_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_data()
        config = get_user_config(data, interaction.user.id)
        user_data = data.get(str(interaction.user.id))
        limit = config["max"]

        if not user_data or (isinstance(user_data, dict) and "finish" not in user_data and user_data.get("status") != "FULL"):
            await interaction.response.send_message(f"👋 Nenhuma recarga ativa no momento.", ephemeral=True)
        elif isinstance(user_data, dict) and user_data.get("status") == "FULL":
            await interaction.response.send_message(f"🔋 Sua energia está cheia (**{limit}/{limit}**)!", ephemeral=True)
        else:
            finish_time = datetime.fromisoformat(user_data["finish"])
            now = datetime.now(timezone.utc)
            if now >= finish_time:
                await interaction.response.send_message(f"✨ Energia completada (**{limit}/{limit}**)!", ephemeral=True)
            else:
                minutes_left = (finish_time - now).total_seconds() / 60
                current = max(0, math.floor(limit - (minutes_left / RECHARGE_MINUTES)))
                await interaction.response.send_message(f"⚡ Status aproximado: **{current}/{limit}**", ephemeral=True)
        
        await interaction.channel.send(embed=create_panel_embed(limit, config["tz"]), view=EnergyView())

    @discord.ui.button(label="Atualizar Energia", style=discord.ButtonStyle.success, emoji="⚡", custom_id="btn_update")
    async def update_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_data()
        config = get_user_config(data, interaction.user.id)
        await interaction.response.send_modal(EnergyModal(config["max"], config["tz"]))

    @discord.ui.button(label="Configurações", style=discord.ButtonStyle.secondary, emoji="⚙️", custom_id="btn_config")
    async def config_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("⚙️ **Painel de Configurações**", view=ConfigView(), ephemeral=True)

# --- Bot e Loop ---
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
    config = get_user_config(data, message.author.id)
    
    if message.content.lower() == "!testar":
        test_finish = datetime.now(timezone.utc) + timedelta(seconds=5)
        data[str(message.author.id)] = {"finish": test_finish.isoformat(), "max": config["max"], "tz": config["tz"]}
        save_data(data)
        await message.channel.send("🧪 **Teste iniciado!** O aviso chegará em instantes.")
        return

    await message.channel.send(embed=create_panel_embed(config["max"], config["tz"]), view=EnergyView())

@tasks.loop(seconds=10)
async def check_energy():
    data = load_data()
    now = datetime.now(timezone.utc)
    changed = False
    for uid, udata in list(data.items()):
        if isinstance(udata, dict) and "finish" in udata:
            if now >= datetime.fromisoformat(udata["finish"]):
                try:
                    user = await client.fetch_user(int(uid))
                    limit, tz = udata.get("max", DEFAULT_MAX), udata.get("tz", "America/Sao_Paulo")
                    await user.send(f"🔥 **Sua energia chegou em {limit}!** Hora de Mystery Dungeon! 🎮")
                    await user.send(embed=create_panel_embed(limit, tz), view=EnergyView())
                    data[uid] = {"status": "FULL", "max": limit, "tz": tz}
                    changed = True
                except: pass
    if changed: save_data(data)

client.run(TOKEN)
