import os
import threading
from flask import Flask
import discord
from discord.ext import commands

# 1. Tạo web server nhỏ để Render kiểm tra port thành công
app = Flask('')

@app.route('/')
def home():
    return "Bot Discord đang hoạt động!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = threading.Thread(target=run_web)
    t.start()

# 2. Chạy web server ngầm
keep_alive()

# 3. Code Bot Discord
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'Bot đã kết nối: {bot.user}')

TOKEN = os.getenv('DISCORD_TOKEN')
if TOKEN:
    bot.run(TOKEN)
