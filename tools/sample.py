# 組み込みライブラリ
import asyncio
import datetime
import os
from itertools import cycle
import random

# 外部ライブラリ
import discord
from discord.ext import commands  # Bot Commands Framework
from discord.ext import tasks
from dotenv import load_dotenv  # python-dotenv
import simplejson as json  # simplejson


load_dotenv()  # .env読み込み

##################################################

''' 定数群 '''

TOKEN = os.getenv("TOKEN")  # Token

STARTUP_LOG = int(os.getenv("STARTUP_LOG"))
DEV_GUILD = int(os.getenv("DEV_GUILD"))
PREFIX = os.getenv("PREFIX")  # Default Prefix
VERSION = os.getenv("VERSION")

##################################################

bot = commands.Bot(command_prefix=PREFIX, intents=discord.Intents.all())


# 起動通知
@bot.event
async def on_ready():
    print("[Akane] ログインしました")

    activity = discord.CustomActivity(name="メンテナンス中 | Under maintenance")
    await bot.change_presence(status=discord.Status.idle, activity=activity)

##################################################

''' 管理者用コマンド '''


# devhelp
@bot.command(name="devhelp")
@commands.is_owner()
async def devhelp(ctx):
    desc = "```Akane 管理者用コマンドリスト```\n**管理コマンド**\n`sync`, `devsync`"
    embed = discord.Embed(title="📖コマンドリスト", description=desc)
    await ctx.reply(embed=embed, mention_author=False)


# sync
@bot.command(name="sync")
@commands.is_owner()
async def sync(ctx):
    try:
        synced = await bot.tree.sync()

    except Exception as e:
        embed = discord.Embed(title=":x: エラー",
                              description="コマンドのSyncに失敗しました",
                              color=0xff0000)
        embed.add_field(name="エラー内容", value=e)
        await ctx.reply(embed=embed, mention_author=False)

    else:
        embed = discord.Embed(title=":white_check_mark: 成功",
                              description=f"{len(synced)}コマンドをSyncしました",
                              color=discord.Colour.green())
        await ctx.reply(embed=embed, mention_author=False)


# devsync
@bot.command(name="devsync")
@commands.is_owner()
async def devsync(ctx):
    try:
        synced = await bot.tree.sync(guild=discord.Object(DEV_GUILD))

    except Exception as e:
        embed = discord.Embed(title=":x: エラー",
                              description="コマンドのSyncに失敗しました",
                              color=0xff0000)
        embed.add_field(name="エラー内容", value=e)
        await ctx.reply(embed=embed, mention_author=False)

    else:
        embed = discord.Embed(title=":white_check_mark: 成功",
                              description=f"{len(synced)}コマンドをSyncしました",
                              color=discord.Colour.green())
        await ctx.reply(embed=embed, mention_author=False)


# stop
@bot.command(name="stop")
@commands.is_owner()
async def stop(ctx):
    print("[Akane] Shutdown is requested by owner")
    embed = discord.Embed(title=":white_check_mark: 成功",
                          description="Botを停止しています",
                          color=discord.Colour.green())
    await ctx.reply(embed=embed, mention_author=False)
    await bot.close()


@bot.command(name="give_money")
@commands.is_owner()
async def give_money(ctx, userid: int, val: int):
    await ctx.reply(f"{userid} to {val}", mention_author=False)

##################################################

# 起動
async def main():
    async with bot:
        await bot.start(TOKEN)


# エラー処理
@bot.event
async def on_command_error(ctx: commands.Context, error):
    # Botが起こしたエラーの場合
    if ctx.author.bot:
        print(error)


asyncio.run(main())
