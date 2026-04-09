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
DEFAULT_RECHARGE_SECONDS = 1800
DATA_FILE = "data.json"

TIMEZONES = {
    "Brasília (UTC-3)": "America/Sao_Paulo",
    "Manaus (UTC-4)": "America/Manaus",
    "Acre (UTC-5)": "America/Rio_Branco",
    "Fernando de Noronha (UTC-2)": "America/Noronha",
    "Lisboa/Londres (UTC+0)": "Europe/Lisbon",
    "Açores (UTC-1)": "Atlantic/Azores"
}

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
        "recharge": u.get("recharge", DEFAULT_RECHARGE_SECONDS),
        "last_msg": u.get("last_msg"),
        "status": u.get("status"),
        "finish": u.get("finish")
    }

def format_recharge(seconds):
    m = seconds // 60
    s = seconds % 60
    return f"{m}m {s}s"

def create_panel_embed(user_limit, user_tz_code, recharge):
    tz_display = next((name for name, tz in TIMEZONES.items() if tz == user_tz_code), user_tz_code)
    return discord.Embed(
        title="🎒 Mystery Dungeon - Energia Azul 🔹",
        description=(
            f"📍 Fuso: **{tz_display}**\n"
            f"🔋 Limite: **{user_limit}**\n"
            f"⏱️ Recarga: **{format_recharge(recharge)}**"
        ),
        color=discord.Color.blue()
    )

# ---------------- MODAIS ----------------

class RechargeModal(discord.ui.Modal, title='⏱️ Tempo de Recarga'):
    time_input = discord.ui.TextInput(label='Novo tempo (mm:ss)', placeholder='Ex: 25:30')

    async def on_submit(self, interaction: discord.Interaction):
        v = self.time_input.value.replace(":", "")
        try:
            m = int(v[:-2]) if len(v) > 2 else int(v)
            s = int(v[-2:]) if len(v) > 2 else 0
        except:
            return await interaction.response.send_message("❌ Formato inválido.", ephemeral=True)

        if s > 59:
            return await interaction.response.send_message("❌ Segundos inválidos.", ephemeral=True)

        total = m * 60 + s

        data = load_data()
        uid = str(interaction.user.id)
        config = get_user_config(data, uid)

        data[uid] = {**config, "recharge": total}
        save_data(data)

        await interaction.response.send_message(f"✅ Tempo atualizado para {m}m {s}s", ephemeral=True)

class EnergyModal(discord.ui.Modal):
    def __init__(self, limit, tz_code, recharge):
        super().__init__(title="⚡ Atualizar Energia")
        self.limit, self.tz_code, self.recharge = limit, tz_code, recharge

        self.energy_input = discord.ui.TextInput(label=f'Energia (0 a {limit})')
        self.time_input = discord.ui.TextInput(label='Tempo próxima (mm:ss)')

        self.add_item(self.energy_input)
        self.add_item(self.time_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            curr = int(self.energy_input.value)
        except:
            return await interaction.response.send_message("❌ Número inválido.", ephemeral=True)

        v = self.time_input.value.replace(":", "")
        m = int(v[:-2]) if len(v) > 2 else int(v)
        s = int(v[-2:]) if len(v) > 2 else 0

        total_next = m * 60 + s

        data = load_data()
        uid = str(interaction.user.id)
        config = get_user_config(data, uid)

        if curr >= self.limit:
            data[uid] = {**config, "status": "FULL", "finish": None}
            msg = "🔋 Energia cheia!"
        else:
            faltam = self.limit - curr
            total = total_next + ((faltam - 1) * self.recharge)
            finish = datetime.now(timezone.utc) + timedelta(seconds=total)

            data[uid] = {**config, "finish": finish.isoformat(), "status": "RECHARGING"}

            tz = zoneinfo.ZoneInfo(self.tz_code)
            local = finish.astimezone(tz)

            msg = f"⏰ Vai encher às {local.strftime('%H:%M:%S')} em {local.strftime('%d/%m')}"

        save_data(data)
        await interaction.response.send_message(msg, ephemeral=True)

# ---------------- VIEW ----------------

class EnergyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Status", style=discord.ButtonStyle.primary, custom_id="btn_status")
    async def status(self, interaction: discord.Interaction, button):
        data = load_data()
        config = get_user_config(data, interaction.user.id)

        if config["status"] == "FULL":
            return await interaction.response.send_message("🔋 Energia cheia!", ephemeral=True)

        if not config["finish"]:
            return await interaction.response.send_message("Sem dados.", ephemeral=True)

        finish = datetime.fromisoformat(config["finish"])
        now = datetime.now(timezone.utc)

        if now >= finish:
            return await interaction.response.send_message("🔋 Energia cheia!", ephemeral=True)

        diff = finish - now
        await interaction.response.send_message(f"⏳ Falta {diff}", ephemeral=True)

    @discord.ui.button(label="Atualizar", style=discord.ButtonStyle.success, custom_id="btn_update")
    async def update(self, interaction: discord.Interaction, button):
        data = load_data()
        config = get_user_config(data, interaction.user.id)
        await interaction.response.send_modal(EnergyModal(config["max"], config["tz"], config["recharge"]))

    @discord.ui.button(label="Config", style=discord.ButtonStyle.secondary, custom_id="btn_config")
    async def config(self, interaction: discord.Interaction, button):
        await interaction.response.send_message(view=ConfigView(), ephemeral=True)

class ConfigView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)

    @discord.ui.button(label="Tempo", style=discord.ButtonStyle.secondary)
    async def recharge(self, interaction: discord.Interaction, button):
        await interaction.response.send_modal(RechargeModal())

# ---------------- BOT ----------------

class MyBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)

    async def setup_hook(self):
        if not check_energy.is_running():
            check_energy.start()

    async def on_ready(self):
        print(f"✅ Online: {self.user}")

client = MyBot()

@tasks.loop(seconds=10)
async def check_energy():
    data = load_data()
    now = datetime.now(timezone.utc)

    for uid, u in list(data.items()):
        if u.get("finish") and now >= datetime.fromisoformat(u["finish"]):
            try:
                user = await client.fetch_user(int(uid))
                await user.send("🔥 Energia cheia!")
                u["status"] = "FULL"
                u["finish"] = None
            except:
                pass

    save_data(data)

@client.event
async def on_message(message):
    if message.author.bot or not isinstance(message.channel, discord.DMChannel):
        return

    data = load_data()
    config = get_user_config(data, message.author.id)

    msg = await message.channel.send(
        embed=create_panel_embed(config["max"], config["tz"], config["recharge"]),
        view=EnergyView()
    )

    data[str(message.author.id)] = {**config, "last_msg": msg.id}
    save_data(data)

client.run(TOKEN)
