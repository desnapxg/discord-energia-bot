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
DEFAULT_RECHARGE_SECONDS = 1800  # 30 minutos padrão
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

# ---------------- EMBED ---------------- #

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

# ---------------- MODALS ---------------- #

class RechargeModal(discord.ui.Modal, title="⏱️ Tempo de Recarga"):
    tempo = discord.ui.TextInput(label="Tempo (MM:SS)", placeholder="Ex: 30:00 ou 25:30")

    async def on_submit(self, interaction: discord.Interaction):
        v = self.tempo.value.replace(":", "")
        if not v.isdigit():
            return await interaction.response.send_message("❌ Formato inválido.", ephemeral=True)

        m, s = int(v[:-2] or 0), int(v[-2:] or 0)
        if s > 59:
            return await interaction.response.send_message("❌ Segundos inválidos.", ephemeral=True)

        seconds = m * 60 + s

        data = load_data()
        uid = str(interaction.user.id)
        config = get_user_config(data, uid)

        data[uid] = {**config, "recharge": seconds}
        save_data(data)

        await interaction.response.send_message(f"✅ Tempo atualizado para {m}m {s}s.", ephemeral=True)


class EnergyModal(discord.ui.Modal):
    def __init__(self, limit, tz_code, recharge):
        super().__init__(title="⚡ Atualizar Energia Azul 🔹")
        self.limit = limit
        self.tz_code = tz_code
        self.recharge = recharge

        self.energy_input = discord.ui.TextInput(
            label=f'Energia azul atual (0 a {limit})', 
            placeholder='Ex: 58'
        )

        self.time_input = discord.ui.TextInput(
            label='Tempo para recarregar a próxima energia azul:',
            placeholder='Ex: 29:59 ou 2959'
        )

        self.add_item(self.energy_input)
        self.add_item(self.time_input)

    async def on_submit(self, interaction: discord.Interaction):
        curr = int(self.energy_input.value)

        v = self.time_input.value.replace(":", "")
        m, s = int(v[:-2] or 0), int(v[-2:] or 0)

        total_next_seconds = m * 60 + s

        data = load_data()
        uid = str(interaction.user.id)
        config = get_user_config(data, uid)

        if curr >= self.limit:
            data[uid] = {**config, "status": "FULL", "finish": None}
            msg = "✅ Sua **energia azul** está cheia!"
        else:
            faltam = self.limit - curr
            total = total_next_seconds + ((faltam - 1) * self.recharge)

            finish = datetime.now(timezone.utc) + timedelta(seconds=total)
            data[uid] = {**config, "finish": finish.isoformat(), "status": "RECHARGING"}

            tz = zoneinfo.ZoneInfo(self.tz_code)
            local = finish.astimezone(tz)

            msg = (
                f"🔹 **Energia azul atualizada: {curr}/{self.limit}**\n"
                f"⏳ Falta: `{m}m {s}s` para recarregar a próxima energia\n"
                f"⏰ Ficará cheia às: `{local.strftime('%H:%M:%S')}` em `{local.strftime('%d/%m')}`"
            )

        save_data(data)
        await interaction.response.send_message(msg, ephemeral=True)

# ---------------- CONFIG ---------------- #

class MainConfigView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)

    @discord.ui.button(label="Alterar Limite", style=discord.ButtonStyle.secondary, emoji="📏")
    async def go_limit(self, interaction, button):
        await interaction.response.send_modal(LimitModal())

    @discord.ui.button(label="Alterar Fuso", style=discord.ButtonStyle.secondary, emoji="🌐")
    async def go_tz(self, interaction, button):
        await interaction.response.edit_message(
            content="🌐 Escolha o fuso horário:",
            view=TimezoneOptionsView()
        )

    @discord.ui.button(label="Tempo de Recarga", style=discord.ButtonStyle.secondary, emoji="⏱️")
    async def go_recharge(self, interaction, button):
        await interaction.response.send_modal(RechargeModal())

    @discord.ui.button(label="Voltar ao Início", style=discord.ButtonStyle.danger, emoji="🏠")
    async def back(self, interaction, button):
        data = load_data()
        config = get_user_config(data, interaction.user.id)

        await interaction.response.edit_message(
            content=None,
            embed=create_panel_embed(config["max"], config["tz"]),
            view=EnergyView()
        )

class LimitModal(discord.ui.Modal, title='📏 Limite de Energia Azul'):
    limit_input = discord.ui.TextInput(label='Novo limite máximo:')

    async def on_submit(self, interaction):
        data = load_data()
        uid = str(interaction.user.id)
        config = get_user_config(data, uid)

        data[uid] = {**config, "max": int(self.limit_input.value)}
        save_data(data)

        await interaction.response.send_message("✅ Limite atualizado!", ephemeral=True)

class TimezoneOptionsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        select = discord.ui.Select(
            options=[discord.SelectOption(label=name, value=tz) for name, tz in TIMEZONES.items()]
        )
        select.callback = self.callback
        self.add_item(select)

    async def callback(self, interaction):
        data = load_data()
        uid = str(interaction.user.id)
        config = get_user_config(data, uid)

        data[uid] = {**config, "tz": interaction.data['values'][0]}
        save_data(data)

        await interaction.response.send_message("✅ Fuso horário atualizado!", ephemeral=True)

# ---------------- BOT ---------------- #

class EnergyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Status da Energia", style=discord.ButtonStyle.primary, emoji="🔍", custom_id="status")
    async def status(self, interaction, button):
        data = load_data()
        uid = str(interaction.user.id)
        u = data.get(uid)

        if not u or u.get("status") is None:
            return await interaction.response.send_message("Sua energia azul ainda não está sendo monitorada.", ephemeral=True)

        limit = u.get("max", DEFAULT_MAX)
        recharge = u.get("recharge", DEFAULT_RECHARGE_SECONDS)

        if u.get("status") == "FULL":
            return await interaction.response.send_message(f"🔋 Energia cheia! ({limit}/{limit})", ephemeral=True)

        finish = datetime.fromisoformat(u["finish"])
        now = datetime.now(timezone.utc)

        diff = finish - now
        total_secs = diff.total_seconds()

        pontos_faltantes = math.ceil(total_secs / recharge)
        current = max(0, limit - pontos_faltantes)

        h, rem = divmod(int(total_secs), 3600)
        m, s = divmod(rem, 60)

        tz = zoneinfo.ZoneInfo(u.get("tz"))
        local = finish.astimezone(tz)

        await interaction.response.send_message(
            f"🔹 **Energia atual: {current}/{limit}**\n"
            f"⏳ Falta: `{h}h {m}m {s}s` para completar.\n"
            f"⏰ Ficará cheia às: `{local.strftime('%H:%M:%S')}` em `{local.strftime('%d/%m')}`",
            ephemeral=True
        )

    @discord.ui.button(label="Atualizar Energia", style=discord.ButtonStyle.success, emoji="⚡", custom_id="update")
    async def update(self, interaction, button):
        data = load_data()
        config = get_user_config(data, interaction.user.id)

        await interaction.response.send_modal(
            EnergyModal(config["max"], config["tz"], config["recharge"])
        )

    @discord.ui.button(label="Configurações", style=discord.ButtonStyle.secondary, emoji="⚙️", custom_id="config")
    async def config(self, interaction, button):
        await interaction.response.send_message("⚙️ Configurações:", view=MainConfigView(), ephemeral=True)

# ---------------- CLIENT ---------------- #

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
        print(f"✅ Bot Online: {self.user}")

client = MyBot()

@tasks.loop(seconds=10)
async def check_energy():
    data = load_data()
    now = datetime.now(timezone.utc)
    changed = False

    for uid, u in data.items():
        if u.get("finish") and now >= datetime.fromisoformat(u["finish"]):
            try:
                user = await client.fetch_user(int(uid))
                await user.send(f"🔥 **Sua energia azul chegou em {u.get('max')}. Hora de Mystery Dungeon!**")
                u["status"] = "FULL"
                u["finish"] = None
                changed = True
            except:
                pass

    if changed:
        save_data(data)

if __name__ == "__main__":
    client.run(TOKEN)
