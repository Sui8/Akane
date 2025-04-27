# 組み込みライブラリ
import datetime

# 外部ライブラリ
import discord
from discord import app_commands
from discord.ext import commands  # Bot Commands Framework

# 自作モジュール
from modules.utils import send_error
from modules.decorators import ephemeral_check, restrict_check


##################################################

''' コマンド '''


class Delete(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Cog読み込み時
    @commands.Cog.listener()
    async def on_ready(self):
        ##### DB読み込み＆チェック #####
        self.dbm = self.bot.get_cog("DatabaseManager")

        if not self.dbm:
            raise RuntimeError("delete: Database cog is not ready")

        if not await self.dbm.check_db():
            raise RuntimeError("delete: Database is not ready")

        #############################

        print("delete: Ready")

    #########################

    # delete
    @app_commands.command(name="delete", description="5秒以上前のメッセージを削除します")
    @app_commands.checks.cooldown(1, 60)
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(num="削除件数を指定")
    @ephemeral_check
    @restrict_check
    async def delete(self, ctx: discord.Interaction, num: app_commands.Range[int, 1, 100]):
        await ctx.response.defer()
        ephemeral = ctx.extras.get('ephemeral', False)

        if ctx.extras.get('restricted', False):
            await send_error(ctx, None, "このコマンドはサーバー管理者によって実行が制限されています。", None, is_followup=True)
            return

        if not ctx.guild:
            await send_error(ctx, None, "このコマンドはDMで使用できません", None, is_followup=False)
            await self.dbm.log_command(ctx.user.id, "delete", num, ctx.guild.id if ctx.guild else None, result="Failed (Mistake)")
            return

        channel = ctx.channel
        now = datetime.datetime.now() - datetime.timedelta(seconds=5)

        try:
            deleted = await channel.purge(before=now, limit=int(num), reason=f'@{ctx.user.name}によるコマンド実行')

        except Exception:
            await send_error(ctx, None, "Botに正しく権限が付与されているか確認してください", self.bot.SUPPORT_SERVER, is_followup=True)
            await self.dbm.log_command(ctx.user.id, "delete", num, ctx.guild.id if ctx.guild else None, result="Failed (Exception)")
            return

        else:
            embed = discord.Embed(title=":white_check_mark: 成功",
                                    description=f"`{len(deleted)}`件のメッセージを削除しました",
                                    color=discord.Colour.green())
            await ctx.followup.send(embed=embed, ephemeral=ephemeral)
            await self.dbm.log_command(ctx.user.id, "delete", num, ctx.guild.id if ctx.guild else None, result="Success")

    #########################

    ''' クールダウン '''

    @delete.error
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
    await bot.add_cog(Delete(bot))
