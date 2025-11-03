# 組み込みライブラリ
import os
from datetime import datetime, timezone, timedelta

# 外部ライブラリ
import discord
from discord import app_commands
from discord.ext import commands  # Bot Commands Framework
from dotenv import load_dotenv  # python-dotenv
# import simplejson as json  # simplejson

# 自作モジュール
from modules.utils import send_error
from modules.decorators import ephemeral_check, restrict_check


load_dotenv()  # .env読み込み

##################################################

''' 定数群 '''

# エラーログ
ERROR_LOG = int(os.getenv("ERROR_LOG"))

##################################################

''' コマンド '''


class Ranking(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Cog読み込み時
    @commands.Cog.listener()
    async def on_ready(self):
        # ---- DB読み込み＆チェック ----
        self.dbm = self.bot.get_cog("DatabaseManager")

        if not self.dbm:
            raise RuntimeError("ranking: Database cog is not ready")

        if not await self.dbm.check_db():
            raise RuntimeError("ranking: Database is not ready")

        #############################

        print("ranking: Ready")

    #########################

    # /rankingコマンドをグループ化
    group = app_commands.Group(name="ranking", description="ランキングを表示するコマンド")

    # money

    @group.command(name="money", description="所持金ランキング")
    @app_commands.checks.cooldown(1, 5)
    @ephemeral_check
    @restrict_check
    async def money(self, ctx: discord.Interaction):
        await ctx.response.defer()

        ephemeral = ctx.extras.get('ephemeral', False)

        if ctx.extras.get('restricted', False):
            await send_error(ctx, None, "このコマンドはサーバー管理者によって実行が制限されています。", None, is_followup=True)
            return

        # トップ10のユーザーと自分の順位を一度に取得
        async with self.dbm.pool.acquire() as conn:
            result = await conn.fetch('''
                WITH user_data AS (
                    SELECT user_id, balance, username
                    FROM wallet_data
                    ORDER BY balance DESC
                    LIMIT 10
                ),
                user_rank AS (
                    SELECT user_id, balance, username,
                        ROW_NUMBER() OVER (ORDER BY balance DESC) AS rank
                    FROM wallet_data
                ),
                user_info AS (
                    SELECT user_id, balance, username
                    FROM wallet_data
                    WHERE user_id = $1
                ),
                rank_info AS (
                    SELECT COUNT(*) + 1 AS rank
                    FROM wallet_data
                    WHERE balance > (SELECT balance FROM user_info)
                )
                SELECT user_data.user_id, user_data.balance, user_data.username, user_rank.rank,
                    NULL AS user_balance, NULL AS user_username, NULL AS user_rank
                FROM user_data
                LEFT JOIN user_rank ON user_rank.user_id = user_data.user_id

                UNION ALL

                SELECT user_info.user_id, user_info.balance, user_info.username, (SELECT rank FROM rank_info),
                    user_info.balance AS user_balance, user_info.username AS user_username, (SELECT rank FROM rank_info) AS user_rank
                FROM user_info
            ''', ctx.user.id)

        # トップ10ユーザーと自分の順位を分ける
        top10_users = []
        user_rank = None
        user_balance = None
        user_ranked = False

        # 取得した結果を処理
        for record in result:
            if record['user_id'] == ctx.user.id:
                user_rank = record['rank']
                user_balance = record['user_balance']

            if record['rank'] <= 10:
                if record['user_id'] == ctx.user.id:
                    if user_ranked is False:
                        user_ranked = True

                    else:
                        break

                top10_users.append(f"{len(top10_users) + 1}. `@{record['username']}`  **{record['balance']:,} ZNY**")

        # 自分の順位と所持金を表示
        if user_balance is not None:
            user_rank_data = f"{user_rank}. `@{ctx.user.name}`  **{user_balance:,} ZNY**"
        else:
            user_rank_data = "集計対象外"

        # embedデータの作成
        desc = "**[所持金TOP10]**\n"
        for i in top10_users:
            desc += f"{i}\n"
        desc += f"\n**[あなたの順位]**\n{user_rank_data}"

        # 現在時刻
        now = datetime.now(timezone.utc)  # 現在時刻(UTC)
        jst = timezone(timedelta(hours=9))  # UTC+9
        now_jst = now.astimezone(jst)
        formatted_now_jst = now_jst.strftime('%Y/%m/%d %H:%M:%S')

        embed = discord.Embed(title="所持金ランキング",
                              description=desc,
                              color=discord.Colour.green())
        embed.set_footer(text=f"ランキング取得時刻: {formatted_now_jst}")
        await ctx.followup.send(embed=embed, ephemeral=ephemeral)
        await self.dbm.log_command(ctx.user.id, "ranking money", None, ctx.guild.id if ctx.guild else None, result="Success")

    # rank

    @group.command(name="rank", description="ユーザーランクランキング")
    @app_commands.checks.cooldown(1, 5)
    @ephemeral_check
    @restrict_check
    async def rank(self, ctx: discord.Interaction):
        await ctx.response.defer()

        ephemeral = ctx.extras.get('ephemeral', False)

        if ctx.extras.get('restricted', False):
            await send_error(ctx, None, "このコマンドはサーバー管理者によって実行が制限されています。", None, is_followup=True)
            return

        # トップ10のユーザーと自分の順位を一度に取得
        async with self.dbm.pool.acquire() as conn:
            result = await conn.fetch('''
                WITH user_data AS (
                    SELECT user_id, level, username
                    FROM wallet_data
                    ORDER BY level DESC
                    LIMIT 10
                ),
                user_rank AS (
                    SELECT user_id, level, username,
                        ROW_NUMBER() OVER (ORDER BY level DESC) AS rank
                    FROM wallet_data
                ),
                user_info AS (
                    SELECT user_id, level, username
                    FROM wallet_data
                    WHERE user_id = $1
                ),
                rank_info AS (
                    SELECT COUNT(*) + 1 AS rank
                    FROM wallet_data
                    WHERE level > (SELECT level FROM user_info)
                )
                SELECT user_data.user_id, user_data.level, user_data.username, user_rank.rank,
                    NULL AS user_level, NULL AS user_username, NULL AS user_rank
                FROM user_data
                LEFT JOIN user_rank ON user_rank.user_id = user_data.user_id

                UNION ALL

                SELECT user_info.user_id, user_info.level, user_info.username, (SELECT rank FROM rank_info),
                    user_info.level AS user_level, user_info.username AS user_username, (SELECT rank FROM rank_info) AS user_rank
                FROM user_info
            ''', ctx.user.id)

        # トップ10ユーザーと自分の順位を分ける
        top10_users = []
        user_rank = None
        user_level = None
        user_ranked = False

        # 取得した結果を処理
        for record in result:
            if record['user_id'] == ctx.user.id:
                user_rank = record['rank']
                # user_balance = record['user_level']

            if record['rank'] <= 10:
                if record['user_id'] == ctx.user.id:
                    if user_ranked is False:
                        user_ranked = True

                    else:
                        break

                top10_users.append(f"{len(top10_users) + 1}. `@{record['username']}`  **#{record['level']}**")

        # 自分の順位を表示
        if user_level is not None:
            user_rank_data = f"{user_rank}. `@{ctx.user.name}`  **#{user_level}**"
        else:
            user_rank_data = "集計対象外"

        # embedデータの作成
        desc = "**[ユーザーランクTOP10]**\n"
        for i in top10_users:
            desc += f"{i}\n"
        desc += f"\n**[あなたの順位]**\n{user_rank_data}"

        # 現在時刻
        now = datetime.now(timezone.utc)  # 現在時刻(UTC)
        jst = timezone(timedelta(hours=9))
        now_jst = now.astimezone(jst)
        formatted_now_jst = now_jst.strftime('%Y/%m/%d %H:%M:%S')

        embed = discord.Embed(title="ユーザーランクランキング",
                              description=desc,
                              color=discord.Colour.green())
        embed.set_footer(text=f"ランキング取得時刻: {formatted_now_jst}")
        await ctx.followup.send(embed=embed, ephemeral=ephemeral)
        await self.dbm.log_command(ctx.user.id, "ranking level", None, ctx.guild.id if ctx.guild else None, result="Success")

    # shikanoko

    @group.command(name="shikanoko", description="「しかのこ」ランキング")
    @app_commands.checks.cooldown(1, 5)
    @ephemeral_check
    @restrict_check
    async def shikanoko(self, ctx: discord.Interaction):
        await ctx.response.defer()

        ephemeral = ctx.extras.get('ephemeral', False)

        if ctx.extras.get('restricted', False):
            await send_error(ctx, None, "このコマンドはサーバー管理者によって実行が制限されています。", None, is_followup=True)
            return

        async with self.dbm.pool.acquire() as conn:
            result = await conn.fetch('''
                WITH user_data AS (
                    SELECT user_id, hits, username
                    FROM shikanoko_data
                    ORDER BY hits DESC
                    LIMIT 10
                ),
                user_rank AS (
                    SELECT user_id, hits, username,
                        ROW_NUMBER() OVER (ORDER BY hits DESC) AS rank
                    FROM shikanoko_data
                ),
                user_info AS (
                    SELECT user_id, hits, username
                    FROM shikanoko_data
                    WHERE user_id = $1
                ),
                rank_info AS (
                    SELECT COUNT(*) + 1 AS rank
                    FROM shikanoko_data
                    WHERE hits > (SELECT hits FROM user_info)
                )
                SELECT user_data.user_id, user_data.hits, user_data.username, user_rank.rank,
                    NULL AS user_hits, NULL AS user_username, NULL AS user_rank
                FROM user_data
                LEFT JOIN user_rank ON user_rank.user_id = user_data.user_id

                UNION ALL

                SELECT user_info.user_id, user_info.hits, user_info.username, (SELECT rank FROM rank_info),
                    user_info.hits AS user_hits, user_info.username AS user_username, (SELECT rank FROM rank_info) AS user_rank
                FROM user_info
            ''', ctx.user.id)

        # トップ10ユーザーと自分の順位を分ける
        top10_users = []
        user_rank = None
        user_hits = None
        user_ranked = False

        # 取得した結果を処理
        for record in result:
            if record['user_id'] == ctx.user.id:
                user_rank = record['rank']
                user_hits = record['user_hits']

            if record['rank'] <= 10:
                if record['user_id'] == ctx.user.id:
                    if user_ranked is False:
                        user_ranked = True

                    else:
                        break

                top10_users.append(f"{len(top10_users) + 1}. `@{record['username']}`  **{record['hits']:,}回**")

        # 自分の順位と出現回数を表示
        if user_hits is not None:
            user_rank_data = f"{user_rank}. `@{ctx.user.name}`  **{user_hits:,}**回"
        else:
            user_rank_data = "集計対象外"

        # embedデータの作成
        desc = "**[出現回数TOP10]**\n"
        for i in top10_users:
            desc += f"{i}\n"
        desc += f"\n**[あなたの順位]**\n{user_rank_data}"

        # 現在時刻
        now = datetime.now(timezone.utc)  # 現在時刻(UTC)
        jst = timezone(timedelta(hours=9))  # UTC+9
        now_jst = now.astimezone(jst)
        formatted_now_jst = now_jst.strftime('%Y/%m/%d %H:%M:%S')

        embed = discord.Embed(title="🦌「しかのこ」ランキング",
                              description=desc,
                              color=discord.Colour.green())
        embed.set_footer(text=f"ランキング取得時刻: {formatted_now_jst}")
        await ctx.followup.send(embed=embed, ephemeral=ephemeral)
        await self.dbm.log_command(ctx.user.id, "ranking shikanoko", None, ctx.guild.id if ctx.guild else None, result="Success")

    #########################

    ''' クールダウン '''

    @shikanoko.error
    async def shikanoko_on_command_error(self, ctx: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.checks.CommandOnCooldown):
            retry_after_int = int(error.retry_after)
            retry_minute = retry_after_int // 60
            retry_second = retry_after_int % 60
            embed = discord.Embed(title="エラー",
                                  description=f"クールダウン中です。\nあと**{retry_minute}分{retry_second}秒**お待ちください。",
                                  color=0xff0000)
            embed.set_footer(text=f"Report ID: {ctx.id}")
            return await ctx.followup.send(embed=embed, ephemeral=True)

    @money.error
    async def money_on_command_error(self, ctx: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.checks.CommandOnCooldown):
            retry_after_int = int(error.retry_after)
            retry_minute = retry_after_int // 60
            retry_second = retry_after_int % 60
            embed = discord.Embed(title="エラー",
                                  description=f"クールダウン中です。\nあと**{retry_minute}分{retry_second}秒**お待ちください。",
                                  color=0xff0000)
            embed.set_footer(text=f"Report ID: {ctx.id}")
            return await ctx.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Ranking(bot))
