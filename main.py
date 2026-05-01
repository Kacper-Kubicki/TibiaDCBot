import discord
from discord import app_commands
from datetime import datetime, timedelta
import json
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

ALLOWED_GUILDS = [
    1491732541206429716, #dev
    1419989925776068740 # perla
]

channels = {}

ADMIN_IDS = [   # ID adminow
    470943158910320640, #ja
    112748817085972480, #guga
    1338184027529547778 #royek
]

# do testow lokalnych
GUILD_ID = 1491732541206429716  # Twój serwer testowy
TEST_GUILD = discord.Object(id=GUILD_ID)

DUMMIES = [
    "Kukła 1",
    "Kukła 2",
    "Kukła 3"
]


intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

DATA_FILE = "data.json"

# ====== DANE ======
bookings = []
registered_users = {}
message_id = None  # ID wiadomości z listą
booking_start = None
booking_end = None

# ====== HELPER ======
def is_admin(user_id):
    return user_id in ADMIN_IDS

# ====== SPRAWDZENIE KANALU ======
def is_correct_channel(interaction):
    # 1. sprawdź serwer
    if interaction.guild_id not in ALLOWED_GUILDS:
        return False

    # 2. sprawdź kanał
    guild_channel = channels.get(str(interaction.guild_id))

    if guild_channel is None:
        return False  # kanał nie ustawiony

    return interaction.channel_id == guild_channel
# ====== ZAPIS / ODCZYT ======
def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump({
            "bookings": bookings,
            "users": registered_users,
            "message_id": message_id,
            "booking_start": booking_start,
            "booking_end": booking_end,
            "channels": channels
        }, f, indent=4)

def load_data():
    global bookings, registered_users, message_id, booking_start, booking_end, channels

    if not os.path.exists(DATA_FILE):
        return

    with open(DATA_FILE, "r") as f:
        data = json.load(f)
        bookings = data.get("bookings", [])
        registered_users = data.get("users", {})
        message_id = data.get("message_id", None)
        booking_start = data.get("booking_start", None)
        booking_end =  data.get("booking_end", None)
        channels = data.get("channels", {})

# ====== DATY ======
def generate_dates():
    if not booking_start or not booking_end:
        return []

    start = datetime.strptime(booking_start, "%Y-%m-%d %H:%M")
    end = datetime.strptime(booking_end, "%Y-%m-%d %H:%M")

    dates = []
    current = start.date()
    end_date = end.date()

    while current <= end_date:
        dates.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)

    return dates

# ====== AUTOCOMPLETE ======
async def dummy_autocomplete(interaction, current):
    return [
        app_commands.Choice(name=d, value=d)
        for d in DUMMIES
        if current.lower() in d.lower()
    ][:25]

async def date_autocomplete(interaction, current):
    return [
        app_commands.Choice(name=d, value=d)
        for d in generate_dates()
        if current.lower() in d.lower()
    ][:25]

def generate_hours_for_date(date_str):
    if not booking_start or not booking_end:
        return []

    start = datetime.strptime(booking_start, "%Y-%m-%d %H:%M")
    end = datetime.strptime(booking_end, "%Y-%m-%d %H:%M")
    selected_date = datetime.strptime(date_str, "%Y-%m-%d")

    hours = []

    for h in range(0, 24):
        current = selected_date.replace(hour=h, minute=0)

        if current < start:
            continue
        if current > end:
            continue

        hours.append(f"{h}:00")

    return hours

async def hour_autocomplete(interaction, current):
    date = None

    for option in interaction.data.get("options", []):
        if option["name"] == "date":
            date = option["value"]

    if not date:
        return []

    hours = generate_hours_for_date(date)

    return [
        app_commands.Choice(name=h, value=h)
        for h in hours
        if current.lower() in h.lower()
    ][:25]

# ====== REJESTRACJA ======
@tree.command(name="rg", description="Rejestracja")
async def register(interaction: discord.Interaction, name: str):

    if not is_correct_channel(interaction):
        await interaction.response.send_message("❌ Używaj bota tylko na wyznaczonym kanale.",ephemeral=True)
        return

    registered_users[str(interaction.user.id)] = name
    save_data()

    await interaction.response.send_message(f"✅ Zarejestrowano jako {name}", ephemeral=True)
    await update_list(interaction.channel)

# ====== SPRAWDZANIE REJESTRACJI=====
def is_registered(user_id):
    return str(user_id) in registered_users

# ====== BOOK ======
@tree.command(name="book")
@app_commands.autocomplete(dummy = dummy_autocomplete, date=date_autocomplete, start=hour_autocomplete, end=hour_autocomplete)
async def book(interaction: discord.Interaction, dummy: str, date: str, start: str, end: str):

    if not is_registered(interaction.user.id):
        await interaction.response.send_message("❌ Najpierw użyj /rg", ephemeral=True)
        return

    if not is_correct_channel(interaction):
        await interaction.response.send_message("❌ Używaj bota tylko na wyznaczonym kanale.",ephemeral=True)
        return

    if dummy not in DUMMIES:
        await interaction.response.send_message("❌ Nieprawidłowa kukła", ephemeral=True)
        return

    start_hour = int(start.split(":")[0])
    end_hour = int(end.split(":")[0])

    # pozwalamy na przejście przez północ
    same_day = True

    if end_hour <= start_hour:
        same_day = False

    user_start = datetime.strptime(f"{date} {start}", "%Y-%m-%d %H:%M")
    user_end = datetime.strptime(f"{date} {end}", "%Y-%m-%d %H:%M")

    if not same_day:
        user_end += timedelta(days=1)

    for b in bookings:
        if b["dummy"] != dummy:
            continue

        existing_start = datetime.strptime(f"{b['date']} {b['start']}:00", "%Y-%m-%d %H:%M")
        existing_end = datetime.strptime(f"{b['date']} {b['end']}:00", "%Y-%m-%d %H:%M")

        # jeśli rezerwacja przechodziła przez północ
        if b["end"] <= b["start"]:
            existing_end += timedelta(days=1)

        # sprawdzanie overlap
        if not (user_end <= existing_start or user_start >= existing_end):
            await interaction.response.send_message("❌ Podana data jest już zarezerwowana", ephemeral=True)
            return

    if booking_start and booking_end:

        start_range = datetime.strptime(booking_start, "%Y-%m-%d %H:%M")
        end_range = datetime.strptime(booking_end, "%Y-%m-%d %H:%M")

        if user_start < start_range or user_end > end_range:
            await interaction.response.send_message(
                "❌ Rezerwacja poza dozwolonym zakresem.",
                ephemeral=True
            )
            return

    bookings.append({
        "dummy": dummy,
        "date": date,
        "start": start_hour,
        "end": end_hour,
        "user_id": str(interaction.user.id)
    })

    save_data()
    await interaction.response.send_message("✅ Zarezerwowano", ephemeral=True)
    await update_list(interaction.channel)

# ====== CANCEL ======
async def cancel_autocomplete(interaction, current):
    user_bookings = [b for b in bookings if b["user_id"] == str(interaction.user.id)]

    return [
        app_commands.Choice(
            name=f"[{b['dummy']}] {b['date']} {b['start']}:00–{b['end']}:00",
            value=str(i)
        )
        for i, b in enumerate(user_bookings)
    ][:25]

@tree.command(name="cancel")
@app_commands.autocomplete(reservation=cancel_autocomplete)
async def cancel(interaction: discord.Interaction, reservation: str):

    if not is_correct_channel(interaction):
        await interaction.response.send_message("❌ Używaj bota tylko na wyznaczonym kanale.",ephemeral=True)
        return

    user_bookings = [b for b in bookings if b["user_id"] == str(interaction.user.id)]

    index = int(reservation)
    if index >= len(user_bookings):
        await interaction.response.send_message("❌ Błąd", ephemeral=True)
        return

    bookings.remove(user_bookings[index])
    save_data()

    await interaction.response.send_message("🗑 Usunięto", ephemeral=True)
    await update_list(interaction.channel)

# ====== CZYSZCZENIE LISTY ======
@tree.command(name="reset", description="Reset wszystkich rezerwacji")
async def reset(interaction: discord.Interaction):

    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ Nie masz uprawnień.", ephemeral=True)
        return

    global bookings

    bookings.clear()
    save_data()

    await interaction.response.send_message("🧹 Wszystkie rezerwacje zostały usunięte.", ephemeral=True)
    await update_list(interaction.channel)

# ====== WYŚWIETL LISTĘ UŻYTKOWNIKÓW ======
@tree.command(name="users", description="Lista zarejestrowanych użytkowników")
async def users(interaction: discord.Interaction):

    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ Nie masz uprawnień.", ephemeral=True)
        return

    if not registered_users:
        await interaction.response.send_message("📭 Brak zarejestrowanych użytkowników.", ephemeral=True)
        return

    description = "\n".join([
        f"• {name} "
        for user_id, name in registered_users.items()
    ])

    embed = discord.Embed(
        title="👥 Zarejestrowani użytkownicy",
        description=description,
        color=discord.Color.green()
    )

    await interaction.response.send_message(embed=embed, ephemeral=True)

# ====== USTAWIENIE DATY EVENTU ======
@tree.command(name="setrange", description="Ustaw zakres rezerwacji")
async def setrange(
    interaction: discord.Interaction,
    start_date: str,
    start_hour: str,
    end_date: str,
    end_hour: str
):

    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ Nie masz uprawnień.", ephemeral=True)
        return

    global booking_start, booking_end

    try:
        start_dt = datetime.strptime(f"{start_date} {start_hour}", "%Y-%m-%d %H:%M")
        end_dt = datetime.strptime(f"{end_date} {end_hour}", "%Y-%m-%d %H:%M")
    except:
        await interaction.response.send_message(
            "❌ Format: YYYY-MM-DD HH:MM",
            ephemeral=True
        )
        return

    if start_dt >= end_dt:
        await interaction.response.send_message("❌ Początek musi być przed końcem", ephemeral=True)
        return

    booking_start = start_dt.strftime("%Y-%m-%d %H:%M")
    booking_end = end_dt.strftime("%Y-%m-%d %H:%M")

    save_data()

    await interaction.response.send_message(
        f"✅ Zakres ustawiony:\n{booking_start} → {booking_end}",
        ephemeral=True
    )
# ====== USTAWIANIE KANAŁU ======
@tree.command(name="setchannel", description="Ustaw kanał rezerwacji")
async def setchannel(interaction: discord.Interaction):

    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ Brak uprawnień", ephemeral=True)
        return

    if interaction.guild_id not in ALLOWED_GUILDS:
        await interaction.response.send_message("❌ Ten serwer nie jest dozwolony", ephemeral=True)
        return

    channels[str(interaction.guild_id)] = interaction.channel_id
    save_data()

    await interaction.response.send_message("✅ Kanał ustawiony!", ephemeral=True)

# ====== AKTUALIZACJA LISTY ======
async def update_list(channel):
    global message_id

    from collections import defaultdict

    sorted_bookings = sorted(bookings, key=lambda b: (b["dummy"], b["date"], b["start"]))

    grouped = defaultdict(list)

    for b in sorted_bookings:
        grouped[b["dummy"]].append(b)

    if grouped:
        parts = []

        for dummy, items in grouped.items():
            part = [f"**{dummy}**"]
            for b in items:
                part.append(
                    f"• {b['date']} | {b['start']}:00–{b['end']}:00 — {registered_users.get(b['user_id'], '???')}"
                )
            parts.append("\n".join(part))

        description = "\n\n".join(parts)
    else:
        description = "📭 Brak rezerwacji"

    embed = discord.Embed(
        title = f"📅 Rezerwacje\n🟢 Początek eventu {booking_start}\n🔴 Koniec eventu {booking_end}",
        description=description,
        color=discord.Color.blue()
    )

    embed.set_thumbnail(url="https://media.tenor.com/6d-iB6DGJXUAAAAi/tibia-ferumbras-ferumbras.gif")

    try:
        if message_id:
            old_message = await channel.fetch_message(message_id)
            await old_message.delete()
    except:
        pass

    new_message = await channel.send(embed=embed)



    message_id = new_message.id
    save_data()



# ====== START ======
@client.event
async def on_ready():
    load_data()
    await tree.sync()
    #await tree.sync(guild=TEST_GUILD)
    print(f"Zalogowano jako {client.user}")

client.run(TOKEN)