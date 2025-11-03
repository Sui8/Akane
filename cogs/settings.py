# 組み込みライブラリ
import traceback

# 外部ライブラリ
import discord
from discord import app_commands
from discord.ext import commands  # Bot Commands Framework
import simplejson as json

# 自作モジュール
from modules.utils import send_error
from modules.decorators import ephemeral_check


##################################################

class RestrictView(discord.ui.View):
    def __init__(self, bot, author_id, restricted_commands, all_commands, guild_id, dbm):
        super().__init__(timeout=300)
        self.bot = bot
        self.author_id = author_id
        self.dbm = dbm
        self.guild_id = guild_id
        self.restricted_commands = restricted_commands
        self.message = None  # メッセージを保存するための変数
        self.all_commands = list(set(all_commands))  # 重複防止
        self.all_commands = []
        self.all_commands = sorted(set(all_commands))  # 昇順ソート
        self.page = 0
        self.per_page = 25

        self.clear_items()
        self.dropdown = self.create_dropdown()
        self.add_item(self.dropdown)
        self.add_pagination_buttons()
        self.add_bulk_buttons()

    # ボタンがクリックされたときに実行されるコールバック関数
    async def button_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            embed = discord.Embed(title=":x: エラー",
                                  description="このメニューはコマンド実行者のみ操作できます。",
                                  color=0xff0000)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if interaction.data["custom_id"] == "prev_page":
            try:
                if self.page > 0:
                    self.page -= 1
                    await self.update_dropdown(interaction)

            except Exception:
                print("[ERROR] 前のページに移動エラー")
                traceback.print_exc()
                await interaction.response.send_message(":x: エラーが発生しました。\nサポートサーバーまでお問い合わせください。", ephemeral=True)

        elif interaction.data["custom_id"] == "next_page":
            try:
                if (self.page + 1) * self.per_page < len(self.all_commands):
                    self.page += 1
                    await self.update_dropdown(interaction)

            except Exception:
                print("[ERROR] 次のページに移動エラー")
                traceback.print_exc()
                await interaction.response.send_message(":x: エラーが発生しました。\nサポートサーバーまでお問い合わせください。", ephemeral=True)

        elif interaction.data["custom_id"] == "restrict_all":
            try:
                self.restricted_commands = set(self.all_commands)
                async with self.dbm.pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE guild_settings SET restricted_commands = $1 WHERE guild_id = $2",
                        json.dumps(list(self.restricted_commands)), self.guild_id
                    )
                await self.update_dropdown(interaction)

            except Exception:
                print("[ERROR] 一括制限エラー")
                traceback.print_exc()
                await interaction.response.send_message(":x: エラーが発生しました。\nサポートサーバーまでお問い合わせください。", ephemeral=True)

        elif interaction.data["custom_id"] == "unrestrict_all":
            try:
                self.restricted_commands = set()
                async with self.dbm.pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE guild_settings SET restricted_commands = $1 WHERE guild_id = $2",
                        json.dumps({}), self.guild_id
                    )
                await self.update_dropdown(interaction)

            except Exception:
                print("[ERROR] 一括解除エラー")
                traceback.print_exc()
                await interaction.response.send_message(":x: エラーが発生しました。\nサポートサーバーまでお問い合わせください。", ephemeral=True)

    def add_pagination_buttons(self):
        """ページ切り替えボタンを追加"""
        prev_button = discord.ui.Button(emoji="◀️", style=discord.ButtonStyle.blurple, custom_id="prev_page")
        next_button = discord.ui.Button(emoji="▶️", style=discord.ButtonStyle.blurple, custom_id="next_page")

        prev_button.callback = self.button_callback
        next_button.callback = self.button_callback

        # 最初のページなら「前へ」ボタンを無効化
        if self.page == 0:
            prev_button.disabled = True

        # 最後のページなら「次へ」ボタンを無効化
        if (self.page + 1) * self.per_page >= len(self.all_commands):
            next_button.disabled = True

        self.add_item(prev_button)
        self.add_item(next_button)

    def add_bulk_buttons(self):
        """一括制限・解除ボタンを追加"""
        button = discord.ui.Button(label="全て制限", style=discord.ButtonStyle.danger, custom_id="restrict_all")
        button.callback = self.button_callback
        self.add_item(button)

        button = discord.ui.Button(label="全て解除", style=discord.ButtonStyle.success, custom_id="unrestrict_all")
        button.callback = self.button_callback
        self.add_item(button)

    def update_ui(self):
        """UIを更新"""
        self.clear_items()
        self.dropdown = self.create_dropdown()
        self.add_item(self.dropdown)
        self.add_pagination_buttons()
        self.add_bulk_buttons()

    def create_dropdown(self):
        """現在のページのコマンドを含むドロップダウンを作成"""
        start = self.page * self.per_page
        end = start + self.per_page
        commands_on_page = self.all_commands[start:end]

        dropdown = discord.ui.Select(
            placeholder=f"コマンドを選択 ({self.page + 1}/{(len(self.all_commands) - 1) // self.per_page + 1})",
            options=[
                discord.SelectOption(
                    label=cmd,
                    value=cmd,
                    default=(cmd in self.restricted_commands)  # 選択状態を保持
                )
                for cmd in commands_on_page
            ],
            min_values=0,
            max_values=len(commands_on_page),
        )
        dropdown.callback = self.select_callback  # コールバック関数を設定
        return dropdown

    async def select_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            embed = discord.Embed(title=":x: エラー",
                                  description="このメニューはコマンド実行者のみ操作できます。",
                                  color=0xff0000)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        """ドロップダウンでコマンドを選択したときの処理"""
        try:
            selected_commands = set(self.dropdown.values)

            # 既存の制限リストを更新（現在のページのコマンドのみ変更）
            start = self.page * self.per_page
            end = start + self.per_page
            commands_on_page = set(self.all_commands[start:end])

            # ページ内の選択状態を更新し、それ以外は維持する
            self.restricted_commands = (self.restricted_commands - commands_on_page) | selected_commands

            # データベースを更新
            restricted_commands_json = json.dumps(list(self.restricted_commands))
            async with self.dbm.pool.acquire() as conn:
                await conn.execute(
                    "UPDATE guild_settings SET restricted_commands = $1 WHERE guild_id = $2",
                    restricted_commands_json, self.guild_id
                )

            await interaction.response.edit_message(embed=self.get_embed(), view=self)

        except Exception:
            print("[ERROR] ドロップダウン選択エラー")
            traceback.print_exc()
            await interaction.response.send_message(":x: エラーが発生しました。\nサポートサーバーまでお問い合わせください。", ephemeral=True)

    async def update_dropdown(self, interaction):
        """ドロップダウンの更新"""
        try:
            async with self.dbm.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT restricted_commands FROM guild_settings WHERE guild_id = $1",
                    self.guild_id
                )
                self.restricted_commands = set(json.loads(row["restricted_commands"]) if row else [])

            self.update_ui()
            await interaction.response.edit_message(embed=self.get_embed(), view=self)

        except Exception:
            print("[ERROR] ドロップダウン更新エラー")
            traceback.print_exc()
            await interaction.response.send_message(":x: エラーが発生しました。\nサポートサーバーまでお問い合わせください。", ephemeral=True)

    def get_embed(self):
        """現在の制限状況をEmbedで表示"""
        embed = discord.Embed(title="コマンド実行制限", color=discord.Color.green())

        if self.restricted_commands:
            sorted_commands = sorted(self.restricted_commands)
            embed.add_field(name=f"制限中のコマンド ({len(sorted_commands)})", value=", ".join(sorted_commands), inline=False)

        else:
            embed.add_field(name="制限中のコマンド (0)", value="なし", inline=False)

        return embed

    def set_message(self, message: discord.Message):
        """メッセージをセットするためのメソッド"""
        self.message = message

    async def on_timeout(self):
        """タイムアウト時に全てのボタンとドロップダウンを無効化"""
        for item in self.children:
            item.disabled = True  # UIコンポーネントを無効化

        try:
            if self.message:
                await self.message.edit(view=self)  # UIを無効化して更新

            else:
                print("OMG")

        except Exception:
            print("[ERROR] タイムアウト時のUI更新エラー")
            traceback.print_exc()

##################################################


''' コマンド '''


class Settings(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.cache = {}  # キャッシュを使ってDBアクセスを減らす

    # Cog読み込み時
    @commands.Cog.listener()
    async def on_ready(self):
        # ---- DB読み込み＆チェック ----
        self.dbm = self.bot.get_cog("DatabaseManager")

        if not self.dbm:
            raise RuntimeError("setting: Database cog is not ready")

        if not await self.dbm.check_db():
            raise RuntimeError("setting: Database is not ready")

        #############################

        print("setting: Ready")

    #########################

    async def fetch_restricted_commands(self, guild_id: int):
        """DBから制限コマンド一覧を取得"""
        try:
            async with self.dbm.pool.acquire() as conn:
                row = await conn.fetchrow("SELECT restricted_commands FROM guild_settings WHERE guild_id = $1", guild_id)

                if row and row["restricted_commands"]:
                    # JSON文字列をリストに変換
                    return set(json.loads(row["restricted_commands"]))

                if not row:
                    await conn.execute(
                        "INSERT INTO guild_settings (guild_id, language, timezone, restricted_commands) VALUES ($1, $2, $3, $4)",
                        guild_id, None, None, json.dumps([]))

                return set()

        except Exception:
            print("[ERROR] データベース取得エラー")
            traceback.print_exc()
            return set()

    #############################

    # /settingsコマンドをグループ化
    group = app_commands.Group(name="setting", description="ユーザー設定コマンド")

    # info

    @group.command(name="info", description="Akaneの個人設定、サーバー設定（管理者のみ）を表示します")
    @ephemeral_check
    async def info(self, ctx: discord.Interaction):
        await ctx.response.defer()

        ephemeral = ctx.extras.get('ephemeral', False)

        # DBでuser_idが存在するか確認
        async with self.dbm.pool.acquire() as conn:
            result = await conn.fetchrow(
                """
                SELECT language, timezone, ephemeral, spotify_time, game_time
                FROM user_settings WHERE user_id = $1
                """,
                ctx.user.id
                )

        if not result:
            # 未設定の場合初期値を与えておく
            result = ["未設定", "未設定", False, False, False]

        description = f"言語: **{result[0] or '未設定'}**\n" \
            + f"タイムゾーン: **{result[1] or '未設定'}**\n" \
            + f"コマンド出力を非公開(一部非対応): **{'有効' if result[2] else '無効'}**\n" \
            + f"Spotifyの再生時間を記録: **{'有効' if result[3] else '無効'}**\n" \
            + f"ゲームのプレイ時間を記録: **{'有効' if result[4] else '無効'}**\n"

        embed = discord.Embed(title="設定情報",
                              description="",
                              color=discord.Colour.green())

        embed.add_field(name="個人設定", value=description, inline=False)

        # サーバーでの実行かつ管理者なら
        if ctx.guild and ctx.user.guild_permissions.administrator:
            # DBでguild_idが存在するか確認
            async with self.dbm.pool.acquire() as conn:
                guild_result = await conn.fetchrow('SELECT language, timezone FROM guild_settings WHERE guild_id = $1', ctx.guild.id)

            if not guild_result:
                # 未設定の場合初期値を与えておく
                guild_result = ["未設定", "未設定"]

            guild_description = f"言語: **{guild_result[0]}**\n" \
                + f"タイムゾーン: **{guild_result[1]}**\n" \
                + "※個人設定がある場合はそちらが優先されます\n" \
                + "※コマンドの実行制限は`/setting command`で行えます"

            embed.add_field(name="サーバー設定", value=guild_description, inline=False)

        await ctx.followup.send(embed=embed, ephemeral=ephemeral)
        await self.dbm.log_command(ctx.user.id, "setting info", None, ctx.guild.id if ctx.guild else None, result="Success")

    # command

    @group.command(name="command", description="コマンドの実行制限を設定します")
    @ephemeral_check
    async def command(self, ctx: discord.Interaction):
        try:
            await ctx.response.defer()

            # ephemeral = ctx.extras.get('ephemeral', False)

            # サーバーでの実行かつ管理者ではないなら
            if not (ctx.guild and ctx.user.guild_permissions.administrator):
                await send_error(ctx, None, "サーバーで実行していないか、あなたの権限が不足しています。\n管理者ユーザーから実行してください。", None, is_followup=True)
                await self.dbm.log_command(ctx.user.id, "setting command", None, ctx.guild.id if ctx.guild else None, result="Failed (Mistake)")
                return

            guild_id = ctx.guild.id
            restricted_commands = await self.fetch_restricted_commands(guild_id)
            all_commands = [cmd.name for cmd in self.bot.tree.walk_commands()]
            view = RestrictView(self.bot, ctx.user.id, restricted_commands, all_commands, guild_id, self.dbm)
            message = await ctx.followup.send(embed=view.get_embed(), view=view, ephemeral=True)
            view.set_message(message)

        except Exception as e:
            import traceback
            print(traceback.format_exc())
            print(e)

    # reset

    @group.command(name="reset", description="全ての設定をリセットします")
    async def reset(self, ctx: discord.Interaction):
        await ctx.response.defer()

        # DBでuser_idが存在するか確認
        async with self.dbm.pool.acquire() as conn:
            result = await conn.fetchrow('SELECT ephemeral, spotify_time FROM user_settings WHERE user_id = $1', ctx.user.id)

        # 設定があるときは削除する
        if result:
            async with self.dbm.pool.acquire() as conn:
                async with conn.transaction():
                    try:
                        await conn.execute("DELETE FROM user_settings WHERE user_id = $1", ctx.user.id)

                    except Exception as e:
                        await send_error(ctx, "0x00003", None, self.bot.SUPPORT_SERVER, is_followup=True)
                        await self.dbm.log_command(ctx.user.id, "setting reset", None, ctx.guild.id if ctx.guild else None, result=f"0x00003 ({e})")
                        return

        async with self.dbm.pool.acquire() as conn:
            async with conn.transaction():
                try:
                    await conn.execute(
                        """
                        INSERT INTO user_settings (
                            user_id, language, timezone,
                            ephemeral, spotify_time, spotify_total_time,
                            game_time)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                        """,
                        ctx.user.id, "", 0, False, False, 0, False
                        )

                except Exception as e:
                    await send_error(ctx, "0x00003", None, self.bot.SUPPORT_SERVER, is_followup=True)
                    await self.dbm.log_command(ctx.user.id, "setting reset", None, ctx.guild.id if ctx.guild else None, result=f"0x00003 ({e})")
                    return

        embed = discord.Embed(title=":white_check_mark: 完了",
                              description="全ての設定をリセットしました",
                              color=discord.Colour.green())

        await ctx.followup.send(embed=embed, ephemeral=False)
        await self.dbm.log_command(ctx.user.id, "setting reset", None, ctx.guild.id if ctx.guild else None, result="Success")

    # toggle_feature

    @group.command(name="toggle_feature", description="設定の有効/無効を切り替えます")
    @app_commands.describe(feature="設定を切り替える項目")
    @app_commands.describe(status="状態")
    @app_commands.choices(feature=[
        app_commands.Choice(name="コマンド出力を非公開", value="ephemeral"),])
    @app_commands.choices(status=[
        app_commands.Choice(name="有効", value="True"),
        app_commands.Choice(name="無効", value="False"),])
    @ephemeral_check
    async def toggle_feature(self, ctx: discord.Interaction, feature: app_commands.Choice[str], status: app_commands.Choice[str] = None):
        try:
            await ctx.response.defer()

            # ephemeral = ctx.extras.get('ephemeral', False)

            # DBでuser_idが存在するか確認
            async with self.dbm.pool.acquire() as conn:
                result = await conn.fetchrow('SELECT ephemeral, spotify_time FROM user_settings WHERE user_id = $1', ctx.user.id)

            # 設定がない時は作成する
            if not result:
                async with self.dbm.pool.acquire() as conn:
                    async with conn.transaction():
                        try:
                            await conn.execute(
                                """
                                INSERT INTO user_settings (
                                    user_id, language, timezone,
                                    ephemeral, spotify_time, spotify_total_time,
                                    game_time
                                    )
                                VALUES ($1, $2, $3, $4, $5, $6, $7)
                                """,
                                ctx.user.id, "", 0, False, False, 0, False
                                )

                        except Exception as e:
                            await send_error(ctx, "0x00003", None, self.bot.SUPPORT_SERVER, is_followup=True)
                            await self.dbm.log_command(
                                ctx.user.id, "setting toggle_feature", [feature.value, str(status)],
                                ctx.guild.id if ctx.guild else None, result=f"0x00003 ({e})"
                                )
                            return

                result = [False, False]

            # statusが指定されていればそれを、されていなければトグルにする
            if status:
                if status.value == "True":
                    setting = True

                else:
                    setting = False

            else:
                features = ["ephemeral", "spotify_time"]

                if result[features.index(feature.value)]:
                    setting = False

                else:
                    setting = True

            async with self.dbm.pool.acquire() as conn:
                async with conn.transaction():
                    try:
                        await conn.execute(f'''
                                            UPDATE user_settings
                                            SET {feature.value} = $1
                                            WHERE user_id = $2
                                            ''', setting, ctx.user.id)

                    except Exception as e:
                        await send_error(ctx, "0x00003", None, self.bot.SUPPORT_SERVER, is_followup=True)
                        await self.dbm.log_command(
                            ctx.user.id, "setting toggle_feature", [feature.value, str(status)],
                            ctx.guild.id if ctx.guild else None, result=f"0x00003 ({e})"
                            )
                        return

            embed = discord.Embed(title=":white_check_mark: 設定完了",
                                  description=f"【{feature.name}】を**{'有効' if setting else '無効'}**に設定しました",
                                  color=discord.Colour.green())

            await ctx.followup.send(embed=embed, ephemeral=setting)
            await self.dbm.log_command(
                ctx.user.id, "setting toggle_feature", [feature.value, str(status)],
                ctx.guild.id if ctx.guild else None, result="Success"
                )

        except Exception as e:
            import traceback
            print(traceback.format_exc())
            print(e)

    ##################################################


async def setup(bot: commands.Bot):
    await bot.add_cog(Settings(bot))
