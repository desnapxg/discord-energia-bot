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

# --- Funções de Apoio ---
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

# --- Modais ---

class EnergyModal(discord.ui.Modal):
    def __init__(self, limit, tz_code):
        super().__init__(title="⚡ Atualizar Energia Azul 🔹")
        self.limit, self.tz_code = limit, tz_code
        
        self.energy_input = discord.ui.TextInput(
            label=f'Energia azul atual (0 a {limit})', 
            placeholder='Ex: 58', min_length=1, max_length=3
        )
        self.time_input = discord.ui.TextInput(
            label='Tempo para recarregar a próxima energia azul:', 
            placeholder='Ex: 12:30 ou 12', default="29:59", min_length=1, max_length=5
        )
        self.add_item(self.energy_input)
        self.add_item(self.time_input)

    async def on_submit(self, interaction: discord.Interaction):
        v_energy = self.energy_input.value.strip()
        # Limpa espaços e normaliza separadores
        v_time = self.time_input.value.strip().replace(' ', '').replace(',', ':')
        
        if not v_energy.isdigit():
            return await interaction.response.send_message("❌ A energia deve ser um número inteiro.", ephemeral=True)
        
        curr = int(v_energy)
        if curr > self.limit:
            return await interaction.response.send_message(f"❌ Valor inválido. Seu limite atual é **{self.limit}**.", ephemeral=True)

        m, s = 0, 0
        try:
            if ':' in v_time:
                parts = v_time.split(':')
                m = int(parts[0])
                s = int(parts[1]) if len(parts) > 1 and parts[1] else 0
            else:
                m = int(v_time)
                s = 0
        except ValueError:
            return await interaction.response.send_message("❌ Formato de tempo inválido. Use `minutos:segundos` (ex: 12:30).", ephemeral=True)

        # Validação lógica de tempo (Não pode ser mais que o tempo de 1 carga)
        total_input_seconds = (m * 60) + s
        if total_input_seconds > (RECHARGE_MINUTES * 60) or m < 0 or s < 0 or s > 59:
            return await interaction.response.send_message(f"❌ O tempo não pode exceder {RECHARGE_MINUTES} minutos.", ephemeral=True)

        data = load_data()
        user_id = str(interaction.user.id)
        u_info = data.get(user_id, {"max": self.limit, "tz": self.tz_code})
        
        if curr >= self.limit:
            u_info.update({"status": "FULL", "finish": None})
            msg = f"✅ Sua **energia azul** foi definida como cheia (**{self.limit}/{self.limit}**)!"
        else:
            missing_points = self.limit - curr
            # Cálculo: segundos para a próxima + (pontos restantes - 1) * 30 min
            total_seconds_needed = total_input_seconds + ((missing_points - 1) * RECHARGE_MINUTES * 60)
            
            finish_time = datetime.now(timezone.utc) + timedelta(seconds=total_seconds_needed)
            u_info.update({"finish": finish_time.isoformat(), "status": "RECHARGING"})
            
            local_tz = zoneinfo.ZoneInfo(self.tz_code)
            finish_local = finish_time.astimezone(local_tz)
            msg = (
                f"🔹 **Energia azul atualizada: {curr}/{self.limit}**\n"
                f"⏰ Ficará cheia às: `{finish_local.strftime('%H:%M:%S')}` em `{finish_local.strftime('%d/%m/%Y')}`"
            )
            
        data[user_id] = u_info
        save_data(data)
        await interaction.response.send_message(msg, ephemeral=True)

# --- Views de Configuração ---

class LimitModal(discord.ui.Modal, title='📏 Limite de Energia Azul 🔹'):
    limit_input = discord.ui.TextInput(label='Novo limite máximo:', placeholder='Ex: 120', min_length=1, max_length=3)
    async def on_submit(self, interaction: discord.Interaction):
        val = self.limit_input.value.strip()
        if not val.isdigit(): return await interaction.response.send_message("❌ Digite apenas números.", ephemeral=True)
        data = load_data(); user_id = str(interaction.user.id)
        u_info = data.get(user_id, {"max": DEFAULT_MAX, "tz": "America/Sao_Paulo"})
        u_info["max"] = int(val); data[user_id] = u_info; save_data(data)
        await interaction.response.send_message(f"✅ Limite azul alterado para **{val}**!", ephemeral=True)

class TimezoneOptionsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        select = discord.ui.Select(
            placeholder="Escolha seu fuso horário...", 
            options=[discord.SelectOption(label=name, value=tz) for name, tz in TIMEZONES.items()]
        )
        select.callback = self.tz_callback
        self.add_item(select)

    async def tz_callback(self, interaction: discord.Interaction):
        data = load_data(); user_id = str(interaction.user.id)
        u_info = data.get(user_id, {"max": DEFAULT_MAX, "tz": "America/Sao_Paulo"})
        u_info["tz"] = interaction.data['values'][0]; data[user_id] = u_info; save_data(data)
        await interaction.response.send_message("✅ Fuso horário atualizado com sucesso!", ephemeral=True)

    @discord.ui.button(label="Voltar", style=discord.ButtonStyle.danger, emoji="⬅️")
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="⚙️ Configurações da Energia Azul:", view=MainConfigView(), embed=None)

class MainConfigView(discord.ui.View):
    def __init__(self): super().__init__(timeout=180)
    @discord.ui.button(label="Alterar Limite", style=discord.ButtonStyle.secondary, emoji="📏")
    async def go_limit(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(LimitModal())
    @discord.ui.button(label="Alterar Fuso", style=discord.ButtonStyle.secondary, emoji="🌐")
    async def go_tz(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="🌐 Selecione a região correta:", view=TimezoneOptionsView())
    @discord.ui.button(label="Voltar ao Início", style=discord.ButtonStyle.danger, emoji="🏠")
    async def back_to_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_data(); config = get_user_config(data, interaction.user.id)
        await interaction.response.edit_message(content=None, embed=create_panel_embed(config["max"], config["tz"]), view=EnergyView())

# --- View Principal ---

class EnergyView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)

    @discord.ui.button(label="Status da Energia", style=discord.ButtonStyle.primary, emoji="🔍", custom_id="p:status")
    async def status_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_data(); user_id = str(interaction.user.id); u_data = data.get(user_id)
        if not u_data or ("finish" not in u_data and u_data.get("status") != "FULL"):
            return await interaction.response.send_message("Você ainda não registrou sua energia.", ephemeral=True)
        
        limit = u_data.get("max", DEFAULT_MAX)
        if u_data.get("status") == "FULL":
            return await interaction.response.send_message(f"🔋 Sua energia azul está cheia! (**{limit}/{limit}**)", ephemeral=True)
        
        finish_time = datetime.fromisoformat(u_data["finish"])
        now = datetime.now(timezone.utc)
        if now >= finish_time: return await interaction.response.send_message(f"✨ Energia cheia! (**{limit}/{limit}**)", ephemeral=True)
        
        diff = finish_time - now
        total_secs = diff.total_seconds()
        # Cálculo de pontos atuais baseado no tempo restante preciso
        current = max(0, limit - math.ceil(total_secs / (RECHARGE_MINUTES * 60)))
        
        h, m, s = int(total_secs // 3600), int((total_secs % 3600) // 60), int(total_secs % 60)
        await interaction.response.send_message(f"🔹 **Energia atual: {current}/{limit}**\n⏳ Falta: `{h}h {m}m {s}s` para completar.", ephemeral=True)

    @discord.ui.button(label="Atualizar Energia", style=discord.ButtonStyle.success, emoji="⚡", custom_id="p:update")
    async def update_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_data(); config = get_user_config(data, interaction.user.id)
        await interaction.response.send_modal(EnergyModal(config["max"], config["tz"]))

    @discord.ui.button(label="Configurações", style=discord.ButtonStyle.secondary, emoji="⚙️", custom_id="p:config")
    async def config_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("⚙️ Painel de Configurações:", view=MainConfigView(), ephemeral=True)

# --- Core do Bot ---

class MyBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
    async def setup_hook(self):
        self.add_view(EnergyView())
        if not check_energy.is_running(): check_energy.start()
    async def on_ready(self): print(f"✅ Bot de Energia Azul pronto: {self.user}")

client = MyBot()

@client.event
async def on_message(message):
    if message.author.bot or not isinstance(message.channel, discord.DMChannel): return
    data = load_data(); user_id = str(message.author.id); u_info = get_user_config(data, user_id)

    if message.content.lower() == "!testar":
        u_info.update({"finish": (datetime.now(timezone.utc) + timedelta(seconds=10)).isoformat(), "status": "RECHARGING"})
        data[user_id] = u_info; save_data(data); await message.channel.send("🧪 Teste iniciado! Em 10s você receberá o aviso.")
        return 

    if u_info.get("last_msg"):
        try:
            old = await message.channel.fetch_message(u_info["last_msg"]); await old.delete()
        except: pass
    new_msg = await message.channel.send(embed=create_panel_embed(u_info["max"], u_info["tz"]), view=EnergyView())
    u_info["last_msg"] = new_msg.id; data[user_id] = u_info; save_data(data)

@tasks.loop(seconds=10)
async def check_energy():
    data = load_data(); now = datetime.now(timezone.utc); changed = False
    for uid, udata in list(data.items()):
        if isinstance(udata, dict) and udata.get("finish"):
            if now >= datetime.fromisoformat(udata["finish"]):
                try:
                    user = await client.fetch_user(int(uid))
                    await user.send(f"🔥 **Sua energia azul chegou em {udata.get('max')}. Hora de fazer alguma Mystery Dungeon Azul!**")
                    udata["status"] = "FULL"; udata["finish"] = None; changed = True
                except: pass
    if changed: save_data(data)

if __name__ == "__main__":
    client.run(TOKEN)
