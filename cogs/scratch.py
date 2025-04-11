# 外部ライブラリ
import discord
from discord import app_commands
from discord.ext import commands  # Bot Commands Framework
import scratchattach as scratch3  # scratchattach

# 自作モジュール
from modules.utils import send_error
from modules.decorators import ephemeral_check, restrict_check


##################################################

''' コマンド '''


class Scratch(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Cog読み込み時

    @commands.Cog.listener()
    async def on_ready(self):
        ##### DB読み込み＆チェック #####
        self.dbm = self.bot.get_cog("DatabaseManager")

        if not self.dbm:
            raise RuntimeError("scratch: Database cog is not ready")

        if not await self.dbm.check_db():
            raise RuntimeError("scratch: Database is not ready")

        #############################

        print("scratch: Ready")

    #########################

    # /scratchコマンドをグループ化
    group = app_commands.Group(name="scratch", description="Scratch関係のコマンド")

    # user

    @group.command(name="user", description="Scratchのユーザー情報を取得します")
    @app_commands.checks.cooldown(2, 10)
    @app_commands.describe(user="ユーザー名")
    @ephemeral_check
    @restrict_check
    async def scratch_user(self, ctx: discord.Interaction, user: app_commands.Range[str, 1, 25]):
        ephemeral = ctx.extras.get('ephemeral', False)

        await ctx.response.defer()

        if ctx.extras.get('restricted', False):
            await send_error(ctx, None, "このコマンドはサーバー管理者によって実行が制限されています。", None, is_followup=True)
            return

        try:
            user = scratch3.get_user(user)

        except Exception:
            await send_error(ctx, None, "ユーザーを取得できませんでした", None, is_followup=True)
            await self.dbm.log_command(ctx.user.id, "scratch user", user, ctx.guild.id if ctx.guild else None, result="Failed (Exception)")

        else:
            if user.scratchteam:
                embed = discord.Embed(
                    title="ユーザー名",
                    description=f"[{user}](https://scratch.mit.edu/users/{user}) [Scratchチーム]",
                    color=discord.Colour.green())
            else:
                embed = discord.Embed(
                    title="ユーザー名",
                    description=f"[{user}](https://scratch.mit.edu/users/{user})",
                    color=discord.Colour.green())

            try:
                embed.set_thumbnail(url=user.icon_url)

            except Exception:
                pass

            jd = user.join_date

            embed.add_field(name="ユーザーID",
                            value=user.id, inline=True)
            embed.add_field(name="国",
                            value=user.country, inline=True)
            embed.add_field(name="通知数",
                            value=user.message_count(), inline=True)
            embed.add_field(name="フォロー数",
                            value=user.following_count(), inline=True)
            embed.add_field(name="フォロワー数",
                            value=user.follower_count(), inline=True)
            embed.add_field(name="共有したプロジェクト数",
                            value=user.project_count(), inline=True)
            embed.add_field(name="お気に入りプロジェクト数",
                            value=user.favorites_count(), inline=True)
            # embed.add_field(name="フォローしているスタジオ数",
            # value=user.studio_following_count(), inline=True)
            embed.add_field(name="キュレーションしたスタジオ数",
                            value=user.studio_count(), inline=True)
            embed.add_field(name="私について",
                            value=user.about_me, inline=False)
            embed.add_field(name="私が取り組んでいること",
                            value=user.wiwo, inline=False)
            embed.set_footer(text=f"アカウント作成日時: {jd[:4]}/{jd[5:7]}/{jd[8:10]} {jd[11:19]}")

            await ctx.followup.send(embed=embed, ephemeral=ephemeral)
            await self.dbm.log_command(ctx.user.id, "scratch user", None, ctx.guild.id if ctx.guild else None, result="Success")

    # ff

    @group.command(name="ff", description="Scratchの特定ユーザーがフォロー・フォロワーか確認します")
    @app_commands.checks.cooldown(2, 10)
    @app_commands.describe(mode="モード選択")
    @app_commands.describe(target="対象ユーザー名")
    @app_commands.describe(user="フォロー・フォロワーであるか確認するユーザー名")
    @app_commands.choices(mode=[
        discord.app_commands.Choice(name="following", value="following"),
        discord.app_commands.Choice(name="follower", value="follower"),])
    @ephemeral_check
    @restrict_check
    async def scratch_ff(self, ctx: discord.Interaction, mode: str, target: app_commands.Range[str, 1, 25], user: app_commands.Range[str, 1, 25]):
        ephemeral = ctx.extras.get('ephemeral', False)

        await ctx.response.defer()

        if ctx.extras.get('restricted', False):
            await send_error(ctx, None, "このコマンドはサーバー管理者によって実行が制限されています。", None, is_followup=True)
            return

        try:
            us = scratch3.get_user(target)

        except Exception:
            await send_error(ctx, None, "ユーザーを取得できませんでした", None, is_followup=True)
            await self.dbm.log_command(ctx.user.id, "scratch ff", [mode, target, user], ctx.guild.id if ctx.guild else None, result="Failed (Exception)")

        else:
            if mode == "following":
                try:
                    data = us.is_following(user)

                except Exception:
                    await send_error(ctx, None, "ユーザーを取得できませんでした", None, is_followup=True)
                    await self.dbm.log_command(ctx.user.id, "scratch ff", [mode, target, user], ctx.guild.id if ctx.guild else None, result="Failed (Exception)")


                else:
                    if data:
                        status = "しています"

                    else:
                        status = "していません"

                    embed = discord.Embed(title="フォロー判定",
                                          description=f"`@{target}`は`@{user}`を**フォロー{status}**",
                                          color=discord.Colour.green())
                    await ctx.followup.send(embed=embed, ephemeral=ephemeral)
                    await self.dbm.log_command(ctx.user.id, "scratch ff", [mode, target, user], ctx.guild.id if ctx.guild else None, result="Success")

            if mode == "follower":
                try:
                    data = us.is_followed_by(user)

                except Exception:
                    await send_error(ctx, None, "ユーザーを取得できませんでした", None, is_followup=True)
                    await self.dbm.log_command(ctx.user.id, "scratch ff", [mode, target, user], ctx.guild.id if ctx.guild else None, result="Failed (Exception)")


                else:
                    if data:
                        status = "されています"

                    else:
                        status = "されていません"

                    embed = discord.Embed(title="フォロワー判定",
                                          description=f"`@{target}`は`@{user}`に**フォロー{status}**",
                                          color=discord.Colour.green())
                    await ctx.followup.send(embed=embed, ephemeral=ephemeral)
                    await self.dbm.log_command(ctx.user.id, "scratch ff", [mode, target, user], ctx.guild.id if ctx.guild else None, result="Success")

    #########################

    ''' クールダウン '''

    @scratch_user.error
    async def user_on_command_error(self, ctx: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.checks.CommandOnCooldown):
            retry_after_int = int(error.retry_after)
            retry_minute = retry_after_int // 60
            retry_second = retry_after_int % 60
            embed = discord.Embed(title="エラー",
                                  description=f"クールダウン中です。\nあと**{retry_minute}分{retry_second}秒**お待ちください。",
                                  color=0xff0000)
            embed.set_footer(text=f"Report ID: {ctx.id}")
            return await ctx.response.send_message(embed=embed, ephemeral=True)

    @scratch_ff.error
    async def ff_on_command_error(self, ctx: discord.Interaction, error: app_commands.AppCommandError):
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
    await bot.add_cog(Scratch(bot))
