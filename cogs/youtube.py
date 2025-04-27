# 外部ライブラリ
import discord
from discord import app_commands
from discord.ext import commands  # Bot Commands Framework
from yt_dlp import YoutubeDL  # yt-dlp

# 自作モジュール
from modules.utils import send_error
from modules.decorators import ephemeral_check, restrict_check


##################################################

''' コマンド '''


class YouTube(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    # Cog読み込み時
    @commands.Cog.listener()
    async def on_ready(self):
        ##### DB読み込み＆チェック #####
        self.dbm = self.bot.get_cog("DatabaseManager")

        if not self.dbm:
            raise RuntimeError("youtube: Database cog is not ready")

        if not await self.dbm.check_db():
            raise RuntimeError("youtube: Database is not ready")

        #############################

        print("youtube: ready")

    #########################

    # yt-dlp

    @app_commands.command(name="ytdl", description="YouTube動画のダウンロードリンクを取得します")
    @app_commands.checks.cooldown(1, 30)
    @app_commands.describe(url="動画URLを指定")
    @app_commands.describe(option="オプションを指定")
    @app_commands.choices(option=[
        discord.app_commands.Choice(name='videoonly', value=1),
        discord.app_commands.Choice(name='soundonly', value=2),
    ])
    @ephemeral_check
    @restrict_check
    async def ytdl(self, ctx: discord.Interaction,
                   url: str, option: discord.app_commands.Choice[int] = None):
        ephemeral = ctx.extras.get('ephemeral', False)

        await ctx.response.defer()

        if ctx.extras.get('restricted', False):
            await send_error(ctx, None, "このコマンドはサーバー管理者によって実行が制限されています。", None, is_followup=True)
            return

        if url.startswith("https://www.youtube.com/playlist"):
            await send_error(ctx, None, "プレイリストのダウンロードリンクは取得できません", None, is_followup=True)
            await self.dbm.log_command(ctx.user.id, "ytdl", [url, option], ctx.guild.id if ctx.guild else None, result="Failed (Mistake)")
            return

        url = url.split('&')[0]

        try:
            if option.value == 1:
                youtube_dl_opts = {'format': 'bestvideo', 'max-downloads': '1', "cookies": "data/cookie.txt"}
                opt = "動画のみ"

            elif option.value == 2:
                youtube_dl_opts = {'format': 'bestaudio[ext=m4a]', 'max-downloads': '1', "cookies": "data/cookie.txt"}
                opt = "音声のみ"

        except Exception:
            youtube_dl_opts = {'format': 'best', 'max-downloads': '1', "cookiefile": "data/cookie.txt",
                'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                }}
            opt = "なし"

        try:
            with YoutubeDL(youtube_dl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=False)
                video_url = info_dict.get("url", None)
                video_title = info_dict.get('title', None)

        except Exception as e:
            await send_error(ctx, None, "エラーが発生しました。\nしばらく時間をおいてからお試しください。解決しない場合は、サポートサーバーまでお問い合わせください。", None, is_followup=True)
            await self.dbm.log_command(ctx.user.id, "ytdl", [url, option], ctx.guild.id if ctx.guild else None, result=f"Failed ({e})")

        else:
            embed = discord.Embed(
                title="YouTube動画ダウンロードリンク",
                description=f"`{video_title}`のダウンロードリンクを取得しました。URLは約6時間有効です。 "
                            f"(オプション: {opt})\n\n[クリックしてダウンロード]({video_url})\n"
                            f"※YouTubeによる自動生成動画はダウンロードに失敗する場合があります\n"
                            f":warning: 著作権に違反してアップロードされた動画をダウンロードすることは違法です",
                color=discord.Colour.red())
            await ctx.followup.send(embed=embed, ephemeral=ephemeral)
            await self.dbm.log_command(ctx.user.id, "ytdl", [url, option], ctx.guild.id if ctx.guild else None, result="Success")

    #########################

    ''' クールダウン '''

    @ytdl.error
    async def on_command_error(self, ctx: discord.Interaction, error: app_commands.AppCommandError):
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
    await bot.add_cog(YouTube(bot))
