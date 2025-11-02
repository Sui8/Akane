# 外部ライブラリ
import discord
from discord import app_commands
from discord.ext import commands  # Bot Commands Framework

# 自作モジュール
from modules.utils import send_error
from modules.decorators import ephemeral_check, restrict_check


##################################################

''' コマンド '''


class Guild(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Cog読み込み時
    @commands.Cog.listener()
    async def on_ready(self):
        # ---- DB読み込み＆チェック ----
        self.dbm = self.bot.get_cog("DatabaseManager")

        if not self.dbm:
            raise RuntimeError("guild: Database cog is not ready")

        if not await self.dbm.check_db():
            raise RuntimeError("guild: Database is not ready")

        #############################

        print("guild: ready")

    #########################

    # server

    @app_commands.command(name="server", description="サーバー情報を取得します")
    @app_commands.checks.cooldown(2, 15)
    @ephemeral_check
    @restrict_check
    async def server(self, ctx: discord.Interaction):
        await ctx.response.defer()
        ephemeral = ctx.extras.get('ephemeral', False)

        if ctx.extras.get('restricted', False):
            await send_error(ctx, None, "このコマンドはサーバー管理者によって実行が制限されています。", None, is_followup=True)
            return

        if not ctx.guild:
            await send_error(ctx, None, "このコマンドはサーバー以外で使用できません", None, is_followup=True)
            await self.dbm.log_command(ctx.user.id, "server", None, ctx.guild.id if ctx.guild else None, result="Failed (Mistake)")
            return

        try:
            embed = discord.Embed(title="サーバー情報",
                                  description="",
                                  color=discord.Colour.dark_blue())
            icon = ctx.guild.icon.replace(static_format='png')
            created_at = ctx.guild.created_at.timestamp()
            others = f"ロール数: {len(ctx.guild.roles)}\n" \
                + f"絵文字数: {len(ctx.guild.emojis)}\n" \
                + f"スタンプ数: {len(ctx.guild.stickers)}\n" \
                + f"サーバーブースト: {ctx.guild.premium_subscription_count} (レベル{ctx.guild.premium_tier})\n" \
                + f"認証レベル: {ctx.guild.verification_level}\n" \
                + f"AFK: {ctx.guild.afk_timeout}秒"

            embed.add_field(name="サーバーID", value=ctx.guild.id, inline=True)
            embed.add_field(name="作成日時", value=f"<t:{int(created_at)}:f>", inline=True)
            embed.add_field(name="所有者", value=ctx.guild.owner.mention, inline=True)
            embed.add_field(name="人数", value=f"{ctx.guild.member_count}人", inline=True)  # Memberインテント必須
            embed.add_field(name="チャンネル数", value=f"テキスト: {len(ctx.guild.text_channels)}\nボイス: {len(ctx.guild.voice_channels)}", inline=True)
            embed.add_field(name="その他", value=others, inline=True)

        except Exception:
            await send_error(ctx, None, "サーバー情報を取得できません。\nBotの権限を確認して下さい。", None, is_followup=True)
            await self.dbm.log_command(ctx.user.id, "server", None, ctx.guild.id if ctx.guild else None, result="Failed (Exception)")
            return

        else:

            embed.set_thumbnail(url=icon)
            await ctx.followup.send(embed=embed, ephemeral=ephemeral)
            await self.dbm.log_command(ctx.user.id, "server", None, ctx.guild.id if ctx.guild else None, result="Success")

    #########################

    ''' クールダウン '''

    @server.error
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
    await bot.add_cog(Guild(bot))
