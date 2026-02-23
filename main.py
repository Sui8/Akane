# 組み込みライブラリ
import asyncio
import datetime
import os
from itertools import cycle
import random
import time

# 外部ライブラリ
import discord
from discord.ext import commands  # Bot Commands Framework
from discord.ext import tasks
from dotenv import load_dotenv  # python-dotenv
# import simplejson as json  # simplejson

# 自作ライブラリ
from server import keep_alive

load_dotenv()  # .env読み込み
keep_alive()  # Webサーバー起動

intents = discord.Intents.default()
intents.message_content = True  # (特権) メッセージインテント
intents.members = True  # (特権) メンバーインテント

bot = commands.Bot(command_prefix=os.getenv("PREFIX"), intents=intents, help_command=None)

##################################################

''' 定数群 '''

TOKEN = os.getenv("TOKEN")  # Token
TEST_TOKEN = os.getenv("TEST_TOKEN")  # テスト用BotのToken

STARTUP_LOG = int(os.getenv("STARTUP_LOG"))
bot.ERROR_LOG = int(os.getenv("ERROR_LOG"))  # エラーログを投げるチャンネル
DEV_GUILD = int(os.getenv("DEV_GUILD"))
bot.PREFIX = os.getenv("PREFIX")  # Default Prefix
bot.VERSION = os.getenv("VERSION")
bot.OWNER_NAME = os.getenv("OWNER_NAME")
bot.SUPPORT_SERVER = os.getenv("SUPPORT_SERVER")

# 読み込むCogのリスト
EXTENSIONS = [
    'cogs.database_manager',
    'cogs.system',
    'cogs.fun',
    'cogs.shikanoko',
    'cogs.scratch',
    'cogs.user',
    'cogs.youtube',
    'cogs.guild',
    'cogs.delete',
    'cogs.nijigen',
    'cogs.useful',
    'cogs.web',
    'cogs.akane-talks',
    'cogs.akane-ai',
    'cogs.money',
    'cogs.settings',
    'cogs.jppost',
    'cogs.gamble',
    'cogs.ranking',
    'cogs.pokepoke',
    'cogs.banword',
    'cogs.exchange'
]

##################################################

# 起動通知


@bot.event
async def on_ready():
    global STATUS_LIST

    print("[Akane] ログインしました")
    start_time = time.time()  # 起動タイムを計測
    bot_guilds = len(bot.guilds)
    # bot_members = bot.users
    bot_members = 0

    # database_manager呼び出し
    dbm = bot.get_cog("DatabaseManager")

    if dbm:
        # DBが生きていれば処理
        if await dbm.check_db():
            # 設定更新
            async with dbm.pool.acquire() as conn:
                async with conn.transaction():
                    try:
                        await conn.execute(
                            """
                            UPDATE bot_data
                            SET value = $1
                            WHERE name = 'guilds'
                            """,
                            str(bot_guilds)
                            )

                        await conn.execute(
                            """
                            UPDATE bot_data
                            SET value = $1
                            WHERE name = 'members'
                            """,
                            str(bot_members)
                            )

                    except Exception as e:
                        print(f"[Error] main: {e}")

            # 設定読み出し
            async with dbm.pool.acquire() as conn:
                try:
                    bot.COMMANDS_COUNT = await conn.fetchval("""
                        SELECT value FROM bot_data WHERE name = 'commands_count'
                    """)

                except Exception as e:
                    print(f"[Error] main: {e}")

        else:
            print("[Error] main: Database isn't available")

    else:
        print("[Error] main: Can't load 'database_manager'")

    # ステータスリストをcycleで生成
    STATUS_LIST = cycle(["❓/help", f"{bot_guilds:,} Servers", f"Version {bot.VERSION}"])
    activity = discord.CustomActivity(name="✅ 起動完了")
    await bot.change_presence(activity=activity)

    # 起動メッセージを専用サーバーに送信（チャンネルが存在しない場合、スルー）
    try:
        ready_log = await bot.fetch_channel(STARTUP_LOG)
        embed = discord.Embed(title="Akane 起動完了",
                              description=f"**{bot.user}** (ID: {bot.user.id}) が起動しました。"
                              f"\n```サーバー数: {bot_guilds:,}\n"
                              f"ユーザー数: {bot_members:,}\n"
                              f"起動時間: {round(time.time() - start_time, 2)}秒```",
                              timestamp=datetime.datetime.now())
        embed.set_footer(text=f"Akane - Ver{bot.VERSION}")
        await ready_log.send(embed=embed)

    except Exception:
        pass

    # 5秒後からステータス変更とサーバー数更新開始
    await asyncio.sleep(5)
    change_activity.start()
    update_guilds_count.start()


# Activity自動変更
@tasks.loop(seconds=10)
async def change_activity():
    activity = discord.CustomActivity(name=next(STATUS_LIST))
    await bot.change_presence(activity=activity)


# サーバー数自動更新 (更新するとcycleは先頭に戻る)
@tasks.loop(minutes=60)
async def update_guilds_count():
    global STATUS_LIST

    bot_guilds = len(bot.guilds)
    STATUS_LIST = cycle(["❓/help", f"{bot_guilds:,} Servers", f"Version {bot.VERSION}"])


##################################################

''' 管理者用コマンド '''


# help
@bot.command(name="help")
@commands.is_owner()
async def devhelp(ctx):
    desc = "```Akane 管理者用コマンドリスト```\n" \
         + "**管理コマンド**\n`help`, `sync`, `devsync`, `reload`, `stop`, `give`, `givexp` `resetwork`, `resetlogin`"
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
        # DBにこの情報を出力しておく
        dbm = bot.get_cog("DatabaseManager")

        if dbm:
            # DBが生きていれば処理
            if await dbm.check_db():
                # 設定更新
                async with dbm.pool.acquire() as conn:
                    async with conn.transaction():
                        try:
                            await conn.execute(
                                """
                                UPDATE bot_data
                                SET value = $1
                                WHERE name = 'commands_count'
                                """,
                                str(len(synced))
                                )

                        except Exception as e:
                            print(f"Error: {e}")

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


# reload
@bot.command(name="reload")
@commands.is_owner()
async def reload(ctx):
    try:
        for extention in EXTENSIONS:
            await bot.load_extension(extention)

    except Exception as e:
        embed = discord.Embed(title=":x: エラー",
                              description="コマンドのSyncに失敗しました",
                              color=0xff0000)
        embed.add_field(name="エラー内容", value=e)
        await ctx.reply(embed=embed, mention_author=False)

    else:
        embed = discord.Embed(title=":white_check_mark: 成功",
                              description=f"{len(EXTENSIONS)}個のCogをリロードしました",
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


##################################################


# 全てのインタラクションを取得
@bot.event
async def on_interaction(ctx: discord.Interaction):
    try:
        if ctx.data['component_type'] == 2:
            if "hit" in ctx.data["custom_id"] or "stand" in ctx.data["custom_id"]:
                # blackjack
                gamble_cog = bot.get_cog('Gamble')

                if gamble_cog:
                    await gamble_cog.blackjack_button_click(ctx)

            else:
                # janken
                await janken_button_click(ctx)

        # elif inter.data['component_type'] == 3:
        #     await on_dropdown(inter)

    except KeyError:
        pass


# janken Buttonの処理
async def janken_button_click(ctx: discord.Interaction):
    custom_id = ctx.data["custom_id"]

    if custom_id == "j_g":
        result = random.choice(range(1, 3))

        if result == 1:
            await ctx.response.send_message(f"ぽん:v: {ctx.user.mention}\n君の勝ちやで～")

        elif result == 2:
            await ctx.response.send_message(f"ぽん✊ {ctx.user.mention}\nあいこやな。")

        else:
            await ctx.response.send_message(f"ぽん✋ {ctx.user.mention}\n私の勝ちやな。また挑戦してや。")

    if custom_id == "j_c":
        result = random.choice(range(1, 3))

        if result == 1:
            await ctx.response.send_message(f"ぽん✋ {ctx.user.mention}\n君の勝ちやで～")

        elif result == 2:
            await ctx.response.send_message(f"ぽん:v: {ctx.user.mention}\nあいこやな。")

        else:
            await ctx.response.send_message(f"ぽん✊ {ctx.user.mention}\n私の勝ちやな。また挑戦してや。")

    if custom_id == "j_p":
        result = random.choice(range(1, 3))

        if result == 1:
            await ctx.response.send_message(f"ぽん✊ {ctx.user.mention}\n君の勝ちやで～")

        elif result == 2:
            await ctx.response.send_message(f"ぽん✋ {ctx.user.mention}\nあいこやな。")

        else:
            await ctx.response.send_message(f"ぽん:v: {ctx.user.mention}\n私の勝ちやな。また挑戦してや。")


##################################################

# Cog読み込み
async def load_extension():
    for cog in EXTENSIONS:
        await bot.load_extension(cog)


# 起動
async def main():
    async with bot:
        await load_extension()
        print("[Akane] Cogを全て読み込みました")
        await bot.start(TOKEN)


# エラー処理
@bot.event
async def on_command_error(ctx: commands.Context, error):
    # Botが起こしたエラーの場合
    if ctx.author.bot:
        print(error)

    if isinstance(error, commands.errors.CheckFailure):  # スラッシュコマンドでのみ動作するように制約
        await ctx.send(":x: 権限がありません", ephemeral=True)  # 権限を持たずにコマンドを実行した際に警告する

asyncio.run(main())
