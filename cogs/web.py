# 組み込みライブラリ
import os
import base64

# 外部ライブラリ
import discord
from discord import app_commands
from discord.ext import commands  # Bot Commands Framework
import requests  # requests
from dotenv import load_dotenv  # python-dotenv
import simplejson as json  # simplejson

# 自作モジュール
from modules.utils import send_error
from modules.decorators import ephemeral_check, restrict_check


load_dotenv()  # .env読み込み

##################################################

''' 定数群 '''

UR7_USERNAME = os.getenv("UR7_USERNAME")  # ur7.cc
UR7_PASSWORD = os.getenv("UR7_PASSWORD")  # ur7.cc
SHORTIO_KEY = os.getenv("SHORTIO_KEY")  # short.io

##################################################

''' 関数群 '''


# 5000choen
class GosenChoen(discord.ui.Modal, title='「5000兆円欲しい！」ジェネレーター'):
    line1 = discord.ui.TextInput(
        label='上の行',
        placeholder='5000兆円',
        required=True,
        max_length=50,
    )

    line2 = discord.ui.TextInput(
        label='下の行',
        placeholder='欲しい！',
        required=True,
        max_length=50,
    )

    async def on_submit(self, ctx: discord.Interaction):
        url = f"https://gsapi.cbrx.io/image?top={self.line1.value}&bottom={self.line2.value}&type=png"

        try:
            embed = discord.Embed()
            embed.set_image(url=url)
            embed.set_footer(text="Powered by 5000choyen-api")
            await ctx.response.send_message(embed=embed, ephemeral=False)

        except Exception:
            await send_error(ctx, None, "作成に失敗しました。\nしばらく時間をおいてからお試しください。", None, is_followup=True)
            await self.dbm.log_command(ctx.user.id, "5000", None, ctx.guild.id if ctx.guild else None, result="Failed (Exception)")

    async def on_error(
            self, ctx: discord.Interaction, error: Exception) -> None:
        await send_error(ctx, None, "作成に失敗しました。\nしばらく時間をおいてからお試しください。", None, is_followup=True)
        await self.dbm.log_command(ctx.user.id, "5000", None, ctx.guild.id if ctx.guild else None, result=f"Failed ({error})")


##################################################

''' コマンド '''


class Web(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    # Cog読み込み時
    @commands.Cog.listener()
    async def on_ready(self):
        ##### DB読み込み＆チェック #####
        self.dbm = self.bot.get_cog("DatabaseManager")

        if not self.dbm:
            raise RuntimeError("web: Database cog is not ready")

        if not await self.dbm.check_db():
            raise RuntimeError("web: Database is not ready")

        #############################

        print("web: ready")

    #########################

    # short

    @app_commands.command(name="short", description="URLを短縮します")
    @app_commands.checks.cooldown(1, 10)
    @app_commands.describe(url="短縮するURLを貼り付け")
    @app_commands.describe(host="使用するドメイン")
    @app_commands.choices(host=[
        discord.app_commands.Choice(name="is.gd", value="isgd"),
        discord.app_commands.Choice(name="x3.f5.si", value="shortio"),
        discord.app_commands.Choice(name="ur7.cc", value="ur7")])
    @ephemeral_check
    @restrict_check
    async def short(self, ctx: discord.Interaction, url: str, host: str = None):
        ephemeral = ctx.extras.get('ephemeral', False)

        await ctx.response.defer()

        if ctx.extras.get('restricted', False):
            await send_error(ctx, None, "このコマンドはサーバー管理者によって実行が制限されています。", None, is_followup=True)
            return

        # short.io
        if host == "shortio":
            res = requests.post('https://api.short.io/links', json={
                'domain': 'x3.f5.si',
                'originalURL': url,
            }, headers = {
                'authorization': SHORTIO_KEY,
                'content-type': 'application/json'
            }, )

            res.raise_for_status()

            try:
                data = res.json()
                short_link = data["shortURL"]

            except Exception:
                await send_error(ctx, None, "エラーが発生しました。\nしばらく時間をおいてからお試しください。", None, is_followup=True)
                await self.dbm.log_command(ctx.user.id, "short", [url, host], ctx.guild.id if ctx.guild else None, result="Failed (Exception)")
                return

        # ur7.cc
        elif host == "ur7":
            res = requests.post(
            f"https://ur7.cc/yourls-api.php?username={UR7_USERNAME}&password={UR7_PASSWORD}&action=shorturl&format=json&url={url}"
            )

            try:
                data = res.json()
                short_link = json.dumps(res["shorturl"])

            except Exception:
                await send_error(ctx, None, "エラーが発生しました。\nしばらく時間をおいてからお試しください。", None, is_followup=True)
                await self.dbm.log_command(ctx.user.id, "short", [url, host], ctx.guild.id if ctx.guild else None, result="Failed (Exception)")
                return

        # is.gd
        else:
            api_url = "https://is.gd/create.php"
            params = {
                "format": "json",
                "url": url
            }

            try:
                res = requests.get(api_url, params=params)
                data = res.json()
                short_link = data.get("shorturl")

            except Exception:
                await send_error(ctx, None, "エラーが発生しました。\nしばらく時間をおいてからお試しください。", None, is_followup=True)
                await self.dbm.log_command(ctx.user.id, "short", [url, host], ctx.guild.id if ctx.guild else None, result="Failed (Exception)")
                return

        await ctx.followup.send(short_link, ephemeral=True)
        await self.dbm.log_command(ctx.user.id, "short", [url, host], ctx.guild.id if ctx.guild else None, result="Success")

    # 5000choen

    @app_commands.command(name="5000", description="「5000兆円欲しい！」ジェネレーター")
    @app_commands.checks.cooldown(2, 15)
    @restrict_check
    async def gosen_choen(self, ctx: discord.Interaction):
        if ctx.extras.get('restricted', False):
            await send_error(ctx, None, "このコマンドはサーバー管理者によって実行が制限されています。", None, is_followup=False)
            return

        await ctx.response.send_modal(GosenChoen())

    # mcskin

    @app_commands.command(name="mcskin", description="Minecraft (Java)ユーザーのスキンを取得します")
    @app_commands.checks.cooldown(1, 10)
    @app_commands.describe(user="ユーザー名またはUUID")
    @ephemeral_check
    @restrict_check
    async def mcskin(self, ctx: discord.Interaction, user: str):
        await ctx.response.defer()

        ephemeral = ctx.extras.get('ephemeral', False)

        if ctx.extras.get('restricted', False):
            await send_error(ctx, None, "このコマンドはサーバー管理者によって実行が制限されています。", None, is_followup=True)
            return

        def is_uuid(value):
            """ UUIDかどうかを判定する関数 """
            return len(value) == 32 and all(c in '0123456789abcdef' for c in value.lower())

        # UUIDのハイフンがあれば除去
        if is_uuid(user):
            uuid = user.replace("-", "")

        else:
            # ユーザ名からUUID変換
            url = f"https://api.mojang.com/users/profiles/minecraft/{user}"
            headers = {"content-type": "application/json"}
            
            try:
                response = requests.get(url, headers=headers)

                if response.status_code == 200:
                    user_data = response.json()
                    uuid = user_data["id"]

            except Exception:
                await send_error(ctx, None, "エラーが発生しました。\nしばらく時間をおいてからお試しください。", None, is_followup=True)
                await self.dbm.log_command(ctx.user.id, "mcskin", user, ctx.guild.id if ctx.guild else None, result="Failed (Exception)")
                return

        # UUIDからユーザー情報取得
        url = f"https://sessionserver.mojang.com/session/minecraft/profile/{uuid}"
        headers = {"content-type": "application/json"}

        try:
            response = requests.get(url, headers=headers)

            if response.status_code == 200:
                user_data = response.json()
                name = user_data["name"]
                properties = user_data["properties"]
                textures = list(filter(lambda x: x["name"]=="textures", properties))[0]["value"]
                
                # スキン画像のURL取得
                textures = json.loads(base64.b64decode(textures))
                skin_url = textures["textures"]["SKIN"]["url"]

                # embed生成
                embed = discord.Embed(title="Minecraft スキン",
                                      description=f"**ユーザー名**: `{name}`\n**UUID**: `{uuid}`",
                                      color=0xa84300)
                embed.set_image(url=skin_url)
                button = discord.ui.Button(label="NameMC", style=discord.ButtonStyle.link,
                                           url=f"https://ja.namemc.com/profile/{uuid}")
                view = discord.ui.View()
                view.add_item(button)

                await ctx.followup.send(embed=embed, view=view, ephemeral=ephemeral)
                await self.dbm.log_command(ctx.user.id, "mcskin", user, ctx.guild.id if ctx.guild else None, result="Success")

        except Exception:
            await send_error(ctx, None, "エラーが発生しました。\nしばらく時間をおいてからお試しください。", None, is_followup=True)
            await self.dbm.log_command(ctx.user.id, "mcskin", user, ctx.guild.id if ctx.guild else None, result="Failed (Exception)")
            return

    ##################################################

    ''' クールダウン '''

    @short.error
    async def short_on_command_error(self, ctx: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.checks.CommandOnCooldown):
            retry_after_int = int(error.retry_after)
            retry_minute = retry_after_int // 60
            retry_second = retry_after_int % 60
            embed = discord.Embed(title="エラー",
                                  description=f"クールダウン中です。\nあと**{retry_minute}分{retry_second}秒**お待ちください。",
                                  color=0xff0000)
            embed.set_footer(text=f"Report ID: {ctx.id}")
            return await ctx.response.send_message(embed=embed, ephemeral=True)

    @gosen_choen.error
    async def gosen_choen_on_command_error(self, ctx: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.checks.CommandOnCooldown):
            retry_after_int = int(error.retry_after)
            retry_minute = retry_after_int // 60
            retry_second = retry_after_int % 60
            embed = discord.Embed(title="エラー",
                                  description=f"クールダウン中です。\nあと**{retry_minute}分{retry_second}秒**お待ちください。",
                                  color=0xff0000)
            embed.set_footer(text=f"Report ID: {ctx.id}")
            return await ctx.response.send_message(embed=embed, ephemeral=True)

    @mcskin.error
    async def mcskin_on_command_error(self, ctx: discord.Interaction, error: app_commands.AppCommandError):
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
    await bot.add_cog(Web(bot))
