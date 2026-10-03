import asyncio
import os
import random
import sqlite3
import time
from datetime import datetime, timedelta

import discord
from discord import app_commands
from discord.ext import commands

# =========================================================
# CONFIG & TOKEN & ADMIN
# =========================================================

TOKEN = "MTU1NDkxMTkyMjQ4NTIwNzA5MA.GvrweG.GctYRpcebOhS0aWIkeC_7WKQz_RBJ7vo5e7JEI"

ADMIN_IDS = [
    1551927144534380676,
]

START_POINTS = 0        
MIN_BET = 3000  # Mức cược tối thiểu chơi game là 3k VNĐ
MAX_BET = 10000000

MIN_BET_FOR_ITEM = 1000  # Cược từ 1k trở lên là có cơ hội nhận quà VIP Blox Fruits!

# TỈ LỆ ĐÃ CẬP NHẬT THEO YÊU CẦU
ITEM_REAL_DROP_RATE = 2.0      # Tỉ lệ nổ quà thật 2%
JACKPOT_RATE = 0.0099          # Tỉ lệ nổ hũ Jackpot 0.99%

# GIF Direct Links
GIF_MONEY_TRANSFER = "https://i.postimg.cc/85zPy2z1/money-transfer.gif"  
GIF_ROYAL_GRANT = "https://i.postimg.cc/mD83BhhR/gold-coins.gif"
GIF_SHAKING_DICE = "https://i.postimg.cc/vT4Qx31k/dice-roll.gif"

# =========================================================
# BLOX FRUITS ITEM CONFIG
# =========================================================
BLOX_FRUIT_ITEMS = [
    {
        "name": "2x Boss Drops Chance", 
        "icon": "👑", 
        "url": "https://static.wikia.nocookie.net/roblox-blox-piece/images/3/3a/BadgeBossDrops.png"
    },
    {
        "name": "Fast Boats", 
        "icon": "🚤", 
        "url": "https://static.wikia.nocookie.net/roblox-blox-piece/images/f/fa/BadgeBoats.png"
    },
    {
        "name": "2x Money", 
        "icon": "💰", 
        "url": "https://static.wikia.nocookie.net/roblox-blox-piece/images/c/cf/BadgeMoneyx2.png"
    },
    {
        "name": "2x Mastery", 
        "icon": "⚡", 
        "url": "https://static.wikia.nocookie.net/roblox-blox-piece/images/1/16/BadgeMasteryx2.png"
    },
    {
        "name": "Dark Blade", 
        "icon": "⚔️", 
        "url": "https://static.wikia.nocookie.net/roblox-blox-piece/images/7/7f/BadgeDarkBlade.png"
    }
]

def get_random_show_item():
    return random.choice(BLOX_FRUIT_ITEMS)

def check_real_item_claim(bet_amount: int):
    if bet_amount >= MIN_BET_FOR_ITEM:
        # Tỉ lệ 2% (random từ 1 đến 100 <= 2)
        if random.uniform(1, 100) <= ITEM_REAL_DROP_RATE:
            return True
    return False

def check_jackpot_claim():
    # Tỉ lệ 0.99% (random từ 0 đến 100 < 0.99)
    return random.uniform(0, 100) < 0.99

# Database SQLite
db = sqlite3.connect("casino_giant.db", check_same_thread=False)

db.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    points INTEGER NOT NULL DEFAULT 0,
    wins INTEGER NOT NULL DEFAULT 0,
    losses INTEGER NOT NULL DEFAULT 0,
    total_games INTEGER NOT NULL DEFAULT 0,
    vip_rank TEXT NOT NULL DEFAULT '🥉 Đồng'
)
""")

db.execute("""
CREATE TABLE IF NOT EXISTS jackpot_fund (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    pool INTEGER NOT NULL DEFAULT 500000
)
""")

db.execute("INSERT OR IGNORE INTO jackpot_fund (id, pool) VALUES (1, 500000)")
db.commit()
db_lock = asyncio.Lock()

baccarat_queues = {}
xocdia_lobbies = {}
bacc_history = []

# =========================================================
# DATABASE HELPER FUNCTIONS
# =========================================================

def get_vip_rank(total_games: int):
    if total_games >= 200: return "💎 Kim Cương"
    elif total_games >= 100: return "🥇 Vàng"
    elif total_games >= 50: return "🥈 Bạc"
    return "🥉 Đồng"

async def create_user(user_id: int):
    async with db_lock:
        db.execute("INSERT OR IGNORE INTO users (user_id, points, wins, losses, total_games, vip_rank) VALUES (?, ?, 0, 0, 0, '🥉 Đồng')", (user_id, START_POINTS))
        db.commit()

async def get_user(user_id: int):
    await create_user(user_id)
    async with db_lock:
        cur = db.execute("SELECT user_id, points, wins, losses, total_games, vip_rank FROM users WHERE user_id = ?", (user_id,))
        return cur.fetchone()

async def set_points(user_id: int, amount: int):
    await create_user(user_id)
    async with db_lock:
        cur = db.execute("SELECT total_games FROM users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        total_g = row[0] if row else 0
        new_vip = get_vip_rank(total_g)
        db.execute("UPDATE users SET points = ?, vip_rank = ? WHERE user_id = ?", (max(0, amount), new_vip, user_id))
        db.commit()

async def add_points(user_id: int, amount: int):
    await create_user(user_id)
    async with db_lock:
        cur = db.execute("SELECT points, total_games FROM users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        current_pts = row[0] if row else START_POINTS
        total_g = row[1] if row else 0
        
        new_pts = max(0, current_pts + amount)
        new_vip = get_vip_rank(total_g)
        
        db.execute("UPDATE users SET points = ?, vip_rank = ? WHERE user_id = ?", (new_pts, new_vip, user_id))
        db.commit()

async def update_result(user_id: int, points_change: int, win: bool):
    await create_user(user_id)
    async with db_lock:
        cur = db.execute("SELECT points, total_games FROM users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        current_pts = row[0] if row else START_POINTS
        total_g = row[1] if row else 0
        
        new_pts = max(0, current_pts + points_change)
        new_total = total_g + 1
        new_vip = get_vip_rank(new_total)

        if win:
            db.execute("UPDATE users SET points = ?, wins = wins + 1, total_games = ?, vip_rank = ? WHERE user_id = ?", (new_pts, new_total, new_vip, user_id))
        else:
            db.execute("UPDATE users SET points = ?, losses = losses + 1, total_games = ?, vip_rank = ? WHERE user_id = ?", (new_pts, new_total, new_vip, user_id))
        db.commit()

async def get_jackpot():
    async with db_lock:
        cur = db.execute("SELECT pool FROM jackpot_fund WHERE id = 1")
        row = cur.fetchone()
        return row[0] if row else 500000

async def add_jackpot(amount: int):
    async with db_lock:
        db.execute("UPDATE jackpot_fund SET pool = pool + ? WHERE id = 1", (amount,))
        db.commit()

async def reset_jackpot():
    async with db_lock:
        db.execute("UPDATE jackpot_fund SET pool = 500000 WHERE id = 1")
        db.commit()

# =========================================================
# BOT SETUP
# =========================================================

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

# =========================================================
# SYSTEM COMMANDS
# =========================================================

@bot.tree.command(name="help", description="Xem danh sách các lệnh Casino")
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🎰 BẢNG HƯỚNG DẪN CASINO HOÀNG GIA 🎰",
        description="Chào mừng bạn đến với sòng bạc Hoàng Gia! Dưới đây là danh sách các lệnh hỗ trợ:",
        color=discord.Color.gold()
    )
    embed.add_field(name="💳 /sodu", value="Xem số dư tài khoản, rank VIP và Hũ Jackpot", inline=True)
    embed.add_field(name="🔍 /checktien", value="Kiểm tra số dư tài khoản người chơi khác", inline=True)
    embed.add_field(name="💸 /chuyentien", value="Chuyển tiền cho người chơi khác trong server", inline=True)
    embed.add_field(name="🏆 /bxh", value="Xem bảng xếp hạng top đại gia", inline=True)
    embed.add_field(name="🎴 /baccarat", value="Mở bàn Baccarat Cân Bằng", inline=False)
    embed.add_field(name="🎲 /xocdia", value="Mở bàn Xóc Đĩa Chuẩn Xác Suất", inline=False)
    
    if interaction.user.id in ADMIN_IDS:
        embed.add_field(
            name="👑 LỆNH QUẢN TRỊ (ADMIN)",
            value="`/congtien` - Bơm tiền cho người chơi\n`/trutien` - Tịch thu tài sản\n`/setmoney` - Đặt lại chính xác số tiền",
            inline=False
        )
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="sodu", description="Xem số dư tài khoản, rank VIP và Hũ Jackpot của bạn")
async def sodu_cmd(interaction: discord.Interaction):
    user = await get_user(interaction.user.id)
    jp = await get_jackpot()
    embed = discord.Embed(title=f"💳 THÔNG TIN TÀI KHOẢN - {interaction.user.display_name}", color=discord.Color.gold())
    
    embed.add_field(name="💰 Số Dư Tài Khoản:", value=f"### 🟡 {user[1]:,} VNĐ", inline=False)
    embed.add_field(name="🏅 Cấp VIP:", value=f"{user[5]} (Tổng ván: {user[4]})", inline=True)
    embed.add_field(name="📈 Thắng / Thua:", value=f"{user[2]} / {user[3]}", inline=True)
    embed.add_field(name="🎁 Hũ Jackpot Chung:", value=f"### ✨ {jp:,} VNĐ", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="checktien", description="Xem số dư tài khoản và thông tin của một thành viên khác")
@app_commands.describe(target="Thành viên bạn muốn kiểm tra số dư")
async def checktien_cmd(interaction: discord.Interaction, target: discord.User):
    user = await get_user(target.id)
    jp = await get_jackpot()
    
    embed = discord.Embed(
        title=f"💳 THÔNG TIN TÀI KHOẢN - {target.display_name}", 
        color=discord.Color.blue()
    )
    if target.display_avatar:
        embed.set_thumbnail(url=target.display_avatar.url)
        
    embed.add_field(name="💰 Số Dư Thành Viên:", value=f"### 🔵 {user[1]:,} VNĐ", inline=False)
    embed.add_field(name="🏅 Cấp VIP:", value=f"{user[5]} (Tổng ván: {user[4]})", inline=True)
    embed.add_field(name="📈 Thắng / Thua:", value=f"{user[2]} / {user[3]}", inline=True)
    embed.add_field(name="🎁 Hũ Jackpot Chung:", value=f"### ✨ {jp:,} VNĐ", inline=False)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="chuyentien", description="Chuyển tiền cho người chơi khác")
@app_commands.describe(target="Người nhận tiền", amount="Số tiền chuyển")
async def chuyentien_cmd(interaction: discord.Interaction, target: discord.User, amount: int):
    if target.id == interaction.user.id:
        await interaction.response.send_message("❌ Bạn không thể tự chuyển tiền cho chính mình!", ephemeral=True)
        return
    if amount < 1000:
        await interaction.response.send_message("❌ Số tiền chuyển tối thiểu là 1,000 VNĐ!", ephemeral=True)
        return

    sender = await get_user(interaction.user.id)
    if sender[1] < amount:
        await interaction.response.send_message(f"❌ Bạn không đủ tiền! Số dư hiện tại: `{sender[1]:,} VNĐ`", ephemeral=True)
        return

    await add_points(interaction.user.id, -amount)
    await add_points(target.id, amount)
    
    embed = discord.Embed(
        title="💸 GIAO DỊCH CHUYỂN TIỀN THÀNH CÔNG",
        description=f"👤 **Người chuyển:** <@{interaction.user.id}> (`{interaction.user.display_name}`)\n"
                    f"🎯 **Người nhận:** <@{target.id}> (`{target.display_name}`)\n\n"
                    f"💵 **Số tiền giao dịch:**\n### 🟢 +{amount:,} VNĐ",
        color=discord.Color.green()
    )
    embed.set_thumbnail(url=GIF_MONEY_TRANSFER)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="bxh", description="Xem bảng xếp hạng đại gia")
async def bxh_cmd(interaction: discord.Interaction):
    async with db_lock:
        cur = db.execute("SELECT user_id, points, vip_rank FROM users ORDER BY points DESC LIMIT 10")
        rows = cur.fetchall()

    embed = discord.Embed(title="🏆 BẢNG XẾP HẠNG ĐẠI GIA", color=discord.Color.gold())
    desc = ""
    for idx, r in enumerate(rows, start=1):
        member = interaction.guild.get_member(r[0]) if interaction.guild else None
        name = member.display_name if member else f"ID: {r[0]}"
        icon = "🥇" if idx == 1 else ("🥈" if idx == 2 else ("🥉" if idx == 3 else f"`#{idx}`"))
        desc += f"{icon} **{name}** • **{r[1]:,} VNĐ** ({r[2]})\n"

    embed.description = desc if desc else "Chưa có dữ liệu."
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="congtien", description="[ADMIN] Ban hành sắc lệnh bơm tiền hoàng gia cho người chơi")
@app_commands.describe(target="Người nhận sắc lệnh", amount="Số tiền bơm")
async def congtien_cmd(interaction: discord.Interaction, target: discord.User, amount: int):
    if interaction.user.id not in ADMIN_IDS:
        await interaction.response.send_message("❌ Bạn không có quyền Admin để sử dụng sắc lệnh này!", ephemeral=True)
        return

    await add_points(target.id, amount)
    updated_user = await get_user(target.id)
    new_balance = updated_user[1]

    embed = discord.Embed(
        title="👑 📜 SẮC LỆNH HOÀNG GIA - BƠM TIỀN ĐẠI GIA 📜 👑",
        description=f"👤 **Đại gia được nhận:** <@{target.id}> (`{target.display_name}`)\n"
                    f"💰 **Số tiền bơm thêm:**\n### 🟡 +{amount:,} VNĐ\n\n"
                    f"💎 **Số dư hiện tại:**\n### ✨ {new_balance:,} VNĐ",
        color=discord.Color.from_rgb(255, 215, 0)
    )
    embed.set_thumbnail(url=GIF_ROYAL_GRANT)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="trutien", description="[ADMIN] Ban hành lệnh tịch thu, trừ tiền tài sản của người chơi")
@app_commands.describe(target="Người bị phạt", amount="Số tiền trừ", lydo="Lý do tịch thu tài sản")
async def trutien_cmd(interaction: discord.Interaction, target: discord.User, amount: int, lydo: str = "Vi phạm nội quy sòng bạc"):
    if interaction.user.id not in ADMIN_IDS:
        await interaction.response.send_message("❌ Bạn không có quyền Admin để sử dụng lệnh này!", ephemeral=True)
        return

    user_data = await get_user(target.id)
    current_balance = user_data[1]

    actual_deduct = min(current_balance, amount)
    await add_points(target.id, -actual_deduct)

    updated_user = await get_user(target.id)
    new_balance = updated_user[1]

    embed = discord.Embed(
        title="⚖️ 📜 SẮC LỆNH TỊCH THU TÀI SẢN 📜 ⚖️",
        description=f"👤 **Đối tượng phạm tội:** <@{target.id}> (`{target.display_name}`)\n"
                    f"💸 **Số tiền bị tịch thu:**\n### 🔴 -{actual_deduct:,} VNĐ\n"
                    f"📌 **Lý do xử phạt:** *{lydo}*\n"
                    f"📉 **Số dư còn lại:**\n### ⚪ {new_balance:,} VNĐ",
        color=discord.Color.from_rgb(178, 34, 34)
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="setmoney", description="[ADMIN] Đặt lại chính xác số tiền cho tài khoản")
@app_commands.describe(target="Người chơi", amount="Số tiền mới")
async def setmoney_cmd(interaction: discord.Interaction, target: discord.User, amount: int):
    if interaction.user.id not in ADMIN_IDS:
        await interaction.response.send_message("❌ Bạn không có quyền Admin!", ephemeral=True)
        return

    await set_points(target.id, amount)
    embed = discord.Embed(
        title="⚙️ ĐẶT LẠI SỐ DƯ TÀI KHOẢN",
        description=f"👤 **Tài khoản:** <@{target.id}>\n"
                    f"💵 **Số dư mới:**\n### 🟢 {amount:,} VNĐ",
        color=discord.Color.blue()
    )
    await interaction.response.send_message(embed=embed)

# =========================================================
# GAME BACCARAT
# =========================================================

class BaccaratBetModal(discord.ui.Modal):
    def __init__(self, choice: str, choice_name: str):
        super().__init__(title=f"💎 ĐẶT CƯỚC BACCARAT: {choice_name}")
        self.choice = choice
        self.choice_name = choice_name

    sotien = discord.ui.TextInput(
        label="Nhập số tiền cược (Từ 3k đến 10,000,000 VNĐ)", 
        placeholder="Ví dụ: 3000", 
        min_length=1, 
        max_length=10
    )

    async def on_submit(self, interaction: discord.Interaction):
        try: 
            raw_val = self.sotien.value.replace(",", "").replace(".", "").strip()
            bet_amt = int(raw_val)
        except ValueError:
            await interaction.response.send_message("❌ Số tiền cược không hợp lệ! Vui lòng chỉ nhập số.", ephemeral=True)
            return

        if bet_amt < MIN_BET or bet_amt > MAX_BET:
            await interaction.response.send_message(f"❌ Mức cược không hợp lệ! Cược tối thiểu từ `{MIN_BET:,}` đến `{MAX_BET:,}` VNĐ.", ephemeral=True)
            return

        uid = interaction.user.id
        user = await get_user(uid)
        if user[1] < bet_amt:
            await interaction.response.send_message(f"❌ Số dư của bạn không đủ để đặt cược! (Số dư: `{user[1]:,} VNĐ`)", ephemeral=True)
            return

        cid = interaction.channel_id
        lobby = baccarat_queues.get(cid)
        if not lobby or lobby["status"] != "waiting":
            await interaction.response.send_message("⏳ Rất tiếc, bàn Baccarat này đã đóng cổng cược!", ephemeral=True)
            return

        for b in lobby["bets"]:
            if b["user_id"] == uid:
                await interaction.response.send_message("⚠ Bạn đã đặt cược ở bàn này rồi, không thể đặt thêm!", ephemeral=True)
                return

        await add_points(uid, -bet_amt)
        
        jackpot_contribution = int(bet_amt * 0.04)
        await add_jackpot(jackpot_contribution)

        lobby["bets"].append({
            "user_id": uid, "name": interaction.user.display_name,
            "choice": self.choice, "choice_name": self.choice_name, "bet": bet_amt
        })
        
        await interaction.response.send_message(
            f"✨ Đã đặt cược cửa **{self.choice_name}** thành công!\n"
            f"💵 **Số tiền cược:** 🪙 `{bet_amt:,} VNĐ` *(Đã trích {jackpot_contribution:,} VNĐ vào Hũ)*", 
            ephemeral=True
        )

class BaccaratView(discord.ui.View):
    def __init__(self, channel_id):
        super().__init__(timeout=None)
        self.channel_id = channel_id

    @discord.ui.button(label="💎 PLAYER (Ăn 1:1)", style=discord.ButtonStyle.primary, custom_id="bac_p")
    async def p_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BaccaratBetModal("player", "Player"))

    @discord.ui.button(label="🔥 BANKER (Ăn 1:1)", style=discord.ButtonStyle.danger, custom_id="bac_b")
    async def b_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BaccaratBetModal("banker", "Banker"))

    @discord.ui.button(label="👑 TIE / HÒA (Ăn 1:8)", style=discord.ButtonStyle.success, custom_id="bac_t")
    async def t_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BaccaratBetModal("tie", "Tie (Hòa)"))

@bot.tree.command(name="baccarat", description="Mở bàn Baccarat Cân Bằng - Giao diện Hoàng Gia")
async def baccarat_cmd(interaction: discord.Interaction):
    await interaction.response.defer()
    cid = interaction.channel_id
    if cid in baccarat_queues and baccarat_queues[cid]["status"] == "waiting":
        await interaction.followup.send("⏳ Đã có bàn Baccarat đang mở trong kênh này rồi!", ephemeral=True)
        return

    baccarat_queues[cid] = {"status": "waiting", "bets": []}
    lobby = baccarat_queues[cid]
    view = BaccaratView(cid)

    show_item = get_random_show_item()

    suits = ['♠', '♣', '♥', '♦']
    ranks = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
    all_cards = [f"{r}{s}" for r in ranks for s in suits]
    
    mult_cards = {}
    num_mult = random.choice([1, 2])
    selected_mult_cards = random.sample(all_cards, num_mult)
    for c in selected_mult_cards:
        mult_cards[c] = random.choice([2, 3, 5])

    mult_display = " ✦ ".join([f"⚡ `{card}` » **x{val}**" for card, val in mult_cards.items()])
    jp_pool = await get_jackpot()
    roadmap_str = " ".join(bacc_history[-10:]) if bacc_history else "🌸 *Chưa có cầu*"

    embed = discord.Embed(
        title="🌟 🎴 BÀN BACCARAT HOÀNG GIA - CÂN BẰNG VIP 🎴 🌟",
        description=f"✨ **LÁ BÀI SỐ NHÂN VÁN NÀY:**\n {mult_display}\n\n"
                    f"🎁 **QUÀ TẶNG VÁN NÀY:** {show_item['icon']} **{show_item['name']}** *(Cược từ **1.000 VNĐ** trở lên & Thắng là có cơ hội nhận quà VIP!)*\n\n"
                    f"📊 **BẢNG SOI CẦU (ROADMAP):**\n` {roadmap_str} `\n\n"
                    f"⏱ **Thời gian cược:** **` 25 giây `**\n"
                    f"🎁 **Hũ Jackpot Hiện Tại:** ` {jp_pool:,} VNĐ `\n",
        color=discord.Color.from_rgb(138, 43, 226)
    )
    embed.set_image(url=show_item["url"])

    msg = await interaction.followup.send(embed=embed, view=view)

    for rem in range(20, 0, -5):
        if cid not in baccarat_queues: return
        await asyncio.sleep(5)
        b_list = [f"🔸 **{b['name']}** ➔ ` {b['choice_name']} ` (💵 **{b['bet']:,} VNĐ**)" for b in lobby["bets"]]
        embed.description = (f"✨ **LÁ BÀI SỐ NHÂN VÁN NÀY:**\n {mult_display}\n\n"
                             f"🎁 **QUÀ TẶNG VÁN NÀY:** {show_item['icon']} **{show_item['name']}** *(Cược từ **1.000 VNĐ** trở lên & Thắng là có cơ hội nhận quà VIP!)*\n\n"
                             f"📊 **BẢNG SOI CẦU:** ` {' '.join(bacc_history[-10:]) if bacc_history else 'Chưa có'} `\n"
                             f"⏱ **Thời gian cược:** **` {rem} giây `**\n\n"
                             f"📋 **DANH SÁCH CƯỚC:**\n" + ("\n".join(b_list) if b_list else "*Chưa có ai đặt...*"))
        try: await msg.edit(embed=embed, view=view)
        except Exception: pass

    for rem in range(5, 0, -1):
        if cid not in baccarat_queues: return
        await asyncio.sleep(1)
        b_list = [f"🔸 **{b['name']}** ➔ ` {b['choice_name']} ` (💵 **{b['bet']:,} VNĐ**)" for b in lobby["bets"]]
        embed.description = (f"✨ **LÁ BÀI SỐ NHÂN:**\n {mult_display}\n\n"
                             f"🎁 **QUÀ TẶNG VÁN NÀY:** {show_item['icon']} **{show_item['name']}**\n\n"
                             f"⏱ **Sắp đóng bàn:** **` {rem} giây `**\n\n"
                             f"📋 **DANH SÁCH CƯỚC:**\n" + ("\n".join(b_list) if b_list else "*Chưa có ai đặt...*"))
        try: await msg.edit(embed=embed, view=view)
        except Exception: pass

    if not lobby["bets"]:
        lobby["status"] = "ended"
        embed.title = "❌ BÀN BACCARAT ĐÃ ĐÓNG"
        embed.description = "Hủy bàn do không có lượt cược nào."
        embed.set_image(url=None)
        try: await msg.edit(embed=embed, view=None)
        except Exception: pass
        if cid in baccarat_queues: del baccarat_queues[cid]
        return

    lobby["status"] = "dealing"
    deck = list(all_cards)
    random.shuffle(deck)

    p_hand = [deck.pop(), deck.pop()]
    b_hand = [deck.pop(), deck.pop()]

    def val(c):
        v = c[:-1]
        return 0 if v in ['J', 'Q', 'K', '10'] else (1 if v == 'A' else int(v))
    def score(h):
        return sum(val(c) for c in h) % 10

    p_sc = score(p_hand)
    b_sc = score(b_hand)

    deal_embed_p = discord.Embed(
        title="🌟 🎴 Đang chia bài Baccarat 🎴 🌟",
        description=f"🔵 **PLAYER:** ` {p_hand[0]}  {p_hand[1]} ` ➔ **{p_sc} ĐIỂM**\n"
                    f"🔴 **BANKER:** ` 🂠   🂠 ` ➔ *Đang úp bài...*\n\n"
                    f"⚡ *Đang lật bài bên Banker... Chờ chút!*",
        color=discord.Color.blue()
    )
    deal_embed_p.set_image(url=None)
    try: await msg.edit(embed=deal_embed_p, view=None)
    except Exception: pass
    
    await asyncio.sleep(2.5)

    if p_sc < 8 and b_sc < 8:
        if p_sc <= 5:
            p_hand.append(deck.pop())
            p_sc = score(p_hand)
            if b_sc <= 5:
                b_hand.append(deck.pop())
                b_sc = score(b_hand)
        elif b_sc <= 5:
            b_hand.append(deck.pop())
            b_sc = score(b_hand)

    winner = "player" if p_sc > b_sc else ("banker" if b_sc > p_sc else "tie")
    bacc_history.append("🔵 P" if winner == "player" else ("🔴 B" if winner == "banker" else "🟢 T"))

    winning_hand = p_hand if winner == "player" else (b_hand if winner == "banker" else (p_hand + b_hand))
    applied_multiplier = 1
    matched_mult_info = []

    for card in winning_hand:
        if card in mult_cards:
            applied_multiplier *= mult_cards[card]
            matched_mult_info.append(f"`{card}` (x{mult_cards[card]})")

    results_summary = []
    jp_pool = await get_jackpot()
    
    # Kiểm tra nổ hũ với tỉ lệ mới 0.99%
    hit_jackpot = check_jackpot_claim()

    for b in lobby["bets"]:
        uid_b = b["user_id"]
        bet_amt = b["bet"]
        choice = b["choice"]
        
        if choice == winner:
            if winner in ["player", "banker"]: 
                base_payout = bet_amt * 2  
            else: 
                base_payout = bet_amt * 9

            base_profit = base_payout - bet_amt
            final_profit = base_profit * applied_multiplier
            total_payout = bet_amt + final_profit

            await add_points(uid_b, total_payout)
            await update_result(uid_b, final_profit, win=True)

            got_real_item = check_real_item_claim(bet_amt)
            mult_text = f" 🔥 **[x{applied_multiplier}]**" if applied_multiplier > 1 else ""
            
            if got_real_item:
                item_text = f"\n  └ 🎁✨ **[QUÀ VIP BLOX FRUITS]** Chúc mừng bạn đã quay trúng: {show_item['icon']} **{show_item['name']}** cực khủng!"
            else:
                if bet_amt >= MIN_BET_FOR_ITEM:
                    item_text = f"\n  └ 💫 *(Đã đạt mức cược 1k+ nhưng rất tiếc chưa may mắn trúng quà ván này!)*"
                else:
                    item_text = f"\n  └ 💡 *(Cược dưới 1k nên không đủ điều kiện nhận quà vật phẩm)*"

            results_summary.append(
                f"✅ **{b['name']}** ➔ Thắng cửa **{b['choice_name']}** (+`{total_payout:,} VNĐ`){mult_text}{item_text}"
            )
        else:
            await update_result(uid_b, -bet_amt, win=False)
            results_summary.append(
                f"❌ **{b['name']}** ➔ Thua cửa **{b['choice_name']}** (-`{bet_amt:,} VNĐ`)"
            )

    jackpot_msg = ""
    if hit_jackpot and lobby["bets"]:
        lucky = random.choice(lobby["bets"])
        await add_points(lucky["user_id"], jp_pool)
        jackpot_msg = f"\n\n🎉👑 **NỔ HŨ JACKPOT HOÀNG GIA!** Chúc mừng đại gia **{lucky['name']}** đã hốt trọn **`{jp_pool:,} VNĐ`** từ hũ chung!"
        await reset_jackpot()  

    mult_status_str = f"⚡ **Hệ số nhân:** " + " ✦ ".join(matched_mult_info) + f" ➔ **x{applied_multiplier}**\n" if matched_mult_info else ""

    final_embed = discord.Embed(
        title="🏆 KẾT QUẢ BACCARAT HOÀNG GIA 🏆",
        description=f"🔵 **PLAYER:** ` {'  '.join(p_hand)} ` ➔ **{p_sc} ĐIỂM**\n"
                    f"🔴 **BANKER:** ` {'  '.join(b_hand)} ` ➔ **{b_sc} ĐIỂM**\n"
                    f"{mult_status_str}"
                    f"👑 **KẾT QUẢ CỬA THẮNG:** **` {winner.upper()} `**\n"
                    f"─────────────────────────────────────\n"
                    f"📊 **CHI TIẾT MỞ THƯỞNG:**\n" +
                    "\n".join(results_summary) + jackpot_msg,
        color=discord.Color.gold()
    )

    try: await msg.edit(embed=final_embed, view=None)
    except Exception: pass
    if cid in baccarat_queues: del baccarat_queues[cid]

# =========================================================
# GAME XÓC ĐĨA
# =========================================================

class XocDiaBetModal(discord.ui.Modal):
    def __init__(self, choice_type: str, choice_name: str):
        super().__init__(title=f"ĐẶT CƯỚC XÓC ĐĨA: {choice_name}")
        self.choice_type = choice_type
        self.choice_name = choice_name

    sotien = discord.ui.TextInput(
        label="Nhập số tiền cược (Từ 3k đến 10,000,000 VNĐ)", 
        placeholder="Ví dụ: 3000", 
        min_length=1, 
        max_length=10
    )

    async def on_submit(self, interaction: discord.Interaction):
        try: 
            raw_val = self.sotien.value.replace(",", "").replace(".", "").strip()
            bet_amt = int(raw_val)
        except ValueError:
            await interaction.response.send_message("❌ Số tiền cược không hợp lệ! Vui lòng chỉ nhập số.", ephemeral=True)
            return

        if bet_amt < MIN_BET or bet_amt > MAX_BET:
            await interaction.response.send_message(f"❌ Mức cược không hợp lệ! Cược tối thiểu từ `{MIN_BET:,}` đến `{MAX_BET:,}` VNĐ.", ephemeral=True)
            return

        uid = interaction.user.id
        user = await get_user(uid)
        if user[1] < bet_amt:
            await interaction.response.send_message(f"❌ Số dư của bạn không đủ để đặt cược! (Số dư: `{user[1]:,} VNĐ`)", ephemeral=True)
            return

        cid = interaction.channel_id
        lobby = xocdia_lobbies.get(cid)
        if not lobby or lobby["status"] != "waiting":
            await interaction.response.send_message("⏳ Rất tiếc, bàn Xóc Đĩa này đã đóng cổng cược!", ephemeral=True)
            return

        for b in lobby["bets"]:
            if b["user_id"] == uid:
                await interaction.response.send_message("⚠ Bạn đã đặt cược ở bàn này rồi, không thể đặt thêm!", ephemeral=True)
                return

        await add_points(uid, -bet_amt)
        
        jackpot_contribution = int(bet_amt * 0.04)
        await add_jackpot(jackpot_contribution)
        
        lobby["bets"].append({
            "user_id": uid, "name": interaction.user.display_name,
            "choice": self.choice_type, "choice_name": self.choice_name, "bet": bet_amt
        })
        
        await interaction.response.send_message(
            f"✅ Đã cược cửa **{self.choice_name}** thành công!\n"
            f"💵 **Số tiền cược:** 🎲 `{bet_amt:,} VNĐ` *(Đã trích {jackpot_contribution:,} VNĐ vào Hũ)*", 
            ephemeral=True
        )

class XocDiaView(discord.ui.View):
    def __init__(self, channel_id):
        super().__init__(timeout=None)
        self.channel_id = channel_id

    @discord.ui.button(label="🔴 CHẴN (Ăn 1:2)", style=discord.ButtonStyle.danger, custom_id="xd_chan")
    async def chan_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(XocDiaBetModal("chan", "Chẵn"))

    @discord.ui.button(label="⚪ LẺ (Ăn 1:2)", style=discord.ButtonStyle.secondary, custom_id="xd_le")
    async def le_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(XocDiaBetModal("le", "Lẻ"))

    @discord.ui.button(label="🔥 TÀI (3-4 Đỏ)", style=discord.ButtonStyle.primary, custom_id="xd_tai")
    async def tai_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(XocDiaBetModal("tai", "Tài"))

    @discord.ui.button(label="❄ XỈU (0-2 Đỏ)", style=discord.ButtonStyle.success, custom_id="xd_xiu")
    async def xiu_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(XocDiaBetModal("xiu", "Xỉu"))

@bot.tree.command(name="xocdia", description="Mở bàn Xóc Đĩa truyền thống chuẩn xác suất")
async def xocdia_cmd(interaction: discord.Interaction):
    await interaction.response.defer()
    cid = interaction.channel_id
    if cid in xocdia_lobbies and xocdia_lobbies[cid]["status"] == "waiting":
        await interaction.followup.send("⏳ Đã có bàn Xóc Đĩa đang mở trong kênh này rồi!", ephemeral=True)
        return

    xocdia_lobbies[cid] = {"status": "waiting", "bets": []}
    lobby = xocdia_lobbies[cid]
    view = XocDiaView(cid)

    show_item = get_random_show_item()
    jp_pool = await get_jackpot()

    embed = discord.Embed(
        title="🏮 🎲 BÀN XÓC ĐĨA HOÀNG GIA - MỞ BÁT 🎲 🏮",
        description=f"🎁 **QUÀ TẶNG VÁN NÀY:** {show_item['icon']} **{show_item['name']}** *(Cược từ **1.000 VNĐ** trở lên & Thắng là có cơ hội nhận quà VIP!)*\n\n"
                    f"⏱ **Mở thưởng sau:** **` 25 giây `**\n"
                    f"🎁 **Hũ Jackpot Hiện Tại:** ` {jp_pool:,} VNĐ `\n\n"
                    f"📋 **Danh sách người chơi:**\nTrống (Bấm các nút bên dưới để chọn cửa & cược)",
        color=discord.Color.dark_orange()
    )
    embed.set_image(url=show_item["url"])

    msg = await interaction.followup.send(embed=embed, view=view)

    for rem in range(20, 0, -5):
        if cid not in xocdia_lobbies: return
        await asyncio.sleep(5)
        b_list = [f"🔸 **{b['name']}** ➔ **{b['choice_name']}** (💵 **{b['bet']:,} VNĐ**)" for b in lobby["bets"]]
        embed.description = f"🎁 **QUÀ TẶNG VÁN NÀY:** {show_item['icon']} **{show_item['name']}** *(Cược từ **1.000 VNĐ** trở lên & Thắng là có cơ hội nhận quà VIP!)*\n\n⏱ **Mở thưởng sau:** **` {rem} giây `**\n\n📋 **Danh sách người chơi:**\n" + ("\n".join(b_list) if b_list else "Trống")
        try: await msg.edit(embed=embed, view=view)
        except Exception: pass

    for rem in range(5, 0, -1):
        if cid not in xocdia_lobbies: return
        await asyncio.sleep(1)
        b_list = [f"🔸 **{b['name']}** ➔ **{b['choice_name']}** (💵 **{b['bet']:,} VNĐ**)" for b in lobby["bets"]]
        embed.description = f"🎁 **QUÀ TẶNG VÁN NÀY:** {show_item['icon']} **{show_item['name']}**\n\n⏱ **Sắp mở bát:** **` {rem} giây `**\n\n📋 **Danh sách người chơi:**\n" + ("\n".join(b_list) if b_list else "Trống")
        try: await msg.edit(embed=embed, view=view)
        except Exception: pass

    if not lobby["bets"]:
        lobby["status"] = "ended"
        embed.title = "❌ BÀN XÓC ĐĨA ĐÃ ĐÓNG"
        embed.description = "Hủy bàn do không có người cược."
        embed.set_image(url=None)
        try: await msg.edit(embed=embed, view=None)
        except Exception: pass
        if cid in xocdia_lobbies: del xocdia_lobbies[cid]
        return

    lobby["status"] = "shaking"
    shake_embed = discord.Embed(
        title="🌀 Đang rung bát xóc đĩa...", 
        description="*Đang lắc xúc xắc chuẩn xác suất... Mời anh em chờ mở bát!*", 
        color=discord.Color.orange()
    )
    shake_embed.set_thumbnail(url=GIF_SHAKING_DICE)
    try: await msg.edit(embed=shake_embed, view=None)
    except Exception: pass
    await asyncio.sleep(2.5)

    coins = [random.choice([0, 1]) for _ in range(4)]
    red_count = sum(coins)
    coin_emojis = ["⚪" if c == 0 else "🔴" for c in coins]
    
    is_chan = (red_count % 2 == 0)
    is_tai = (red_count >= 3)

    results_summary = []
    jp_pool_current = await get_jackpot()
    
    # Kiểm tra nổ hũ với tỉ lệ mới 0.99%
    hit_jackpot = check_jackpot_claim()

    for b in lobby["bets"]:
        uid_b = b["user_id"]
        bet_amt = b["bet"]
        choice = b["choice"]
        
        won = False
        if choice == "chan" and is_chan: won = True
        elif choice == "le" and not is_chan: won = True
        elif choice == "tai" and is_tai: won = True
        elif choice == "xiu" and not is_tai: won = True

        if won:
            payout = bet_amt * 2
            profit = bet_amt
            await add_points(uid_b, payout)
            await update_result(uid_b, profit, win=True)
            
            got_real_item = check_real_item_claim(bet_amt)
            if got_real_item:
                item_text = f"\n  └ 🎁✨ **[QUÀ VIP BLOX FRUITS]** Chúc mừng bạn đã quay trúng: {show_item['icon']} **{show_item['name']}** cực khủng!"
            else:
                if bet_amt >= MIN_BET_FOR_ITEM:
                    item_text = f"\n  └ 💫 *(Đã đạt mức cược 1k+ nhưng rất tiếc chưa may mắn trúng quà ván này!)*"
                else:
                    item_text = f"\n  └ 💡 *(Cược dưới 1k nên không đủ điều kiện nhận quà vật phẩm)*"

            results_summary.append(
                f"✅ **{b['name']}** ➔ Thắng cửa **{b['choice_name']}** (+`{payout:,} VNĐ`){item_text}"
            )
        else:
            await update_result(uid_b, -bet_amt, win=False)
            results_summary.append(
                f"❌ **{b['name']}** ➔ Thua cửa **{b['choice_name']}** (-`{bet_amt:,} VNĐ`)"
            )

    jackpot_msg = ""
    if hit_jackpot and lobby["bets"]:
        lucky = random.choice(lobby["bets"])
        await add_points(lucky["user_id"], jp_pool_current)
        jackpot_msg = f"\n\n🎉👑 **NỔ HŨ JACKPOT XÓC ĐĨA!** Chúc mừng đại gia **{lucky['name']}** đã hốt trọn **`{jp_pool_current:,} VNĐ`** từ hũ chung!"
        await reset_jackpot()

    final_embed = discord.Embed(
        title="🏮 KẾT QUẢ MỞ BÁT XÓC ĐĨA 🏮",
        description=f"🪙 **QUÂN VỊ:** ` {' '.join(coin_emojis)} `\n"
                    f"🔥 **TỔNG SỐ ĐỎ:** **{red_count} đỏ**\n"
                    f"🏆 **KẾT QUẢ CỬA THẮNG:** **` {'CHẴN' if is_chan else 'LẺ'} `** | **` {'TÀI' if is_tai else 'XỈU'} `**\n"
                    f"─────────────────────────────────────\n"
                    f"📊 **CHI TIẾT MỞ THƯỞNG:**\n" +
                    "\n".join(results_summary) + jackpot_msg,
        color=discord.Color.gold()
    )

    try: await msg.edit(embed=final_embed, view=None)
    except Exception: pass
    if cid in xocdia_lobbies: del xocdia_lobbies[cid]

# =========================================================
# ON READY
# =========================================================

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Bot Casino đã sẵn sàng hoạt động: {bot.user}")

if __name__ == "__main__":
    if not TOKEN:
        raise ValueError("❌ Không tìm thấy DISCORD_TOKEN! Vui lòng kiểm tra lại token.")
    bot.run(TOKEN)
