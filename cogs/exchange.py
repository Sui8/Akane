# 組み込みライブラリ
import os
import base64
import aiohttp

# 外部ライブラリ
import discord
from discord import app_commands
from discord.ext import commands, tasks  # Bot Commands Framework
import requests  # requests
import simplejson as json  # simplejson

# 自作モジュール
from modules.utils import send_error
from modules.decorators import ephemeral_check, restrict_check


##################################################

''' 定数群 '''

URL = "https://api.frankfurter.dev/v1/latest"

##################################################

''' コマンド '''


class Exchange(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.cache = {}
        self.update_cache.start()

    def cog_unload(self):
        self.update_cache.cancel()

    # 12時間ごとにデータを更新
    @tasks.loop(hours=12)
    async def update_cache(self):
        async with aiohttp.ClientSession() as session:
            async with session.get(URL) as resp:
                if resp.status == 200:
                    data = await resp.json()

                    # 換算レートをcacheに保存
                    self.cache = data.get("rates", {})

                    # ベース通貨(EUR)
                    self.cache["EUR"] = 1.0

                    # print("exchange: Currency cache updated.")

    # Cog読み込み時
    @commands.Cog.listener()
    async def on_ready(self):
        # ---- DB読み込み＆チェック ----
        self.dbm = self.bot.get_cog("DatabaseManager")

        if not self.dbm:
            raise RuntimeError("exchange: Database cog is not ready")

        if not await self.dbm.check_db():
            raise RuntimeError("exchange: Database is not ready")

        #############################

        print("exchange: ready")

    #########################

    # 通貨コードの予測変換用
    async def currency_autocomplete(self, ctx: discord.Interaction, current: str):
        currencies = list(self.cache.keys())
        return [
            app_commands.Choice(name=c, value=c)
            for c in currencies if current.upper() in c
        ][:25] # Discordの制限で最大25個

    # fx

    @app_commands.command(name="fx", description="通貨換算 (デフォルト: USD→JPY)")
    @app_commands.checks.cooldown(20, 60)
    @app_commands.autocomplete(from_cur=currency_autocomplete, to_cur=currency_autocomplete)
    @app_commands.describe(amount="金額")
    @app_commands.describe(from_cur="換算元")
    @app_commands.describe(to_cur="換算先")
    async def fx(self, ctx: discord.Interaction, amount: float = 1.0, from_cur: str = "USD", to_cur: str = "JPY"):

        await ctx.response.defer()
        
        # キャッシュなし
        if not self.cache:
            await send_error(ctx, None, "通貨換算データを取得できません。\nしばらく時間をおいてからお試しください。", None, is_followup=True)
            await self.dbm.log_command(ctx.user.id, "fx", [amount, from_cur, to_cur], ctx.guild.id if ctx.guild else None, result="Failed (Exception)")
            return

        from_cur, to_cur = from_cur.upper(), to_cur.upper()
        
        if from_cur not in self.cache or to_cur not in self.cache:
            await send_error(ctx, None, "未対応の通貨です", None, is_followup=True)
            await self.dbm.log_command(ctx.user.id, "fx", [amount, from_cur, to_cur], ctx.guild.id if ctx.guild else None, result="Failed")
            return

        # EURを介して計算 (金額 / 元通貨のEURレート) * 先通貨のEURレート
        base_amount = amount / self.cache[from_cur]
        converted = base_amount * self.cache[to_cur]
        rate = self.cache[to_cur] / self.cache[from_cur]

        embed = discord.Embed(title="通貨換算", color=discord.Color.blue())
        embed.add_field(name="Result", value=f"**{amount} {from_cur}** → **{converted:.2f} {to_cur}**", inline=False)
        embed.set_footer(text=f"Rate: 1 {from_cur} = {rate:.4f} {to_cur}")
        
        await ctx.followup.send(embed, ephemeral=False)
        await self.dbm.log_command(ctx.user.id, "fx", [amount, from_cur, to_cur], ctx.guild.id if ctx.guild else None, result="Success")


    ##################################################

    ''' クールダウン '''

    @fx.error
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
    await bot.add_cog(Exchange(bot))
