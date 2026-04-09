import discord
from discord.ext import tasks
import os
import json
import math
from datetime import datetime, timedelta, timezone
import zoneinfo

TOKEN = os.getenv("TOKEN")

DEFAULT_MAX = 100
DEFAULT_RECHARGE_SECONDS = 1800  # 30 min
DATA_FILE = "data.json"

TIMEZONES = {
    "Brasília (UTC-3)": "America/Sao_Paulo",
    "Manaus (UTC-4)": "America/Manaus",
    "Acre (UTC-5)": "America/Rio_Branco",
    "Fernando de Noronha (UTC-2)": "America/Noronha",
    "Lisboa/Londres (UTC+0)": "Europe/Lisbon",
    "Açores (UTC-1)": "Atlantic/Azores"
}

# ---------------- DATA ---------------- #

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.loads(f.read())
    except:
        return {}

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

# ---------------- UI ---------------- #

def create_panel_embed(user_limit, user_tz_code):
    tz_display = next((name for name, tz in TIMEZONES.items() if tz == user_tz_code), user_tz_code)

    return discord.Embed(
        title="🎒 Mystery Dungeon - Energia Azul 🔹",
        description=(
            f"📍 Fuso Atual: **{tz_display}**\n"
            f"🔋 Limite de energia azul: **{user_limit}**\n\n"
            "⚡ Atualizar Energia: Registra sua energia atual.\n"
            "🔍 Ver Status: Confira sua energia.\n"
            "⚙️ Configurações: Ajustes do bot."
        ),
        color=discord.Color.blue()
    )

# ---------------- MODALS ---------------- #

class RechargeModal(discord.ui.Modal, title="⏱️ Tempo de Recarga"):
    tempo = discord.ui.TextInput(label="Tempo (MM:SS)", placeholder="Ex: 30:00 ou 25:30")

    async def on_submit(self, interaction: discord.Interaction):
        value = self.tempo.value.replace(":", "")

        if not value.isdigit():
            return await interaction.response.send_message("❌ Formato inválido.", ephemeral=True)

        if len(value) <= 2:
            m, s = int(value), 0
        else:
            m, s = int(value[:-2]), int(value[-2:])

        if s > 59:
            return await interaction.response.send_message("❌ Segundos inválidos.", ephemeral=True)

        seconds = m * 60 + s

        data = load_data()
        uid = str(interaction.user.id)
        config = get_user_config(data, uid)

        data[uid] = {**config, "recharge": seconds}
        save_data(data)

        await interaction.response.send_message(f"✅ Tempo atualizado para {m}m {s}s", ephemeral=True)


class EnergyModal(discord.ui.Modal):
    def __init__(self, limit, tz_code, recharge):
        super().__init__(title="⚡ Atualizar Energia")
        self.limit = limit
        self.tz_code = tz_code
        self.recharge = recharge

        self.energy_input = discord.ui.TextInput(label=f'Energia atual (0 a {limit})')
        self.time_input = discord.ui.TextInput(label='Tempo próxima energia (MM:SS)')

        self.add_item(self.energy_input)
        self.add_item(self.time_input)

    async def on_submit(self, interaction: discord.Interaction):
        curr = int(self.energy_input.value)

        v = self.time_input.value.replace(":", "")
        m, s = int(v[:-2] or 0), int(v[-2:] or 0)

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

            msg = (
                f"⚡ Energia: {curr}/{self.limit}\n"
                f"🔋 Vai encher às {local.strftime('%H:%M')} do dia {local.strftime('%d/%m')}"
            )

        save_data(data)
        await interaction.response.send_message(msg, ephemeral=True)

# ---------------- CONFIG VIEW ---------------- #

class MainConfigView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)

    @discord.ui.button(label="Alterar Limite", style=discord.ButtonStyle.secondary)
    async def limit(self, i, b):
        await i.response.send_modal(LimitModal())

    @discord.ui.button(label="Alterar Fuso", style=discord.ButtonStyle.secondary)
    async def tz(self, i, b):
        await i.response.edit_message(view=TimezoneOptionsView())

    @discord.ui.button(label="Tempo de Recarga", style=discord.ButtonStyle.secondary)
    async def recharge(self, i, b):
        await i.response.send_modal(RechargeModal())

# ---------------- OUTROS ---------------- #

class LimitModal(discord.ui.Modal, title="Limite"):
    val = discord.ui.TextInput(label="Novo limite")

    async def on_submit(self, i):
        data = load_data()
        uid = str(i.user.id)
        config = get_user_config(data, uid)

        data[uid] = {**config, "max": int(self.val.value)}
        save_data(data)

        await i.response.send_message("✅ Atualizado", ephemeral=True)


class TimezoneOptionsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)

        select = discord.ui.Select(
            options=[discord.SelectOption(label=k, value=v) for k, v in TIMEZONES.items()]
        )

        async def callback(interaction):
            data = load_data()
            uid = str(interaction.user.id)
            config = get_user_config(data, uid)

            data[uid] = {**config, "tz": interaction.data["values"][0]}
            save_data(data)

            await interaction.response.send_message("✅ Fuso atualizado", ephemeral=True)

        select.callback = callback
        self.add_item(select)

# ---------------- BOT ---------------- #

class EnergyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Status da Energia", style=discord.ButtonStyle.primary, custom_id="status")
    async def status(self, interaction, button):
        data = load_data()
        uid = str(interaction.user.id)
        u = data.get(uid)

        if not u or not u.get("finish"):
            return await interaction.response.send_message("Sem dados.", ephemeral=True)

        finish = datetime.fromisoformat(u["finish"])
        tz = zoneinfo.ZoneInfo(u.get("tz", "America/Sao_Paulo"))

        local = finish.astimezone(tz)

        await interaction.response.send_message(
            f"🔋 Vai encher às {local.strftime('%H:%M')} do dia {local.strftime('%d/%m')}",
            ephemeral=True
        )

    @discord.ui.button(label="Atualizar Energia", style=discord.ButtonStyle.success, custom_id="update")
    async def update(self, interaction, button):
        data = load_data()
        config = get_user_config(data, interaction.user.id)

        await interaction.response.send_modal(
            EnergyModal(config["max"], config["tz"], config["recharge"])
        )

    @discord.ui.button(label="Configurações", style=discord.ButtonStyle.secondary, custom_id="config")
    async def config(self, interaction, button):
        await interaction.response.send_message("⚙️ Configurações:", view=MainConfigView(), ephemeral=True)

class MyBot(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())

    async def setup_hook(self):
        self.add_view(EnergyView())
        check_energy.start()

    async def on_ready(self):
        print(f"✅ Online: {self.user}")

client = MyBot()

@tasks.loop(seconds=10)
async def check_energy():
    data = load_data()
    now = datetime.now(timezone.utc)

    for uid, u in data.items():
        if u.get("finish") and now >= datetime.fromisoformat(u["finish"]):
            try:
                user = await client.fetch_user(int(uid))
                await user.send("🔥 Sua energia encheu!")
                u["finish"] = None
                u["status"] = "FULL"
            except:
                pass

    save_data(data)

@client.event
async def on_message(msg):
    if msg.author.bot:
        return

    data = load_data()
    uid = str(msg.author.id)
    config = get_user_config(data, uid)

    new = await msg.channel.send(embed=create_panel_embed(config["max"], config["tz"]), view=EnergyView())

    data[uid] = {**config, "last_msg": new.id}
    save_data(data)

client.run(TOKEN)
