# 組み込みライブラリ
import secrets
from datetime import datetime, timedelta, timezone
import re
import random
import string

# 外部ライブラリ
import discord
from discord import app_commands
from discord.ext import commands  # Bot Commands Framework
# import simplejson as json  # simplejson

# 自作モジュール
from modules.utils import send_error
from modules.decorators import ephemeral_check, restrict_check


##################################################

SEND_TAX = 0.10  # 送金手数料
grade_mapping = {"0": "New Worker", "1": "Worker", "2": "Expert", "3": "Expert+",
                 "4": "Trusted", "5": "Trusted✅", "6": "Moderator"}

##################################################


def get_level_from_experience(total_experience):
    """
    総獲得経験値に基づいてレベルを計算する関数
    ※経験値は指数的に増加
    """
    base_xp = 100  # レベル1→2に必要な経験値
    growth_factor = 1.2  # 経験値増加の指数係数

    level = 1  # レベル1からスタート
    required_xp = base_xp

    # 経験値がレベルアップに達するまで繰り返し
    while total_experience >= required_xp:
        total_experience -= required_xp
        level += 1
        required_xp = int(base_xp * (level ** growth_factor))

    # レベル上限
    if level > 500:
        level = 500

    return level


def get_next_level_experience(total_experience):
    """
    現在の総獲得経験値に基づいて次のレベルに到達するために必要な経験値を計算する関数
    """
    base_xp = 100  # レベル1→2に必要な経験値
    growth_factor = 1.2  # 経験値増加の指数係数 かつては1.5, Lv.100まで

    level = 1  # レベル1からスタート
    required_xp = base_xp

    # 現在のレベルを計算
    while total_experience >= required_xp:
        total_experience -= required_xp
        level += 1
        required_xp = int(base_xp * (level ** growth_factor))

    # レベル100でストップ
    if level >= 500:
        return 0

    # 次のレベルに必要な経験値
    next_level_experience = required_xp - total_experience
    return next_level_experience

##################################################


''' コマンド '''


class Money(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Cog読み込み時

    @commands.Cog.listener()
    async def on_ready(self):
        # ---- DB読み込み＆チェック ----
        self.dbm = self.bot.get_cog("DatabaseManager")

        if not self.dbm:
            raise RuntimeError("money: Database cog is not ready")

        if not await self.dbm.check_db():
            raise RuntimeError("money: Database is not ready")

        #############################

        print("money: Ready")

    #########################

    # wallet

    @app_commands.command(name="wallet", description="ウォレットを表示します")
    @app_commands.checks.cooldown(2, 10)
    @ephemeral_check
    @restrict_check
    async def wallet(self, ctx: discord.Interaction):
        await ctx.response.defer()
        ephemeral = ctx.extras.get('ephemeral', False)

        if ctx.extras.get('restricted', False):
            await send_error(ctx, None, "このコマンドはサーバー管理者によって実行が制限されています。", None, is_followup=True)
            return

        # DBでuser_idが存在するか確認
        async with self.dbm.pool.acquire() as conn:
            result = await conn.fetchrow("""
                SELECT balance, exp, level, total_login, last_login, trust_rank
                FROM wallet_data
                WHERE user_id = $1
            """, ctx.user.id)

        now = datetime.now(timezone.utc)  # 現在時刻(UTC)

        # UTC+9
        jst = timezone(timedelta(hours=9))
        now_jst = now.astimezone(jst)
        formatted_now_jst = now_jst.strftime('%Y/%m/%d %H:%M:%S')

        # ウォレットを持っていればログイン、持っていなければ作成
        if result:
            balance, exp, level, total_login, last_login, grade = result[0], result[1], result[2], result[3], result[4], result[5]

            # UTC+9変換と翌日計算
            last_login = last_login.replace(tzinfo=timezone.utc)  # timezone付与
            last_login_dt = last_login.astimezone(jst)
            next_day = last_login_dt.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)

            # 翌日以降かどうか
            if now_jst >= next_day:
                new_total_login = total_login + 1

                # 7日ボーナス
                if new_total_login % 7 == 0:
                    bonus = 5000
                    exp_bonus = 12500

                    # 試験中 レベルブースト
                    bonus += int(bonus * (level - 1) * 0.05)
                    exp_bonus += int(exp_bonus * (level - 1) * 0.1)

                else:
                    bonus = 1000
                    exp_bonus = 2500

                    # 試験中 レベルブースト
                    bonus += int(bonus * (level - 1) * 0.05)
                    exp_bonus += int(exp_bonus * (level - 1) * 0.1)

                # 新しいレベルを計算
                new_level = get_level_from_experience(exp + exp_bonus)

                # グレードアップしているか
                if new_level >= 350 and new_total_login >= 31 and grade < 4:
                    new_grade = 4

                elif new_level >= 200 and new_total_login >= 21 and grade < 3:
                    new_grade = 3

                elif new_level >= 100 and new_total_login >= 14 and grade < 2:
                    new_grade = 2

                elif new_level >= 30 and new_total_login >= 7 and grade < 1:
                    new_grade = 1

                else:
                    new_grade = grade

                async with self.dbm.pool.acquire() as conn:
                    async with conn.transaction():
                        try:
                            await conn.execute(
                                '''
                                UPDATE wallet_data
                                SET
                                    balance = $1, badges = $2,
                                    exp = $3, last_login = $4,
                                    total_login = $5, username = $6,
                                    level = $7, trust_rank = $8
                                WHERE user_id = $9
                                ''',
                                balance + bonus, "",
                                exp + exp_bonus, now.replace(tzinfo=None),
                                new_total_login, ctx.user.name,
                                new_level, new_grade,
                                ctx.user.id
                                )

                        except Exception as e:
                            await send_error(ctx, "0x00003", None, self.bot.SUPPORT_SERVER, is_followup=True)
                            await self.dbm.log_command(ctx.user.id, "wallet", None, ctx.guild.id if ctx.guild else None, result=f"0x00003 ({e})")
                            return

                # embed説明
                description = f"**所持金**: {balance + bonus:,} ZNY\n\n:white_check_mark: ログイン ({new_total_login}日目) **+{bonus:,} ZNY**"

                # レベルが上がったなら
                if new_level != level:
                    description += f"\n:up: ランクアップ！(Rank {result[2]}→**Rank {new_level}**)"

                # グレードが上がったなら
                if new_grade != grade:
                    grade_text = grade_mapping.get(str(grade), "不明")
                    new_grade_text = grade_mapping.get(str(new_grade), "不明")
                    description += f"\n:up: グレードアップ！({grade_text}→**{new_grade_text}**)"

                embed = discord.Embed(title=f"@{ctx.user.name} のウォレット",
                                      description=description,
                                      color=discord.Colour.green())
                embed.set_footer(text=f"最終ログイン: {formatted_now_jst}")
                await ctx.followup.send(embed=embed, ephemeral=ephemeral)
                await self.dbm.log_command(ctx.user.id, "wallet", None, ctx.guild.id if ctx.guild else None, result="Success")

            else:
                embed = discord.Embed(title=f"@{ctx.user.name} のウォレット",
                                      description=f"**所持金**: {balance:,} ZNY",
                                      color=discord.Colour.green())
                embed.set_footer(text=f"最終ログイン: {last_login_dt.strftime('%Y/%m/%d %H:%M:%S')}")
                await ctx.followup.send(embed=embed, ephemeral=ephemeral)
                await self.dbm.log_command(ctx.user.id, "wallet", None, ctx.guild.id if ctx.guild else None, result="Success")

        # 持っていなければ1,000ZNY与えて作成
        else:
            # last_workを適当に設定
            last_str = (now - timedelta(hours=1))

            async with self.dbm.pool.acquire() as conn:
                async with conn.transaction():
                    try:
                        await conn.execute(
                            '''
                            INSERT INTO wallet_data (
                                user_id, username, balance,
                                badges, exp, level,
                                total_login, last_login, last_work,
                                trust_rank)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                            ''',
                            ctx.user.id, ctx.user.name, 1000,
                            "", 0, 1,
                            1, now.replace(tzinfo=None), last_str.replace(tzinfo=None),
                            0
                            )

                    except Exception as e:
                        await send_error(ctx, "0x00003", None, self.bot.SUPPORT_SERVER, is_followup=True)
                        await self.dbm.log_command(ctx.user.id, "wallet", None, ctx.guild.id if ctx.guild else None, result=f"0x00003 ({e})")
                        return

            embed = discord.Embed(title=f"@{ctx.user.name} のウォレット",
                                  description="**所持金**: 1,000 ZNY\n\n:white_check_mark: 初回ログイン **+1,000 ZNY**",
                                  color=discord.Colour.green())
            embed.set_footer(text=f"最終ログイン: {formatted_now_jst}")
            await ctx.followup.send(embed=embed, ephemeral=ephemeral)
            await self.dbm.log_command(ctx.user.id, "wallet", None, ctx.guild.id if ctx.guild else None, result="Success")

    # send

    @app_commands.command(name="send", description="ユーザーに送金します（手数料10%）")
    @app_commands.describe(user="送金先ユーザーをメンションまたはユーザーIDで指定")
    @app_commands.describe(amount="送金金額を入力")
    @ephemeral_check
    @restrict_check
    async def send(self, ctx: discord.Interaction, user: str, amount: app_commands.Range[int, 100]):
        await ctx.response.defer()
        ephemeral = ctx.extras.get('ephemeral', False)

        if ctx.extras.get('restricted', False):
            await send_error(ctx, None, "このコマンドはサーバー管理者によって実行が制限されています。", None, is_followup=True)
            return

        try:
            # メンションからID抽出
            target = re.sub("\\D", "", user)
            target = int(target)
            target_obj = await self.bot.fetch_user(target)

        except Exception:
            embed = discord.Embed(title=":x: エラー",
                                  description="ユーザーが見つかりませんでした",
                                  color=0xff0000)
            await ctx.followup.send(embed=embed, ephemeral=True)

        else:
            if target == ctx.user.id:
                await send_error(ctx, None, "自分自身には送金できません", None, is_followup=True)
                await self.dbm.log_command(ctx.user.id, "send", [user, amount], ctx.guild.id if ctx.guild else None, result="Failed (Mistake)")
                return

            # DBから自分とターゲットユーザーの情報を取得
            async with self.dbm.pool.acquire() as conn:
                sender_data = await conn.fetchval("SELECT balance FROM wallet_data WHERE user_id = $1",
                                                  ctx.user.id)
                target_data = await conn.fetchval("SELECT balance FROM wallet_data WHERE user_id = $1",
                                                  target)

            # 送金元ウォレットの存在確認
            if not sender_data:
                await send_error(ctx, None, "所持金が不足しています", None, is_followup=True)
                await self.dbm.log_command(ctx.user.id, "send", [user, amount], ctx.guild.id if ctx.guild else None, result="Failed (Mistake)")
                return

            # 送金先ウォレットの存在確認
            if not target_data:
                await send_error(ctx, None, "そのユーザーはウォレットを開設していません。\n`/wallet`コマンドを実行するよう依頼してください。", None, is_followup=True)
                await self.dbm.log_command(ctx.user.id, "send", [user, amount], ctx.guild.id if ctx.guild else None, result="Failed (Mistake)")
                return

            sender_balance = sender_data
            target_balance = target_data

            # 所持金の範囲か
            if sender_balance < amount:
                await send_error(ctx, None, "所持金が不足しています", None, is_followup=True)
                await self.dbm.log_command(ctx.user.id, "send", [user, amount], ctx.guild.id if ctx.guild else None, result="Failed (Mistake)")
                return

            transaction_time = datetime.now()  # 現在時刻 without timezoneにしないとエラー吐く

            # 時間変換
            jst = timezone(timedelta(hours=9))
            formatted_transaction_time = transaction_time.strftime("%Y/%m/%d %H:%M:%S")

            transaction_id = secrets.token_hex(10)

            flag = False

            # IDの生成を5回試行する
            for i in range(5):
                transaction_id = secrets.token_hex(10)

                # 生成したIDが既に存在しないか確認
                async with self.dbm.pool.acquire() as conn:
                    query = "SELECT 1 FROM transactions WHERE transaction_id = $1"
                    result = await conn.fetchval(query, transaction_id)

                if not result:
                    flag = True
                    break

            else:
                flag = False

            if not flag:
                await send_error(ctx, "0x00102", "システムエラーが発生しました。\n再度お試しいただくか、", self.bot.SUPPORT_SERVER, is_followup=True)
                await self.dbm.log_command(ctx.user.id, "send", [user, amount], ctx.guild.id if ctx.guild else None, result="0x00102")
                return

            tax = int(amount * SEND_TAX)  # 手数料

            # データのセーブ
            async with self.dbm.pool.acquire() as conn:
                async with conn.transaction():
                    try:
                        await conn.execute(
                            '''
                            UPDATE wallet_data
                            SET balance = $1, username = $2
                            WHERE user_id = $3
                            ''',
                            sender_balance - amount, ctx.user.name, ctx.user.id
                            )
                        await conn.execute(
                            '''
                            UPDATE wallet_data
                            SET balance = $1, username = $2
                            WHERE user_id = $3
                            ''',
                            target_balance + (amount - tax), target_obj.name, target
                            )
                        # transactionをDBに書き込み
                        await conn.execute(
                            '''
                            INSERT INTO transactions (
                                transaction_id, from_user_id,
                                to_user_id, amount,
                                tax, timestamp
                                )
                            VALUES ($1, $2, $3, $4, $5, $6)
                            ''',
                            transaction_id, ctx.user.id,
                            target, (amount - tax),
                            tax, transaction_time
                            )

                    except Exception as e:
                        await send_error(ctx, "0x00003", None, self.bot.SUPPORT_SERVER, is_followup=True)
                        await self.dbm.log_command(
                            ctx.user.id, "send", [user, amount],
                            ctx.guild.id if ctx.guild else None, result=f"0x00003 ({e})"
                            )
                        return

            embed = discord.Embed(title="送金完了",
                                  description=f"**送金元**: `@{ctx.user.name}`\n"
                                              f"**送金先**: `@{target_obj.name}`\n"
                                              f"**送金額**: {amount - tax:,} ZNY (手数料: {tax:,} ZNY)\n"
                                              f"**トランザクションID**: {transaction_id}\n"
                                              f"**送金時刻**: {formatted_transaction_time} (UTC+9)",
                                  color=discord.Colour.green())
            await ctx.followup.send(embed=embed, ephemeral=ephemeral)
            await self.dbm.log_command(ctx.user.id, "send", [user, amount], ctx.guild.id if ctx.guild else None, result="Success")

    # /giftコマンドをグループ化
    group = app_commands.Group(name="gift", description="ギフト関係のコマンド")

    @group.command(name="create", description="ギフトを作成します (手数料10%)")
    @app_commands.describe(amount="金額を入力 (手数料別)")
    @app_commands.describe(message="メッセージを記入 (400文字以内)")
    @restrict_check
    async def gift_create(self, ctx: discord.Interaction, amount: app_commands.Range[int, 100], message: app_commands.Range[str, 1, 400] = None):
        await ctx.response.defer(ephemeral=True)

        if ctx.extras.get('restricted', False):
            await send_error(ctx, None, "このコマンドはサーバー管理者によって実行が制限されています。", None, is_followup=True)
            return

        if not message:
            message = "ギフトをお送りします。"

        # DBから自分の情報を取得
        async with self.dbm.pool.acquire() as conn:
            sender_data = await conn.fetchval("SELECT balance FROM wallet_data WHERE user_id = $1",
                                              ctx.user.id)

        # 送金元ウォレットの存在確認
        if not sender_data:
            await send_error(ctx, None, "所持金が不足しています", None, is_followup=True)
            await self.dbm.log_command(ctx.user.id, "gift create", [amount, message], ctx.guild.id if ctx.guild else None, result="Failed (Mistake)")
            return

        sender_balance = sender_data

        # 所持金の範囲か
        if sender_balance < int(amount * (1 + SEND_TAX)):
            await send_error(ctx, None, "所持金が不足しています。\n※ギフト作成には手数料が別にかかります", None, is_followup=True)
            await self.dbm.log_command(ctx.user.id, "gift create", [amount, message], ctx.guild.id if ctx.guild else None, result="Failed (Mistake)")
            return

        transaction_time = datetime.now(timezone.utc)  # 現在時刻

        gift_id = secrets.token_hex(10)
        flag = False

        # ギフトIDの生成
        characters = string.ascii_letters + string.digits

        for i in range(5):
            gift_id = "".join(random.choice(characters) for _ in range(8))

            # 生成したIDが既に存在しないか確認
            async with self.dbm.pool.acquire() as conn:
                query = "SELECT 1 FROM gifts WHERE gift_id = $1"
                result = await conn.fetchval(query, gift_id)

            if not result:
                flag = True
                break

        else:
            flag = False

        if not flag:
            await send_error(ctx, "0x00102", "システムエラーが発生しました。\n再度お試しいただくか、", self.bot.SUPPORT_SERVER, is_followup=True)
            await self.dbm.log_command(ctx.user.id, "gift create", [amount, message], ctx.guild.id if ctx.guild else None, result="0x00102")
            return

        tax = int(amount * SEND_TAX)  # 手数料

        # データのセーブ
        async with self.dbm.pool.acquire() as conn:
            async with conn.transaction():
                try:
                    await conn.execute(
                        '''
                        INSERT INTO gifts (
                            gift_id, made_user_id,
                            gift_type, amount,
                            message, status,
                            timestamp
                            )
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                        ''',
                        gift_id, ctx.user.id,
                        "money", str(amount),
                        message, "Unused",
                        transaction_time
                        )
                    await conn.execute(
                        '''
                        UPDATE wallet_data
                        SET balance = $1, username = $2
                        WHERE user_id = $3
                        ''',
                        (sender_balance - int(amount * 1.1)),
                        ctx.user.name, ctx.user.id
                        )

                except Exception as e:
                    await send_error(ctx, "0x00003", None, self.bot.SUPPORT_SERVER, is_followup=True)
                    await self.dbm.log_command(
                        ctx.user.id, "gift create", [amount, message],
                        ctx.guild.id if ctx.guild else None, result=f"0x00003 ({e})"
                        )
                    return

        embed = discord.Embed(title=":white_check_mark: ギフトを作成しました",
                              description=f"**金額**: {amount:,} ZNY (手数料: {tax:,} ZNY)\n"
                                          f":arrow_up: **上に表示されている8桁の文字列がギフトIDです**\n"
                                          f"ギフトは`/gift receive`コマンドで受け取れます",
                              color=discord.Colour.green())
        await ctx.followup.send(gift_id, embed=embed, ephemeral=True)
        await self.dbm.log_command(ctx.user.id, "gift create", [amount, message], ctx.guild.id if ctx.guild else None, result="Success")

    # info

    @group.command(name="info", description="ギフトコードの情報を確認します")
    @app_commands.describe(code="ギフトコード")
    @app_commands.checks.cooldown(1, 3)
    @restrict_check
    async def gift_info(self, ctx: discord.Interaction, code: str):
        await ctx.response.defer(ephemeral=True)

        if ctx.extras.get('restricted', False):
            await send_error(ctx, None, "このコマンドはサーバー管理者によって実行が制限されています。", None, is_followup=True)
            return

        try:
            # DBから情報を取得
            async with self.dbm.pool.acquire() as conn:
                gift_data = await conn.fetchrow(
                    '''
                    SELECT
                        made_user_id, gift_type,
                        amount, message,
                        status, timestamp
                    FROM gifts
                    WHERE gift_id = $1
                    ''',
                    code
                    )

            # 送金元ウォレットの存在確認
            if not gift_data:
                await send_error(ctx, None, "ギフトが存在しません。\nコードが正しいか確認してください。", None, is_followup=True)
                await self.dbm.log_command(ctx.user.id, "gift info", code, ctx.guild.id if ctx.guild else None, result="Failed (Mistake)")
                return

            made_user_id, gift_type, amount, message, status, timestamp = gift_data

            # 時間変換
            timestamp_ = timestamp.strftime("%Y/%m/%d %H:%M:%S")

            if gift_type == "money":
                amount = int(amount)
                gift_description = f"{amount:,} ZNY"

            else:
                gift_description = amount

            if status == "Unused":
                status_ = "未使用"

            elif status == "Used":
                status_ = "使用済"

            elif status == "Banned":
                status_ = "凍結中"

            elif status == "Free":
                status_ = "配布(1人1回まで)"

            else:
                status_ = "不明"

            embed = discord.Embed(title="ギフトの情報",
                                  description=f"**ギフトコード**: {code}\n"
                                              f"**状態**: {status_}\n"
                                              f"**内容**: {gift_description}\n"
                                              f"**作成者**: `{made_user_id}`\n"
                                              f"**作成時刻**: {timestamp_} (UTC)\n"
                                              f"**メッセージ**\n{message}",
                                  color=discord.Colour.green())
            embed.set_footer(text="ギフトの受け取り: /gift receive <ギフトコード>")
            await ctx.followup.send(embed=embed, ephemeral=True)
            await self.dbm.log_command(ctx.user.id, "gift info", code, ctx.guild.id if ctx.guild else None, result="Success")

        except Exception:
            import traceback
            print(traceback.format_exc())

    # receive

    @group.command(name="receive", description="ギフトを受け取ります")
    @app_commands.describe(code="ギフトコード")
    @app_commands.checks.cooldown(1, 3)
    @ephemeral_check
    @restrict_check
    async def gift_receive(self, ctx: discord.Interaction, code: str):
        await ctx.response.defer()

        if ctx.extras.get('restricted', False):
            await send_error(ctx, None, "このコマンドはサーバー管理者によって実行が制限されています。", None, is_followup=True)
            return

        try:
            ephemeral = ctx.extras.get('ephemeral', False)

            # DBから情報を取得
            async with self.dbm.pool.acquire() as conn:
                gift_data = await conn.fetchrow(
                    '''
                    SELECT
                        made_user_id, gift_type,
                        amount, message,
                        status, timestamp
                    FROM gifts
                    WHERE gift_id = $1
                    ''',
                    code
                    )

            # 送金元ウォレットの存在確認
            if not gift_data:
                await send_error(ctx, None, "ギフトが存在しません。\nコードが正しいか確認してください。", None, is_followup=True)
                await self.dbm.log_command(ctx.user.id, "gift receive", code, ctx.guild.id if ctx.guild else None, result="Failed (Mistake)")
                return

            made_user_id, gift_type, amount, message, status, timestamp = gift_data

            # ステータス確認
            if status == "Used":
                await send_error(ctx, None, "このギフトは受け取り済みです", None, is_followup=True)
                await self.dbm.log_command(ctx.user.id, "gift receive", code, ctx.guild.id if ctx.guild else None, result="Failed (Mistake)")
                return

            elif status == "Banned":
                await send_error(ctx, None, "このギフトは運営によって凍結されています", None, is_followup=True)
                await self.dbm.log_command(ctx.user.id, "gift receive", code, ctx.guild.id if ctx.guild else None, result="Failed (Mistake)")
                return

            elif status == "Free":
                async with self.dbm.pool.acquire() as conn:
                    gift_received = await conn.fetchrow('''
                                                        SELECT gift_id, received_user_id
                                                        FROM gifts_log
                                                        WHERE gift_id = $1 AND received_user_id = $2
                                                        ''', code, ctx.user.id)

                if gift_received:
                    await send_error(ctx, None, "あなたはこのギフトを受け取り済みです", None, is_followup=True)
                    await self.dbm.log_command(ctx.user.id, "gift receive", code, ctx.guild.id if ctx.guild else None, result="Failed (Mistake)")
                    return

                else:
                    new_status = "Free"

            else:
                new_status = "Used"

            transaction_time = datetime.now(timezone.utc)  # 現在時刻

            # 時間変換
            timestamp_ = timestamp.strftime("%Y/%m/%d %H:%M:%S")

            if gift_type == "money":
                # DBから情報を取得
                async with self.dbm.pool.acquire() as conn:
                    data = await conn.fetchval(
                        '''
                        SELECT balance
                        FROM wallet_data
                        WHERE user_id = $1
                        ''',
                        ctx.user.id
                        )

                if not data:
                    await send_error(
                        ctx, None, "あなたはウォレットを開設していません。\n`/wallet`コマンドを実行してからお試しください。",
                        None, is_followup=True
                        )
                    await self.dbm.log_command(ctx.user.id, "gift receive", code, ctx.guild.id if ctx.guild else None, result="Failed (Mistake)")
                    return

                amount = int(amount)

                # データのセーブ
                async with self.dbm.pool.acquire() as conn:
                    async with conn.transaction():
                        try:
                            await conn.execute(
                                '''
                                INSERT INTO gifts_log (gift_id, received_user_id, timestamp)
                                VALUES ($1, $2, $3)
                                ''',
                                code, ctx.user.id, transaction_time
                                )
                            await conn.execute(
                                '''
                                UPDATE wallet_data
                                SET balance = $1, username = $2
                                WHERE user_id = $3
                                ''',
                                data + amount, ctx.user.name, ctx.user.id
                                )
                            await conn.execute(
                                '''
                                UPDATE gifts
                                SET status = $1
                                WHERE gift_id = $2
                                ''',
                                new_status, code
                                )

                        except Exception as e:
                            await send_error(ctx, "0x00003", None, self.bot.SUPPORT_SERVER, is_followup=True)
                            await self.dbm.log_command(
                                ctx.user.id, "gift receive", code,
                                ctx.guild.id if ctx.guild else None, result=f"0x00003 ({e})"
                                )
                            return

                gift_description = f"**{amount:,} ZNY**を受け取りました"

            else:
                # データのセーブ
                async with self.dbm.pool.acquire() as conn:
                    async with conn.transaction():
                        try:
                            await conn.execute(
                                '''
                                INSERT INTO gifts_log (gift_id, received_user_id, timestamp)
                                VALUES ($1, $2, $3)
                                ''',
                                code, ctx.user.id, transaction_time
                                )
                            await conn.execute(
                                '''
                                UPDATE gifts
                                SET status = $1
                                WHERE gift_id = $2
                                ''',
                                new_status, code)

                        except Exception as e:
                            await send_error(ctx, "0x00003", None, self.bot.SUPPORT_SERVER, is_followup=True)
                            await self.dbm.log_command(
                                ctx.user.id, "gift receive", code,
                                ctx.guild.id if ctx.guild else None, result=f"0x00003 ({e})"
                                )
                            return

                gift_description = f"**{amount}**を受け取りました"

            embed = discord.Embed(title=":white_check_mark: 受け取り完了",
                                  description=f"{gift_description}\n"
                                              f"**送信者**: `{made_user_id}`\n"
                                              f"**メッセージ**\n{message}",
                                  color=discord.Colour.green())
            embed.set_footer(text=f"受け取り時刻: {timestamp_} (UTC+9)")
            await ctx.followup.send(embed=embed, ephemeral=ephemeral)
            await self.dbm.log_command(ctx.user.id, "gift receive", code, ctx.guild.id if ctx.guild else None, result="Success")

        except Exception:
            import traceback
            print(traceback.format_exc())

    # work

    @app_commands.command(name="work", description="20分に1回働いてお金を貰えます")
    @ephemeral_check
    @restrict_check
    async def work(self, ctx: discord.Interaction):
        await ctx.response.defer()

        if ctx.extras.get('restricted', False):
            await send_error(ctx, None, "このコマンドはサーバー管理者によって実行が制限されています。", None, is_followup=True)
            return

        ephemeral = ctx.extras.get('ephemeral', False)

        # DBでuser_idが存在するか確認
        async with self.dbm.pool.acquire() as conn:
            result = await conn.fetchrow(
                """
                SELECT username, balance, exp, level, last_work, trust_rank, total_login
                FROM wallet_data
                WHERE user_id = $1
                """,
                ctx.user.id
                )

        if not result:
            await send_error(ctx, None, "あなたはウォレットを開設していません。\n`/wallet`コマンドを実行してからお試しください。", None, is_followup=True)
            await self.dbm.log_command(ctx.user.id, "work", None, ctx.guild.id if ctx.guild else None, result="Failed (Mistake)")
            return

        previous = result[4]
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        time_difference = now - previous  # 秒数差計算
        seconds_difference = time_difference.total_seconds()  # 秒数に直す

        if seconds_difference < 1200:
            await send_error(
                ctx, None, f"前回の仕事から20分経過していません。\n<t:{int(previous.timestamp()) + 1200 + 32400}:R>にお試しください。",
                None, is_followup=True
                )
            await self.dbm.log_command(ctx.user.id, "work", None, ctx.guild.id if ctx.guild else None, result="Failed (Mistake)")
            return

        works = [300, 400, 450, 500, 550, 600, 650, 700, 750, 800, 1000]
        xps = [1000, 1500, 1750, 2000, 2250, 2500]
        salary = random.choice(works)
        gain_xp = random.choice(xps)
        grade = result['trust_rank']
        total_login = result['total_login']

        # 試験中 レベルブースト
        salary += int(salary * (result[3] - 1) * 0.05)
        gain_xp += int(gain_xp * (result[3] - 1) * 0.1)

        new_balance = result[1] + salary
        new_exp = result[2] + gain_xp
        new_last_work = now

        # 新しいレベルを計算
        new_level = get_level_from_experience(new_exp)

        # グレードアップしているか
        if new_level >= 350 and total_login >= 31 and grade < 4:
            new_grade = 4

        elif new_level >= 200 and total_login >= 21 and grade < 3:
            new_grade = 3

        elif new_level >= 100 and total_login >= 14 and grade < 2:
            new_grade = 2

        elif new_level >= 30 and total_login >= 7 and grade < 1:
            new_grade = 1

        else:
            new_grade = grade

        embed_title = f"✅ {salary:,} ZNY獲得しました (+{gain_xp:,} XP)"
        embed_description = f"所持金: {new_balance:,} ZNY"

        if new_level != result[3]:
            # レベルアップ
            embed_description += f"\n\n:up: ランクアップ！ (Rank {result[3]}→**Rank {new_level}**)"

        if new_grade != grade:
            # レベルアップ
            grade_text = grade_mapping.get(str(grade), "不明")
            new_grade_text = grade_mapping.get(str(new_grade), "不明")
            embed_description += f"\n\n:up: グレードアップ！({grade_text}→**{new_grade_text}**)"

        # トランザクション内でまとめて処理
        async with self.dbm.pool.acquire() as conn:
            async with conn.transaction():
                try:
                    await conn.execute('''
                        UPDATE wallet_data
                        SET balance = $1, exp = $2, last_work = $3, username = $4, level = $5, trust_rank = $6
                        WHERE user_id = $7
                    ''', new_balance, new_exp, new_last_work, ctx.user.name, new_level, new_grade, ctx.user.id)

                except Exception as e:
                    await send_error(ctx, "0x00003", None, self.bot.SUPPORT_SERVER, is_followup=True)
                    await self.dbm.log_command(ctx.user.id, "work", None, ctx.guild.id if ctx.guild else None, result=f"0x00003 ({e})")
                    return

        embed = discord.Embed(title=embed_title,
                              description=embed_description,
                              color=discord.Colour.green())

        await ctx.followup.send(embed=embed, ephemeral=ephemeral)
        await self.dbm.log_command(ctx.user.id, "work", None, ctx.guild.id if ctx.guild else None, result="Success")

    # rank
    @app_commands.command(name="rank", description="ユーザーランクを確認する")
    @app_commands.describe(user="ユーザーをメンションまたはユーザーIDで指定")
    @ephemeral_check
    @restrict_check
    async def rank(self, ctx: discord.Interaction, user: str = None):
        await ctx.response.defer()

        ephemeral = ctx.extras.get('ephemeral', False)

        if ctx.extras.get('restricted', False):
            await send_error(ctx, None, "このコマンドはサーバー管理者によって実行が制限されています。", None, is_followup=True)
            return

        if user:
            # メンションからID抽出
            target = re.sub("\\D", "", str(user))

            # ユーザーIDからユーザーを取得
            try:
                user = await self.bot.fetch_user(target)

            # できなかったらエラー出す
            except Exception:
                await send_error(ctx, None, "ユーザーを取得できませんでした", None, is_followup=True)
                await self.dbm.log_command(ctx.user.id, "rank", user, ctx.guild.id if ctx.guild else None, result="Failed (Exception)")

        else:
            user = await self.bot.fetch_user(ctx.user.id)
            target = ctx.user.id

        # DBでuser_idが存在するか確認
        async with self.dbm.pool.acquire() as conn:
            result = await conn.fetchrow('SELECT balance, badges, exp, total_login, trust_rank FROM wallet_data WHERE user_id = $1', int(target))

        if result:
            balance = f"{result[0]:,} ZNY"
            badges = result[1]
            exp = result[2]
            total = result[3]
            level = get_level_from_experience(exp)
            next_xp = get_next_level_experience(exp)

            if not badges:
                badges = "なし"

            elif len(badges) == 0:
                badges = "なし"

        else:
            balance = "(ウォレット未開設)"
            badges = "なし"
            exp = 0
            total = 0
            level = 1
            next_xp = get_next_level_experience(exp)

        '''
        if settings_result:
            if settings_result[0] == True:
                spotify_time = settings_result[1]

            else:
                spotify_time = 0

        else:
            spotify_time = 0
        '''

        # Bot判定
        if str(user.discriminator) != "0":
            # Akane判定
            if user.id == 777557090562474044:
                embed = discord.Embed(title="",
                                      description="",
                                      color=discord.Colour.red())
                embed.set_author(name="Moderator✅")
                embed.add_field(name=f"{user.name}#{user.discriminator} [Rank 500]",
                                value="**最大ランク到達**\n**総経験値**: 39,296,362 XP", inline=False)
                embed.add_field(name="エンブレム", value="🛠️🤖", inline=True)
                embed.add_field(name="ステータス", value="このユーザーはシステムBOTです", inline=True)

            else:
                embed = discord.Embed(title="",
                                      description="",
                                      color=0xcccccc)
                embed.set_author(name="New Worker")
                embed.add_field(name=f"{user.name}#{user.discriminator} [Rank 1]",
                                value="**最大ランク到達**\n**総経験値**: 0 XP", inline=False)
                embed.add_field(name="エンブレム", value="🤖", inline=True)
                embed.add_field(name="ステータス", value="このユーザーはBOTです", inline=True)

        else:
            # トラストランク別
            if not result:
                embed = discord.Embed(title="",
                                      description="",
                                      color=0xcccccc)
                embed.set_author(name="New Worker")

            elif result['trust_rank'] == 0:
                embed = discord.Embed(title="",
                                      description="",
                                      color=0xcccccc)
                embed.set_author(name="New Worker")

            elif result['trust_rank'] == 1:
                embed = discord.Embed(title="",
                                      description="",
                                      color=discord.Colour.green())
                embed.set_author(name="Worker")

            elif result['trust_rank'] == 2:
                embed = discord.Embed(title="",
                                      description="",
                                      color=0xff7b42)
                embed.set_author(name="Expert")

            elif result['trust_rank'] == 3:
                embed = discord.Embed(title="",
                                      description="",
                                      color=0xb75638)
                embed.set_author(name="Expert+")

            elif result['trust_rank'] == 4:
                embed = discord.Embed(title="",
                                      description="",
                                      color=0x8143e6)
                embed.set_author(name="Trusted")

            elif result['trust_rank'] == 5:
                embed = discord.Embed(title="",
                                      description="",
                                      color=0x8143e6)
                embed.set_author(name="Trusted✅")

            elif result['trust_rank'] == 6:
                embed = discord.Embed(title="",
                                      description="",
                                      color=discord.Colour.red())
                embed.set_author(name="Moderator✅")

            else:
                embed = discord.Embed(title="",
                                      description="",
                                      color=0xcccccc)
                embed.set_author(name="New Worker")

            if level == 500:
                embed.add_field(name=f"@{user.name} [Rank {level}]",
                                value=f"**最大ランク到達**\n**総経験値**: {exp:,} XP",
                                inline=False)

            else:
                embed.add_field(name=f"@{user.name} [Rank {level}]",
                                value=f"あと **{next_xp:,} XP** で **Rank {min(level + 1, 500)}**\n**総経験値**: {exp:,} XP",
                                inline=False)

            embed.add_field(name="エンブレム", value=badges, inline=True)
            embed.add_field(name="ステータス", value=f"**所持金**: {balance}\n**通算ログイン日数**: {total:,}日", inline=True)

        # アイコンが設定できるならしておく
        if hasattr(user.avatar, 'key'):
            embed.set_thumbnail(url=user.avatar.url)

        await ctx.followup.send(embed=embed, ephemeral=ephemeral)
        await self.dbm.log_command(ctx.user.id, "rank", target, ctx.guild.id if ctx.guild else None, result="Success")

    # give

    @commands.command()
    @commands.is_owner()
    async def give(self, ctx: discord.Interaction, userid: int, val: int):
        # DBでuser_idが存在するか確認
        async with self.dbm.pool.acquire() as conn:
            result = await conn.fetchval('SELECT balance FROM wallet_data WHERE user_id = $1', userid)

        if result:
            new_balance = result + val

            if new_balance < 0:
                new_balance = 0

            async with self.dbm.pool.acquire() as conn:
                async with conn.transaction():
                    try:
                        await conn.execute('''
                                           UPDATE wallet_data
                                           SET balance = $1
                                           WHERE user_id = $2
                                           ''', new_balance, userid)

                    except Exception:
                        await ctx.reply(":x: データベースへの書き込みに失敗しました", mention_author=False)
                        return

            await ctx.reply(f":white_check_mark: `{userid}`に**{val:,} ZNY**与えました", mention_author=False)

        else:
            await ctx.reply(":x: そのユーザーのウォレットは作成されていません", mention_author=False)

    # givexp

    @commands.command()
    @commands.is_owner()
    async def givexp(self, ctx: discord.Interaction, userid: int, val: int):
        # DBでuser_idが存在するか確認
        async with self.dbm.pool.acquire() as conn:
            result = await conn.fetchrow('SELECT exp, level FROM wallet_data WHERE user_id = $1', userid)

        if result:
            new_exp = result[0] + val

            if new_exp < 0:
                new_exp = 0

            level = get_level_from_experience(new_exp)

            async with self.dbm.pool.acquire() as conn:
                async with conn.transaction():
                    try:
                        await conn.execute(
                            '''
                            UPDATE wallet_data
                            SET exp = $1, level = $2
                            WHERE user_id = $3
                            ''',
                            new_exp, level, userid
                            )

                    except Exception:
                        await ctx.reply(":x: データベースへの書き込みに失敗しました", mention_author=False)
                        return

            await ctx.reply(f":white_check_mark: `{userid}`に**{val:,} XP**与えました (Lv.{result[1]}→Lv.{level})", mention_author=False)

        else:
            await ctx.reply(":x: そのユーザーのウォレットは作成されていません", mention_author=False)

    # resetwork

    @commands.command()
    @commands.is_owner()
    async def resetwork(self, ctx: discord.Interaction, userid: int):
        # DBでuser_idが存在するか確認
        async with self.dbm.pool.acquire() as conn:
            result = await conn.fetchval('SELECT last_work FROM wallet_data WHERE user_id = $1', userid)

        if result:
            # 最終workを適当に設定
            last_str = datetime(2000, 1, 1, 0, 0, tzinfo=timezone.utc).replace(tzinfo=None)

            async with self.dbm.pool.acquire() as conn:
                async with conn.transaction():
                    try:
                        await conn.execute('''
                                           UPDATE wallet_data
                                           SET last_work = $1
                                           WHERE user_id = $2
                                           ''', last_str, userid)

                    except Exception:
                        await ctx.reply(":x: データベースへの書き込みに失敗しました", mention_author=False)
                        return

            await ctx.reply(f":white_check_mark: `{userid}`のworkをリセットしました", mention_author=False)

        else:
            await ctx.reply(":x: そのユーザーのウォレットは作成されていません", mention_author=False)

    # resetlogin

    @commands.command()
    @commands.is_owner()
    async def resetlogin(self, ctx: discord.Interaction, userid: int):
        # DBでuser_idが存在するか確認
        async with self.dbm.pool.acquire() as conn:
            result = await conn.fetchval('SELECT last_login FROM wallet_data WHERE user_id = $1', userid)

        if result:
            # 最終workを適当に設定
            last_str = datetime(2000, 1, 1, 0, 0, tzinfo=timezone.utc).replace(tzinfo=None)

            async with self.dbm.pool.acquire() as conn:
                async with conn.transaction():
                    try:
                        await conn.execute('''
                                           UPDATE wallet_data
                                           SET last_login = $1
                                           WHERE user_id = $2
                                           ''', last_str, userid)

                    except Exception:
                        await ctx.reply(":x: データベースへの書き込みに失敗しました", mention_author=False)
                        return

            await ctx.reply(f":white_check_mark: `{userid}`のloginをリセットしました", mention_author=False)

        else:
            await ctx.reply(":x: そのユーザーのウォレットは作成されていません", mention_author=False)

    #########################

    ''' クールダウン '''

    @gift_info.error
    async def gift_info_on_command_error(self, ctx: discord.Interaction, error: app_commands.AppCommandError):
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
    await bot.add_cog(Money(bot))
