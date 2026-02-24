import discord
from discord.ext import tasks
import os
import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import math

# Configurações
TOKEN = os.getenv("TOKEN")
MAX_ENERGY = 100
RECHARGE_MINUTES = 30
DATA_FILE = "data.json"
BRASILIA = ZoneInfo("America/Sao_Paulo")

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

# --- Funções de Dados ---
def load_data():
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

# --- Eventos ---
@client.event
async def on_ready():
    print(f"✅ Bot online como {client.user}")
    if not check_energy.is_running():
        check_energy.start()

@client.event
async def on_message(message):
    if message.author.bot:
        return

    # O bot responde apenas em Mensagens Diretas (DM)
    if isinstance(message.channel, discord.DMChannel):
        content = message.content.lower().strip()
        data = load_data()
        user_id = str(message.author.id)

        # COMANDO: STATUS
        if content == "status":
            if user_id not in data:
                await message.channel.send("❌ Nenhum contador ativo. Envie sua energia atual (ex: 45).")
                return

            finish_time = datetime.fromisoformat(data[user_id])
            now = datetime.now(timezone.utc)

            if now >= finish_time:
                await message.channel.send("🔋 Sua energia atual é 100.\n\nSua energia já está cheia!")
                return

            # Cálculo da energia atual baseado no tempo restante
            time_left = finish_time - now
            minutes_left = time_left.total_seconds() / 60
            missing_points = minutes_left / RECHARGE_MINUTES
            current_energy = math.floor(MAX_ENERGY - missing_points)

            # Conversão para o fuso de Brasília para exibição
            finish_brasilia = finish_time.astimezone(BRASILIA)

            await message.channel.send(
                f"⚡ Sua energia atual é **{current_energy}**.\n\n"
                f"🔋 Sua energia ficará cheia às **{finish_brasilia.strftime('%H:%M')}** do dia **{finish_brasilia.strftime('%d/%m/%Y')}**."
            )
            return

        # ENTRADA DE DADOS: NÚMERO DE ENERGIA
        try:
            current_energy = int(content)
        except ValueError:
            await message.channel.send("Dica: Envie um número (0-99) para iniciar o timer ou 'status' para verificar.")
            return

        if current_energy >= MAX_ENERGY:
            await message.channel.send("Sua energia já está cheia! Não é necessário iniciar o timer.")
            return

        # Cálculo do tempo necessário para chegar a 100
        missing = MAX_ENERGY - current_energy
        minutes_needed = missing * RECHARGE_MINUTES
        finish_time = datetime.now(timezone.utc) + timedelta(minutes=minutes_needed)

        # Salvar no JSON
        data[user_id] = finish_time.isoformat()
        save_data(data)

        finish_brasilia = finish_time.astimezone(BRASILIA)

        await message.channel.send(
            f"✅ Energia registrada: **{current_energy}**.\n\n"
            f"🔋 Sua energia ficará cheia às **{finish_brasilia.strftime('%H:%M')}** do dia **{finish_brasilia.strftime('%d/%m/%Y')}**."
        )

# --- Task de Verificação (Roda a cada 1 minuto) ---
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
            except Exception as e:
                print(f"Erro ao enviar DM para {user_id}: {e}")

    if changed:
        save_data(data)

client.run(TOKEN)
