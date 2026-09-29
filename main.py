import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Button, View

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'======================================')
    print(f'Bot {bot.user} đã ONLINE!')
    # Tự động đồng bộ các lệnh Slash Command (dấu /) với Discord
    try:
        synced = await bot.tree.sync()
        print(f'Đã đồng bộ {len(synced)} lệnh Slash (/) thành công!')
    except Exception as e:
        print(f'Lỗi đồng bộ lệnh Slash: {e}')
    print(f'======================================')

# --- 1. LỆNH /delta ---
@bot.tree.command(name="delta", description="Gửi link tải Delta Executor iOS")
async def delta(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📱 Delta Executor iOS Download",
        description="Dưới đây là các đường link tải Delta Executor cho iOS:",
        color=discord.Color.purple()
    )
    embed.add_field(
        name="🔗 Link 1 (Chính thức)", 
        value="[Bấm vào đây để tải](https://deltaexploits.gg/delta-executor-ios)", 
        inline=False
    )
    embed.add_field(
        name="🔗 Link 2 (Dự phòng)", 
        value="[Bấm vào đây để tải](https://deltaexploits.dev/delta-executor-ios)", 
        inline=False
    )
    embed.set_footer(text="Lưu ý: Bạn nên mở bằng Safari trên iOS để cài đặt!")

    # Tạo nút bấm
    btn1 = Button(label="Tải từ Delta official (.gg)", url="https://deltaexploits.gg/delta-executor-ios")
    btn2 = Button(label="Tải từ Delta backup (.dev)", url="https://deltaexploits.dev/delta-executor-ios")
    
    view = View()
    view.add_item(btn1)
    view.add_item(btn2)

    await interaction.response.send_message(embed=embed, view=view)

# --- 2. LỆNH /ping ---
@bot.tree.command(name="ping", description="Kiểm tra độ trễ của bot")
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f'🏓 Pong! Độ trễ hiện tại là `{latency}ms`.')

# --- 3. LỆNH /chao ---
@bot.tree.command(name="chao", description="Gửi lời chào")
async def chao(interaction: discord.Interaction):
    await interaction.response.send_message(f'👋 Xin chào {interaction.user.mention}!')

# Token Bot của bạn
TOKEN = os.getenv('DISCORD_TOKEN')

bot.run(TOKEN)