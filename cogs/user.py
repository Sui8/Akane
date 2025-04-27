# 組み込みライブラリ
import re
import datetime
import random
from collections.abc import Iterable

# 外部ライブラリ
import discord
from discord import app_commands
from discord.ext import commands  # Bot Commands Framework

# 自作モジュール
from modules.utils import send_error
from modules.decorators import ephemeral_check, restrict_check


##################################################

ALL_BADGES = [["staff", "<:Discord_Staff:1310243625980133416>"],
["partner", "<:Discord_Partner:1310244200222162984>"],
["hypesquad", "<:HypeSquad_Events:1310244618478293002>"],
["bug_hunter", "<:Bug_Hunter:1310244948821413928>"],
["bug_hunter_level_2", "<:Gold_Bug_Hunter:1310246180210343936>"],
["hypesquad_balance", "<:HypeSquad_Balance:1310241795418099792>"],
["hypesquad_bravery", "<:HypeSquad_Bravery:1310242994057908305>"],
["hypesquad_brilliance", "<:HypeSquad_Brilliance:1310243053612830771>"],
["early_supporter", "<:Early_Supporter:1310245165977567232>"],
["verified_bot_developer", "<:Early_Verified_Bot_Developer:1310246728120664205>"],
["discord_certified_moderator", "<:Moderator_Programs_Alumni:1310254854886785137>"],
["active_developer", "<:Active_Developer:1310255185276309677>"]
]

##################################################

''' コマンド '''


class User(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    # Cog読み込み時
    @commands.Cog.listener()
    async def on_ready(self):
        ##### DB読み込み＆チェック #####
        self.dbm = self.bot.get_cog("DatabaseManager")

        if not self.dbm:
            raise RuntimeError("user: Database cog is not ready")

        if not await self.dbm.check_db():
            raise RuntimeError("user: Database is not ready")

        #############################

        print("user: ready")

    #########################

    # user

    @app_commands.command(name="user", description="ユーザー情報を取得するで")
    @app_commands.checks.cooldown(2, 15)
    @app_commands.describe(user="ユーザーをメンションまたはユーザーIDで指定")
    @ephemeral_check
    @restrict_check
    async def user(self, ctx: discord.Interaction, user: str):
        await ctx.response.defer()

        user_str = user

        ephemeral = ctx.extras.get('ephemeral', False)

        if ctx.extras.get('restricted', False):
            await send_error(ctx, None, "このコマンドはサーバー管理者によって実行が制限されています。", None, is_followup=True)
            return

        # メンションからID抽出
        target = re.sub("\\D", "", str(user))

        # ユーザーIDからユーザーを取得
        try:
            user = await self.bot.fetch_user(target)

        # できなかったらエラー出す
        except Exception:
            await send_error(ctx, None, "ユーザーを取得できませんでした", None, is_followup=True)
            await self.dbm.log_command(ctx.user.id, "user", user_str, ctx.guild.id if ctx.guild else None, result="Failed (Exception)")

        else:
            # アカウント名切り分け
            if not user.bot:
                embed = discord.Embed(title=f"@{user.name} の情報",
                                      description="",
                                      color=discord.Colour.green())

                # スパマーフラグ確認
                if user.public_flags.spammer:
                    account_type = "ユーザー (:warning: スパマー)"

                else:
                    account_type = "ユーザー"

            else:
                embed = discord.Embed(title=f"{user.name}#{user.discriminator} の情報",
                                      description="",
                                      color=discord.Colour.green())

                # BOT種別確認
                if user.public_flags.verified_bot:
                    account_type = "認証済みBOT"

                else:
                    account_type = "BOT"

            # 公式か確認
            if user.public_flags.system:
                account_type = "Discord公式"

            # アイコンとバナー
            try:
                embed.set_thumbnail(url=user.avatar_url)

            except Exception:
                pass

            try:
                embed.set_image(url=user.banner.url)

            except Exception:
                pass

            created_at = int(user.created_at.timestamp()) # アカウント作成日時

            # バッジの所持状況確認
            try:
                owned_badges = [badge[1] for badge in ALL_BADGES if getattr(user.public_flags, badge[0], False)]

                if len(owned_badges) == 0:
                    owned_badges = ["なし"]

            except Exception:
                owned_badges = ["(取得失敗)"]

            
            embed.add_field(name="ユーザーID", value=target, inline=True)
            embed.add_field(name="ニックネーム", value=user.display_name, inline=True)
            embed.add_field(name="メンション", value=user.mention, inline=True)
            embed.add_field(name="バッジ", value=f"{''.join(owned_badges)}", inline=True)
            embed.add_field(name="アカウント種別", value=account_type, inline=True)
            embed.add_field(name="アカウント作成日時", value=f"<t:{created_at}:f> (<t:{created_at}:R>)", inline=True)
            #embed.set_footer(text=f"アカウント作成日時: <t:{created_at}:f> (<t:{created_at}:R>)")

            if hasattr(user.avatar, 'key'):
                embed.set_thumbnail(url=user.avatar.url)

            await ctx.followup.send(embed=embed, ephemeral=ephemeral)
            await self.dbm.log_command(ctx.user.id, "user", user_str, ctx.guild.id if ctx.guild else None, result="Success")

    # unban

    @app_commands.command(name="unban", description="ユーザーのBAN解除をします")
    @app_commands.checks.cooldown(1, 5)
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(user="メンションまたはユーザーID")
    @app_commands.describe(reason="理由")
    @ephemeral_check
    @restrict_check
    async def unban(self, ctx: discord.Interaction, user: str, reason: app_commands.Range[str, 1, 400] = None):
        await ctx.response.defer()

        ephemeral = ctx.extras.get('ephemeral', False)

        if ctx.extras.get('restricted', False):
            await send_error(ctx, None, "このコマンドはサーバー管理者によって実行が制限されています。", None, is_followup=True)
            return

        if not ctx.guild:
            await send_error(ctx, None, "このコマンドはサーバー以外で使用できません", None, is_followup=True)
            await self.dbm.log_command(ctx.user.id, "unban", [user, reason], ctx.guild.id if ctx.guild else None, result="Failed (Mistake)")
            return

        # メンションからID抽出
        target = re.sub("\\D", "", str(user))

        try:
            user = await self.bot.fetch_user(target)

        # できなかったらエラー出す
        except Exception:
            await send_error(ctx, None, "ユーザーを取得できませんでした", None, is_followup=True)
            await self.dbm.log_command(ctx.user.id, "unban", [user, reason], ctx.guild.id if ctx.guild else None, result="Failed (Exception)")

        else:
            try:
                await ctx.guild.unban(user)

            except Exception:
                await send_error(ctx, None, "ユーザー名/IDが正しく、Botに適切な権限があることを確認してください。", None, is_followup=True)
                await self.dbm.log_command(ctx.user.id, "unban", [user, reason], ctx.guild.id if ctx.guild else None, result="Failed (Exception)")

            else:
                embed = discord.Embed(title=":white_check_mark: 成功",
                                      description="BAN解除が完了しました。\n",
                                      timestamp=datetime.datetime.now(),
                                      color=discord.Colour.green())
                try:
                    embed.set_thumbnail(url=user.avatar.url)
                    embed.set_footer(text=f"実行者: `@{ctx.user.name}`",
                                     icon_url=ctx.user.avatar.url)

                except Exception:
                    pass

                # 理由
                if reason:
                    reason += f" (コマンド実行者: @{ctx.user.name})"

                else:
                    reason = f"@{ctx.user.name} によってBAN解除が実行されました"

                embed.add_field(name="BAN解除されたユーザー",
                                value=f"`@{user.name}` [ID:{target}]",
                                inline=True)
                embed.add_field(name="理由",
                                value=f"{reason}",
                                inline=True)

                await ctx.followup.send(embed=embed, ephemeral=ephemeral)
                await self.dbm.log_command(ctx.user.id, "unban", [user, reason], ctx.guild.id if ctx.guild else None, result="Success")

    # massban

    @app_commands.command(name="massban", description="ユーザーを一括BANします")
    @app_commands.checks.cooldown(1, 10)
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(users="スペース/カンマ区切りでメンションまたはユーザーID")
    @app_commands.describe(delete_days="直近のメッセージを削除する日数")
    @app_commands.describe(reason="理由")
    @ephemeral_check
    @restrict_check
    async def massban(self, ctx: discord.Interaction, users: str, delete_days: app_commands.Range[str, 0, 7] = 0, reason: app_commands.Range[str, 1, 400] = None):
        ephemeral = ctx.extras.get('ephemeral', False)

        await ctx.response.defer()

        if ctx.extras.get('restricted', False):
            await send_error(ctx, None, "このコマンドはサーバー管理者によって実行が制限されています。", None, is_followup=True)
            return

        if not ctx.guild:
            await send_error(ctx, None, "このコマンドはサーバー以外で使用できません", None, is_followup=True)
            await self.dbm.log_command(ctx.user.id, "massban", [users, delete_days, reason], ctx.guild.id if ctx.guild else None, result="Failed (Mistake)")
            return

        # 正規表現でID抽出
        mention_pattern = re.compile(r"<@!?(\d+)>")

        target_list = []

        try:
            for target in users.split():
                # メンションがあればIDに変換
                match = mention_pattern.match(target)

                if match:
                    target_list.append(int(match.group(1)))  # メンションからID部分を取り出す

                else:
                    target_list.append(int(target))  # メンションでない場合はそのままIDとして扱う

        except Exception:
            await send_error(ctx, None, "ユーザー名またはIDの形式が正しくありません", None, is_followup=True)
            await self.dbm.log_command(ctx.user.id, "massban", [users, delete_days, reason], ctx.guild.id if ctx.guild else None, result="Failed (Mistake)")
            return

        # 不正な値を処理
        if len(target_list) > 200:
            await send_error(ctx, None, "一度にBANできる上限は200人までです", None, is_followup=True)
            await self.dbm.log_command(ctx.user.id, "massban", [users, delete_days, reason], ctx.guild.id if ctx.guild else None, result="Failed (Mistake)")
            return
        
        if len(target_list) == 0:
            await send_error(ctx, None, "ユーザー名またはIDの形式が正しくありません", None, is_followup=True)
            await self.dbm.log_command(ctx.user.id, "massban", [users, delete_days, reason], ctx.guild.id if ctx.guild else None, result="Failed (Mistake)")
            return
        
        # 理由
        if reason:
            reason += f" (コマンド実行者: @{ctx.user.name})"

        else:
            reason = f"@{ctx.user.name} によって一括BANが実行されました"

        # 削除日数
        delete_days *= 86400

        # メイン処理
        try:
            target_list_snowflake: Iterable[discord.Object] = (discord.Object(id=user_id) for user_id in target_list)
            result = await ctx.guild.bulk_ban(target_list_snowflake, reason=reason, delete_message_seconds=delete_days)

        except Exception as e:
            await send_error(ctx, None, "ユーザー名/IDが正しく、Botに適切な権限があることを確認してください。", None, is_followup=True)
            await self.dbm.log_command(ctx.user.id, "massban", [users, delete_days, reason], ctx.guild.id if ctx.guild else None, result=f"Failed ({e})")

        else:
            successful_count = len(result.banned)
            failed_count = len(result.failed)
            failed_bans = " ".join([f"<@!{user.id}>" for user in result.failed][:15])

            if len(failed_bans) == 0:
                failed_bans = "なし"

            embed = discord.Embed(title=":white_check_mark: 実行完了",
                                    description="一括BANが完了しました。\n",
                                    timestamp=datetime.datetime.now(),
                                    color=discord.Colour.green())
            try:
                embed.set_footer(text=f"実行者: @{ctx.user.name}",
                                    icon_url=ctx.user.avatar.url)

            except Exception:
                pass

            embed.add_field(name="実行結果",
                            value=f":white_check_mark: 成功したユーザー数: **{successful_count}人**\n"
                                f":x: 失敗したユーザー数: **{failed_count}人**",
                            inline=True)
            embed.add_field(name="BANに失敗したユーザー (15人まで表示)",
                            value=failed_bans,
                            inline=True)
            embed.add_field(name="BAN理由",
                            value=f"{reason}",
                            inline=True)

            await ctx.followup.send(embed=embed, ephemeral=ephemeral)
            await self.dbm.log_command(ctx.user.id, "massban", [users, delete_days, reason], ctx.guild.id if ctx.guild else None, result="Success")


    # team
    @app_commands.command(name="team", description="チーム分けする")
    @app_commands.describe(users="チーム分けする項目を空白区切りで入力 (220項目まで)", teams="分けるチーム数")
    @ephemeral_check
    @restrict_check
    async def team(self, ctx: discord.Interaction, users: app_commands.Range[str, 1, 5060], teams: app_commands.Range[int, 1, 25]):
        await ctx.response.defer()

        users = re.split(r'[ 　,]+', users)
        teams_count = teams

        ephemeral = ctx.extras.get('ephemeral', False)

        if ctx.extras.get('restricted', False):
            await send_error(ctx, None, "このコマンドはサーバー管理者によって実行が制限されています。", None, is_followup=True)
            return

        # エラーチェック
        if len(users) < teams:
            await send_error(ctx, None, "チーム数が項目より多いです。", None, is_followup=True)
            return
        
        if len(users) > 220:
            await send_error(ctx, None, "指定された項目数が多すぎます。\n220項目以下にしてください。", None, is_followup=True)
            return

        # ユーザーをシャッフルし、均等にチーム分け
        random.shuffle(users)
        teams = [[] for _ in range(teams_count)]

        for i, user in enumerate(users):
            teams[i % teams_count].append(user)

        # 結果をフォーマット
        embed = discord.Embed(title="チーム分け結果",
                            description="", color=discord.Colour.green())

        for idx, team in enumerate(teams, start=1):
            embed.add_field(name=f"チーム #{idx}",
                            value=' '.join(team),
                            inline=True)

        await ctx.followup.send(embed=embed, ephemeral=ephemeral)
        await self.dbm.log_command(ctx.user.id, "team", [users, teams_count], ctx.guild.id if ctx.guild else None, result="Success")

    ##################################################

    ''' クールダウン '''

    @user.error
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

    @unban.error
    async def unban_on_command_error(self, ctx: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.checks.CommandOnCooldown):
            retry_after_int = int(error.retry_after)
            retry_minute = retry_after_int // 60
            retry_second = retry_after_int % 60
            embed = discord.Embed(title="エラー",
                                  description=f"クールダウン中です。\nあと**{retry_minute}分{retry_second}秒**お待ちください。",
                                  color=0xff0000)
            embed.set_footer(text=f"Report ID: {ctx.id}")
            return await ctx.response.send_message(embed=embed, ephemeral=True)

    @massban.error
    async def massban_on_command_error(self, ctx: discord.Interaction, error: app_commands.AppCommandError):
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
    await bot.add_cog(User(bot))
