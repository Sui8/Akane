# 組み込みライブラリ
import os

# 外部ライブラリ
import discord
from discord import app_commands
from discord.ext import commands  # Bot Commands Framework
from dotenv import load_dotenv  # python-dotenv
import simplejson as json  # simplejson

# 自作モジュール
from modules.shika import shika
from modules.utils import send_error
from modules.decorators import ephemeral_check, restrict_check


load_dotenv()  # .env読み込み

##################################################

''' 定数群 '''

# エラーログ
ERROR_LOG = int(os.getenv("ERROR_LOG"))

##################################################

''' コマンド '''


class Shikanoko(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Cog読み込み時
    @commands.Cog.listener()
    async def on_ready(self):
        # ---- DB読み込み＆チェック ----
        self.dbm = self.bot.get_cog("DatabaseManager")

        if not self.dbm:
            raise RuntimeError("shikanoko: Database cog is not ready")

        if not await self.dbm.check_db():
            raise RuntimeError("shikanoko: Database is not ready")

        #############################

        print("shikanoko: ready")

    #########################

    # shikanoko

    @app_commands.command(name="shikanoko", description="「しかのこのこのここしたんたん」を引き当てよう")
    @app_commands.checks.cooldown(1, 1)
    @app_commands.describe(pcs="回数（1~20）")
    @ephemeral_check
    @restrict_check
    async def shikanoko(self, ctx: discord.Interaction, pcs: app_commands.Range[int, 1, 20] = 1):
        await ctx.response.defer()

        ephemeral = ctx.extras.get('ephemeral', False)

        if ctx.extras.get('restricted', False):
            await send_error(ctx, None, "このコマンドはサーバー管理者によって実行が制限されています。", None, is_followup=True)
            return

        results = []

        for i in range(pcs):
            c = "し"
            words = [c]

            while True:
                c = shika(c)

                if c == "END":
                    word = "".join(words)
                    results.append(word)
                    break

                else:
                    words.append(c)

        # 総実行回数更新
        async with self.dbm.pool.acquire() as conn:
            async with conn.transaction():
                try:
                    await conn.execute('''
                                       UPDATE bot_data
                                       SET value = CAST(value AS INTEGER) + $1
                                       WHERE name = $2
                                       ''',
                                       pcs, "shikanoko_total_draws")

                except Exception as e:
                    await send_error(ctx, "0x00003", None, self.bot.SUPPORT_SERVER, is_followup=True)
                    await self.dbm.log_command(ctx.user.id, "shikanoko", pcs, ctx.guild.id if ctx.guild else None, result=f"0x00003 ({e})")
                    return

        if "しかのこのこのここしたんたん" in results:
            n = results.count("しかのこのこのここしたんたん")
            status = "**あたり！**"
            winner = [ctx.user.id, ctx.user.name]

            # 最新のあたり者と総当たり回数書き込み
            async with self.dbm.pool.acquire() as conn:
                async with conn.transaction():
                    try:
                        await conn.execute('''
                                           UPDATE bot_data
                                           SET value = $1
                                           WHERE name = $2
                                           ''',
                                           json.dumps(winner), "shikanoko_latest_winner")
                        await conn.execute('''
                                           UPDATE bot_data
                                           SET value = CAST(value AS INTEGER) + $1
                                           WHERE name = $2
                                           ''',
                                           n, "shikanoko_total_hits")

                    except Exception as e:
                        await send_error(ctx, "0x00003", None, self.bot.SUPPORT_SERVER, is_followup=True)
                        await self.dbm.log_command(ctx.user.id, "shikanoko", pcs, ctx.guild.id if ctx.guild else None, result=f"0x00003 ({e})")
                        return

            # DBでuser_idが存在するか確認
            async with self.dbm.pool.acquire() as conn:
                hits = await conn.fetchval('SELECT hits FROM shikanoko_data WHERE user_id = $1', ctx.user.id)

            if not hits:
                # 新規ユーザーの場合
                async with self.dbm.pool.acquire() as conn:
                    async with conn.transaction():
                        try:
                            await conn.execute('INSERT INTO shikanoko_data (user_id, username, hits) VALUES ($1, $2, $3)',
                                               ctx.user.id, ctx.user.name, n)

                        except Exception as e:
                            await send_error(ctx, "0x00003", None, self.bot.SUPPORT_SERVER, is_followup=True)
                            await self.dbm.log_command(ctx.user.id, "shikanoko", pcs, ctx.guild.id if ctx.guild else None, result=f"0x00003 ({e})")
                            return
            else:
                # 既存ユーザーの場合、あたり回数とユーザー名を更新
                async with self.dbm.pool.acquire() as conn:
                    async with conn.transaction():
                        try:
                            await conn.execute(f'''
                                                UPDATE shikanoko_data
                                                SET hits = hits + {n}, last_hit_time = CURRENT_TIMESTAMP, username = $1
                                                WHERE user_id = $2
                                                ''', ctx.user.name, ctx.user.id)

                        except Exception as e:
                            await send_error(ctx, "0x00003", None, self.bot.SUPPORT_SERVER, is_followup=True)
                            await self.dbm.log_command(ctx.user.id, "shikanoko", pcs, ctx.guild.id if ctx.guild else None, result=f"0x00003 ({e})")
                            return

        else:
            status = "はずれ..."

        # 総あたり回数と総実行回数、あたり者を表示
        async with self.dbm.pool.acquire() as conn:
            total_hits = await conn.fetchval('''
                                             SELECT CAST(value AS INTEGER) AS numeric_value
                                             FROM bot_data
                                             WHERE name = $1
                                             ''',
                                             "shikanoko_total_hits")
            total_draws = await conn.fetchval('''
                                              SELECT CAST(value AS INTEGER) AS numeric_value
                                              FROM bot_data
                                              WHERE name = $1
                                              ''',
                                              "shikanoko_total_draws")
            latest_winner = await conn.fetchval('''
                                                SELECT value
                                                FROM bot_data
                                                WHERE name = $1
                                                ''',
                                                "shikanoko_latest_winner")

        if latest_winner:
            latest_winner = json.loads(latest_winner)[1]

        else:
            latest_winner = "なし"

        # 結果を変数にまとめる
        result = ""

        for i in results:
            if i == "しかのこのこのここしたんたん":
                i = "**しかのこのこのここしたんたん**"

            result += f"・{i}\n"

        probability = round((total_hits / total_draws) * 100, 2)
        embed = discord.Embed(title=":deer: しかのこのこのここしたんたん",
                              description=f"{result}\n{status}",
                              color=discord.Colour.green())
        embed.set_footer(text=f"統計: {total_hits:,}/{total_draws:,}回当たり ({probability}%)  直近の当選者: @{latest_winner}")
        await ctx.followup.send(embed=embed, ephemeral=ephemeral)
        await self.dbm.log_command(ctx.user.id, "shikanoko", pcs, ctx.guild.id if ctx.guild else None, result="Success")

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
            return await ctx.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Shikanoko(bot))
