import discord
from discord.ext import tasks
import os
import json
import math
from datetime import datetime, timedelta, timezone
import zoneinfo

# --- Configurações Gerais ---
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
    except (json.JSONDecodeError, PermissionError):
        return {}

def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Erro crítico ao salvar dados: {e}")

def get_user_config(data, user_id):
    user_info = data.get(str(user_id))
    if not isinstance(user_info, dict):
        return {"max": DEFAULT_MAX, "tz": "America/Sao_Paulo"}
    return {
        "max": user_info.get("max", DEFAULT_MAX),
        "tz": user_info.get("tz", "America/Sao_Paulo")
    }

def create_panel_embed(user_limit, user_tz_code):
    tz_display = next((name for name, tz in TIMEZONES.items() if tz == user_tz_code), user_tz_code)
    embed = discord.Embed(
        title="🎒 Mystery Dungeon - Energia Azul 🔹",
        description=(
            f"📍 Fuso Atual: **{tz_display}**\n"
            f"🔋 Limite de **energia azul**: **{user_limit}**\n\n"
            "⚡ **Atualizar Energia:** Registra sua energia azul atual.\n"
            "🔍 **Ver Status:** Confira o status atual da sua energia.\n"
            "⚙️ **Configurações:** Altera limite azul ou fuso horário."
        ),
        color=discord.Color.blue()
    )
    return embed

# --- Modais (Formulários) ---

class CustomTimeZoneModal(discord.ui.Modal, title='📍 Configurar Fuso Horário'):
    tz_input = discord.ui.TextInput(label='Cidade ou Fuso (Continent/City)', placeholder='Ex: Tokyo, Paris, New_York...', min_length=3, max_length=50)

    async def on_submit(self, interaction: discord.Interaction):
        raw_input = self.tz_input.value.strip().lower().replace(" ", "_")
        found_tz = None
        for tz in zoneinfo.available_timezones():
            if raw_input in tz.lower():
                found_tz = tz
                break
        
        if found_tz:
            data = load_data()
            user_id = str(interaction.user.id)
            user_info = get_user_config(data, user_id)
            user_info["tz"] = found_tz
            data[user_id] = user_info
            save_data(data)
            await interaction.response.send_message(f"✅ Fuso de **energia azul** definido: **{found_tz}**", ephemeral=True)
            await interaction.channel.send(embed=create_panel_embed(user_info["max"], found_tz), view=EnergyView())
        else:
            await interaction.response.send_message("❌ Fuso não encontrado. Tente `Continente/Cidade`.", ephemeral=True)

class LimitModal(discord.ui.Modal, title='📏 Limite de Energia Azul 🔹'):
    limit_input = discord.ui.TextInput(label='Novo limite máximo (Azul):', placeholder='Ex: 120', min_length=1, max_length=3)

    async def on_submit(self, interaction: discord.Interaction):
        if not self.limit_input.value.isdigit():
            return await interaction.response.send_message("❌ Digite apenas números.", ephemeral=True)
        new_limit = int(self.limit_input.value)
        data = load_data()
        user_id = str(interaction.user.id)
        user_info = get_user_config(data, user_id)
        user_info["max"] = new_limit
        data[user_id] = user_info
        save_data(data)
        await interaction.response.send_message(f"✅ Limite de **energia azul** alterado para **{new_limit}**!", ephemeral=True)
        await interaction.channel.send(embed=create_panel_embed(new_limit, user_info["tz"]), view=EnergyView())

class EnergyModal(discord.ui.Modal):
    def __init__(self, limit, tz_code):
        super().__init__(title="⚡ Atualizar Energia Azul 🔹")
        self.limit, self.tz_code = limit, tz_code
        self.energy_input = discord.ui.TextInput(label=f'Energia AZUL atual (0 a {limit})', min_length=1, max_length=3)
        self.add_item(self.energy_input)

    async def on_submit(self, interaction: discord.Interaction):
        if not self.energy_input.value.isdigit():
            return await interaction.response.send_message("❌ Digite apenas números.", ephemeral=True)
        
        current = int(self.energy_input.value)
        data = load_data()
        user_id = str(interaction.user.id)
        
        if current >= self.limit:
            data[user_id] = {"status": "FULL", "max": self.limit, "tz": self.tz_code}
            msg = f"✅ Sua **energia azul** foi registrada como cheia (**{self.limit}/{self.limit}**)!"
        else:
            missing = self.limit - current
            finish_time = datetime.now(timezone.utc) + timedelta(minutes=missing * RECHARGE_MINUTES)
            data[user_id] = {"finish": finish_time.isoformat(), "max": self.limit, "tz": self.tz_code}
            
            local_tz = zoneinfo.ZoneInfo(self.tz_code)
            finish_local = finish_time.astimezone(local_tz)
            msg = (
                f"🔹 **Energia azul atual: {current}/{self.limit}**\n"
                f"⏰ Energia azul cheia às: `{finish_local.strftime('%H:%M')}` do dia `{finish_local.strftime('%d/%m/%Y')}`"
            )
            
        save_data(data)
        await interaction.response.send_message(msg, ephemeral=True)
        await interaction.channel.send(embed=create_panel_embed(self.limit, self.tz_code), view=EnergyView())

# --- Views ---

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
        await interaction.channel.send(embed=create_panel_embed(user_info["max"], user_info["tz"]), view=EnergyView())

    @discord.ui.button(label="Digitar Manualmente (Outros)", style=discord.ButtonStyle.primary, emoji="⌨️", row=1)
    async def custom_tz(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CustomTimeZoneModal())

class MainConfigView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)

    @discord.ui.button(label="Alterar Limite Azul", style=discord.ButtonStyle.secondary, emoji="📏")
    async def go_limit(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(LimitModal())

    @discord.ui.button(label="Alterar Fuso Horário", style=discord.ButtonStyle.secondary, emoji="🌐")
    async def go_tz(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🌐 Escolha seu fuso horário:", view=TimezoneOptionsView(), ephemeral=True)

class EnergyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Status atual da sua energia", style=discord.ButtonStyle.primary, emoji="🔍", custom_id="p:status")
    async def status_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_data()
        config = get_user_config(data, interaction.user.id)
        user_data = data.get(str(interaction.user.id))
        limit = config["max"]
        
        if not user_data or (isinstance(user_data, dict) and "finish" not in user_data and user_data.get("status") != "FULL"):
            await interaction.response.send_message("Ainda não estamos analisando sua **energia azul**. Atualize para começarmos!", ephemeral=True)
        elif isinstance(user_data, dict) and user_data.get("status") == "FULL":
            await interaction.response.send_message(f"🔋 Sua **energia azul** está cheia (**{limit}/{limit}**)!", ephemeral=True)
        else:
            finish_time = datetime.fromisoformat(user_data["finish"])
            now = datetime.now(timezone.utc)
            if now >= finish_time:
                await interaction.response.send_message(f"✨ Energia azul completada (**{limit}/{limit}**)!", ephemeral=True)
            else:
                minutes_left = (finish_time - now).total_seconds() / 60
                current = max(0, math.floor(limit - (minutes_left / RECHARGE_MINUTES)))
                await interaction.response.send_message(f"🔹 **Energia azul atual: {current}/{limit}**", ephemeral=True)
        
        await interaction.channel.send(embed=create_panel_embed(limit, config["tz"]), view=EnergyView())

    @discord.ui.button(label="Atualizar Energia Azul", style=discord.ButtonStyle.success, emoji="⚡", custom_id="p:update")
    async def update_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_data()
        config = get_user_config(data, interaction.user.id)
        await interaction.response.send_modal(EnergyModal(config["max"], config["tz"]))

    @discord.ui.button(label="Configurações", style=discord.ButtonStyle.secondary, emoji="⚙️", custom_id="p:config")
    async def config_button(self, interaction: discord.Interaction, button: discord.ui.Button):
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
    if message.author.bot or not isinstance(message.channel, discord.DMChannel): 
        return

    data = load_data()
    config = get_user_config(data, message.author.id)

    if message.content.lower() == "!testar":
        test_finish = datetime.now(timezone.utc) + timedelta(seconds=10)
        data[str(message.author.id)] = {"finish": test_finish.isoformat(), "max": config["max"], "tz": config["tz"]}
        save_data(data)
        await message.channel.send("🧪 **Teste iniciado.** Aguarde 10 segundos para o aviso da **energia azul**.")
        return

    await message.channel.send(embed=create_panel_embed(config["max"], config["tz"]), view=EnergyView())

@tasks.loop(seconds=10)
async def check_energy():
    data = load_data()
    now = datetime.now(timezone.utc)
    changed = False
    for uid, udata in list(data.items()):
        if isinstance(udata, dict) and "finish" in udata:
            finish_dt = datetime.fromisoformat(udata["finish"])
            if now >= finish_dt:
                try:
                    user = await client.fetch_user(int(uid))
                    limit, tz = udata.get("max", DEFAULT_MAX), udata.get("tz", "America/Sao_Paulo")
                    await user.send(f"🔥 **Sua energia azul chegou em {limit}!**")
                    await user.send(embed=create_panel_embed(limit, tz), view=EnergyView())
                    data[uid] = {"status": "FULL", "max": limit, "tz": tz}
                    changed = True
                except Exception:
                    pass # Usuário pode ter bloqueado DMs
    if changed: save_data(data)

if __name__ == "__main__":
    client.run(TOKEN)
