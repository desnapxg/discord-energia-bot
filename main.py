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
            return json.loads(f.read())
    except: return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def get_user_config(data, user_id):
    u = data.get(str(user_id), {})
    return {
        "max": u.get("max", DEFAULT_MAX),
        "tz": u.get("tz", "America/Sao_Paulo"),
        "last_msg": u.get("last_msg"),
        "status": u.get("status"),
        "finish": u.get("finish")
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
        
        # Primeiro campo: Placeholder já estava certo
        self.energy_input = discord.ui.TextInput(
            label=f'Energia azul atual (0 a {limit})', 
            placeholder='Ex: 58', 
            min_length=1, 
            max_length=3
        )
        
        # Segundo campo: AJUSTADO para placeholder (some ao digitar)
        self.time_input = discord.ui.TextInput(
            label='Tempo para recarregar a próxima energia azul:', 
            placeholder='Ex: 29:59 ou 2959', 
            min_length=1, 
            max_length=5
        )
        
        self.add_item(self.energy_input)
        self.add_item(self.time_input)

    async def on_submit(self, interaction: discord.Interaction):
        v_energy = self.energy_input.value.strip()
        v_time = self.time_input.value.strip().replace(',', ':').replace(' ', ':').replace('.', ':')
        
        if not v_energy.isdigit():
            return await interaction.response.send_message("❌ Energia deve ser um número.", ephemeral=True)
        
        curr = int(v_energy)
        if curr > self.limit:
            return await interaction.response.send_message(f"❌ Valor acima do limite (**{self.limit}**).", ephemeral=True)

        m, s = 0, 0
        try:
            if ':' in v_time:
                parts = v_time.split(':')
                m, s = int(parts[0]), int(parts[1]) if len(parts) > 1 and parts[1] else 0
            elif len(v_time) >= 3 and v_time.isdigit():
                m = int(v_time[:-2])
                s = int(v_time[-2:])
            else:
                m, s = int(v_time), 0
        except ValueError:
            return await interaction.response.send_message("❌ Formato de tempo inválido.", ephemeral=True)

        total_next_seconds = (m * 60) + s
        if total_next_seconds > (RECHARGE_MINUTES * 60) or s > 59:
            return await interaction.response.send_message("❌ Tempo inválido (Máximo 30:00).", ephemeral=True)

        data = load_data()
        user_id = str(interaction.user.id)
        config = get_user_config(data, user_id)
        
        if curr >= self.limit:
            data[user_id] = {**config, "status": "FULL", "finish": None}
            msg = "✅ Sua **energia azul** está cheia!"
        else:
            pontos_faltantes = self.limit - curr
            segundos_totais = total_next_seconds + ((pontos_faltantes - 1) * RECHARGE_MINUTES * 60)
            
            finish_time = datetime.now(timezone.utc) + timedelta(seconds=segundos_totais)
            data[user_id] = {**config, "finish": finish_time.isoformat(), "status": "RECHARGING"}
            
            local_tz = zoneinfo.ZoneInfo(self.tz_code)
            finish_local = finish_time.astimezone(local_tz)
            msg = (
                f"🔹 **Energia azul atualizada: {curr}/{self.limit}**\n"
                f"⏰ Ficará cheia às: `{finish_local.strftime('%H:%M:%S')}` em `{finish_local.strftime('%d/%m')}`"
            )
            
        save_data(data)
        await interaction.response.send_message(msg, ephemeral=True)

# --- Classes de View, Config e Bot Core ---

class MainConfigView(discord.ui.View):
    def __init__(self): super().__init__(timeout=180)
    @discord.ui.button(label="Alterar Limite", style=discord.ButtonStyle.secondary, emoji="📏")
    async def go_limit(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(LimitModal())
    @discord.ui.button(label="Alterar Fuso", style=discord.ButtonStyle.secondary, emoji="🌐")
    async def go_tz(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="🌐 Escolha o fuso horário:", view=TimezoneOptionsView())
    @discord.ui.button(label="Voltar ao Início", style=discord.ButtonStyle.danger, emoji="🏠")
    async def back_to_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_data(); config = get_user_config(data, interaction.user.id)
        await interaction.response.edit_message(content=None, embed=create_panel_embed(config["max"], config["tz"]), view=EnergyView())

class LimitModal(discord.ui.Modal, title='📏 Limite de Energia Azul'):
    limit_input = discord.ui.TextInput(label='Novo limite máximo:', placeholder='Ex: 100')
    async def on_submit(self, interaction: discord.Interaction):
        if not self.limit_input.value.isdigit(): return await interaction.response.send_message("❌ Use apenas números.", ephemeral=True)
        data = load_data(); user_id = str(interaction.user.id); config = get_user_config(data, user_id)
        data[user_id] = {**config, "max": int(self.limit_input.value)}
        save_data(data); await interaction.response.send_message("✅ Limite atualizado!", ephemeral=True)

class TimezoneOptionsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        options = [discord.SelectOption(label=name, value=tz) for name, tz in TIMEZONES.items()]
        select = discord.ui.Select(placeholder="Selecione seu fuso...", options=options)
        select.callback = self.tz_callback
        self.add_item(select)
    async def tz_callback(self, interaction: discord.Interaction):
        data = load_data(); user_id = str(interaction.user.id); config = get_user_config(data, user_id)
        data[user_id] = {**config, "tz": interaction.data['values'][0]}
        save_data(data); await interaction.response.send_message("✅ Fuso horário atualizado!", ephemeral=True)

class EnergyView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)

    @discord.ui.button(label="Status da Energia", style=discord.ButtonStyle.primary, emoji="🔍", custom_id="p:status")
    async def status_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_data(); user_id = str(interaction.user.id); u_data = data.get(user_id)
        if not u_data or u_data.get("status") is None:
            return await interaction.response.send_message("Sua energia azul ainda não está sendo monitorada.", ephemeral=True)
        limit = u_data.get("max", DEFAULT_MAX)
        if u_data.get("status") == "FULL":
            return await interaction.response.send_message(f"🔋 Energia cheia! ({limit}/{limit})", ephemeral=True)
        finish_time_str = u_data.get("finish")
        if not finish_time_str: return await interaction.response.send_message("Sua energia azul ainda não está sendo monitorada.", ephemeral=True)

        finish_time = datetime.fromisoformat(finish_time_str)
        now = datetime.now(timezone.utc)
        if now >= finish_time: return await interaction.response.send_message(f"✨ Energia cheia! ({limit}/{limit})", ephemeral=True)
        
        diff = finish_time - now
        total_secs = diff.total_seconds()
        pontos_faltantes = math.ceil(total_secs / (RECHARGE_MINUTES * 60))
        current = max(0, limit - pontos_faltantes)
        h, m, s = int(total_secs // 3600), int((total_secs % 3600) // 60), int(total_secs % 60)
        await interaction.response.send_message(f"🔹 **Energia atual: {current}/{limit}**\n⏳ Falta: `{h}h {m}m {s}s` para completar.", ephemeral=True)

    @discord.ui.button(label="Atualizar Energia", style=discord.ButtonStyle.success, emoji="⚡", custom_id="p:update")
    async def update_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_data(); config = get_user_config(data, interaction.user.id)
        await interaction.response.send_modal(EnergyModal(config["max"], config["tz"]))

    @discord.ui.button(label="Configurações", style=discord.ButtonStyle.secondary, emoji="⚙️", custom_id="p:config")
    async def config_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("⚙️ Configurações:", view=MainConfigView(), ephemeral=True)

class MyBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default(); intents.message_content = True
        super().__init__(intents=intents)
    async def setup_hook(self):
        self.add_view(EnergyView())
        if not check_energy.is_running(): check_energy.start()
    async def on_ready(self): print(f"✅ Bot Online: {self.user}")

client = MyBot()

@client.event
async def on_message(message):
    if message.author.bot or not isinstance(message.channel, discord.DMChannel): return
    data = load_data(); user_id = str(message.author.id); config = get_user_config(data, user_id)
    if message.content.lower() == "!testar":
        finish = datetime.now(timezone.utc) + timedelta(seconds=10)
        data[user_id] = {**config, "finish": finish.isoformat(), "status": "RECHARGING"}
        save_data(data); await message.channel.send("🧪 Teste iniciado! 10 segundos...")
        return 
    if config.get("last_msg"):
        try:
            old = await message.channel.fetch_message(config["last_msg"]); await old.delete()
        except: pass
    new_msg = await message.channel.send(embed=create_panel_embed(config["max"], config["tz"]), view=EnergyView())
    data[user_id] = {**config, "last_msg": new_msg.id}; save_data(data)

@tasks.loop(seconds=10)
async def check_energy():
    data = load_data(); now = datetime.now(timezone.utc); changed = False
    for uid, udata in list(data.items()):
        if udata.get("finish"):
            if now >= datetime.fromisoformat(udata["finish"]):
                try:
                    user = await client.fetch_user(int(uid))
                    await user.send(f"🔥 **Sua energia azul chegou em {udata.get('max')}. Hora de fazer alguma Mystery Dungeon Azul!**")
                    udata["status"] = "FULL"; udata["finish"] = None; changed = True
                except: pass
    if changed: save_data(data)

if __name__ == "__main__":
    client.run(TOKEN)
