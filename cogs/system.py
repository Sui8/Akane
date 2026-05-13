# 組み込みライブラリ
import os
import datetime
from zoneinfo import ZoneInfo  # JST設定用
import platform  # カーネル取得用

# 外部ライブラリ
import discord
from discord import app_commands
from discord.ext import commands  # Bot Commands Framework
import psutil  # psutil
from dotenv import load_dotenv  # python-dotenv
import distro  # distro (Linuxのみ)
import simplejson as json  # simplejson

# 自作モジュール
from modules.pagination import Pagination
from modules.utils import send_error
from modules.decorators import ephemeral_check, restrict_check


load_dotenv()  # .env読み込み

##################################################

''' 定数群 '''

VERSION = os.getenv("VERSION")

##################################################

''' コマンド '''


class System(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Cog読み込み時
    @commands.Cog.listener()
    async def on_ready(self):
        # ---- DB読み込み＆チェック ----
        self.dbm = self.bot.get_cog("DatabaseManager")

        if not self.dbm:
            raise RuntimeError("system: Database cog is not ready")

        if not await self.dbm.check_db():
            raise RuntimeError("system: Database is not ready")

        #############################

        print("system: ready")

    #########################

    # help

    @app_commands.command(name="help", description="使用できるコマンドの一覧を表示します")
    @app_commands.describe(command="指定したコマンドの説明を表示します")
    @ephemeral_check
    @restrict_check
    async def help(self, ctx: discord.Interaction, command: str = None):
        await ctx.response.defer()

        # ephemeral = ctx.extras.get('ephemeral', False)

        if ctx.extras.get('restricted', False):
            await send_error(ctx, None, "このコマンドはサーバー管理者によって実行が制限されています。", None, is_followup=True)
            return

        with open("data/commands.json", encoding="UTF-8") as f:
            commands = json.load(f)

        # 長さを整形したコマンド一覧
        commands_just = [cmd.ljust(12) for cmd in commands]

        commands_formatted = [f"`/{commands_just[i]}` {commands[cmd]['info']}" for (i, cmd) in zip(range(len(commands)), commands)]
        L = 10

        # 引数あり: コマンド説明
        if command:
            if commands[command]:
                category = commands[command]["category"]
                help_usage = commands[command]["usage"]
                help_info = commands[command]["info"]
                embed = discord.Embed(title=f"{category}: **{command}**", description="")
                embed.add_field(name="使い方",
                                value=f"\n```/{help_usage}```", inline=False)
                embed.add_field(name="説明",
                                value=f"```{help_info}```", inline=False)
                embed.set_footer(text="<> : 必要引数 | [] : オプション引数")
                await ctx.followup.send(embed=embed, ephemeral=True)
                await self.dbm.log_command(ctx.user.id, "help", command, ctx.guild.id if ctx.guild else None, result="Success")

            else:
                await send_error(ctx, None, "指定されたコマンドは存在しません", None, is_followup=True)
                await self.dbm.log_command(ctx.user.id, "help", command, ctx.guild.id if ctx.guild else None, result="Failed (Mistake)")

        else:
            async def get_page(page: int):
                embed = discord.Embed(
                    title=f"Akane (v{VERSION}) コマンドリスト",
                    description="❓コマンドの詳細説明: /help <コマンド名>\n\n**コマンド**\n",
                    color=discord.Colour.red())
                offset = (page - 1) * L

                for command in commands_formatted[offset:offset+L]:
                    embed.description += f"{command}\n"

                n = Pagination.compute_total_pages(len(commands_formatted), L)
                embed.set_footer(text=f"ページ {page} / {n}")
                return embed, n

            await Pagination(ctx, get_page).navegate()
            await self.dbm.log_command(ctx.user.id, "help", None, ctx.guild.id if ctx.guild else None, result="Success")

    # ping

    @app_commands.command(name="ping", description="BotのPingを確認します")
    @ephemeral_check
    @restrict_check
    async def ping(self, ctx: discord.Interaction):
        await ctx.response.defer()

        ephemeral = ctx.extras.get('ephemeral', False)

        if ctx.extras.get('restricted', False):
            await send_error(ctx, None, "このコマンドはサーバー管理者によって実行が制限されています。", None, is_followup=True)
            return

        embed = discord.Embed(title="Pong!",
                              description=f"`{round(self.bot.latency * 1000, 2)}ms`",
                              color=0xc8ff00)
        await ctx.followup.send(embed=embed, ephemeral=ephemeral)
        await self.dbm.log_command(ctx.user.id, "ping", None, ctx.guild.id if ctx.guild else None, result="Success")

    # stats

    @app_commands.command(name="stats", description="Akaneのステータスを表示します")
    @app_commands.checks.cooldown(2, 30)
    @ephemeral_check
    async def stats(self, ctx: discord.Interaction):
        await ctx.response.defer()

        ephemeral = ctx.extras.get('ephemeral', False)

        async with self.dbm.pool.acquire() as conn:
            COMMAND_COUNT = await conn.fetchval(
                """
                SELECT value
                FROM bot_data
                WHERE name = $1
                """,
                "command_count"
                )

        embed = discord.Embed(title="ステータス",
                              description="",
                              color=0xc8ff00)
        embed.add_field(name=":robot: 統計", value=f"サーバー数: **{len(self.bot.guilds):,}**\nユーザー数: **調整中**")
        embed.add_field(name=":pencil: Botの情報",
                        value=(
                            f"開発者: **{self.bot.OWNER_NAME}**\n"
                            f"バージョン: **{self.bot.VERSION}**\n"
                            f"コマンド数: **{int(COMMAND_COUNT):,}**"))
        embed.add_field(name=":desktop: サーバー情報",
                        value=(
                            f"CPU使用率: **{psutil.cpu_percent(interval=1)}% "
                            f"({round(psutil.cpu_freq().current / 1000, 2)}GHz)**\n"
                            f"メモリ使用率: **{psutil.virtual_memory().percent}% "
                            f"({round(psutil.virtual_memory().used / 1024 ** 3, 1)}/"
                            f"{round(psutil.virtual_memory().total / 1024 ** 3, 1)}GB)**\n"
                            f"起動日時: **{datetime.datetime.fromtimestamp(psutil.boot_time()).strftime('%Y/%m/%d %H:%M:%S')} (UTC+9)**\n"
                            f"discord.py: **v{discord.__version__}**\n"
                            f"OS: **{distro.name(pretty=True)}**\n"
                            f"カーネル: **Linux {platform.release()}**"))
        embed.set_footer(text=f"データ取得時刻: {datetime.datetime.now(ZoneInfo('Asia/Tokyo')).strftime('%Y/%m/%d %H:%M:%S')}")
        await ctx.followup.send(embed=embed, ephemeral=ephemeral)
        await self.dbm.log_command(ctx.user.id, "stats", None, ctx.guild.id if ctx.guild else None, result="Success")

    # invite

    @app_commands.command(name="invite", description="Botの招待リンクを表示します")
    @ephemeral_check
    @restrict_check
    async def invite(self, ctx: discord.Interaction):
        await ctx.response.defer()

        ephemeral = ctx.extras.get('ephemeral', False)

        if ctx.extras.get('restricted', False):
            await send_error(ctx, None, "このコマンドはサーバー管理者によって実行が制限されています。", None, is_followup=True)
            return

        button = discord.ui.Button(label="招待する", style=discord.ButtonStyle.link,
                                   url="https://discord.com/oauth2/authorize?client_id=777557090562474044")
        embed = discord.Embed(title="招待リンク",
                              description="下のボタンからAkaneをサーバーに招待できます\n※サーバー管理権限が必要です",
                              color=0xdda0dd)
        view = discord.ui.View()
        view.add_item(button)
        await ctx.followup.send(embed=embed, view=view, ephemeral=ephemeral)
        await self.dbm.log_command(ctx.user.id, "invite", None, ctx.guild.id if ctx.guild else None, result="Success")

    # support

    @app_commands.command(name="support", description="サポートサーバーの招待リンクを表示します")
    @ephemeral_check
    @restrict_check
    async def support(self, ctx: discord.Interaction):
        await ctx.response.defer()

        ephemeral = ctx.extras.get('ephemeral', False)

        if ctx.extras.get('restricted', False):
            await send_error(ctx, None, "このコマンドはサーバー管理者によって実行が制限されています。", None, is_followup=True)
            return

        await ctx.followup.send("__**サポートサーバー**__\nお問い合わせ・バグ報告・アップデート情報はこちらで配信しています。\n"
                                f"以下のリンクより参加できます。\n{self.bot.SUPPORT_SERVER}",
                                ephemeral=ephemeral)
        await self.dbm.log_command(ctx.user.id, "support", None, ctx.guild.id if ctx.guild else None, result="Success")

    #########################

    ''' クールダウン '''

    @stats.error
    async def stats_on_command_error(self, ctx: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.checks.CommandOnCooldown):
            retry_after_int = int(error.retry_after)
            retry_minute = retry_after_int // 60
            retry_second = retry_after_int % 60
            embed = discord.Embed(title="エラー",
                                  description=f"クールダウン中です。\nあと**{retry_minute}分{retry_second}秒**お待ちください。",
                                  color=0xff0000)
            embed.set_footer(text=f"Report ID: {ctx.id}")
            return await ctx.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(System(bot))
