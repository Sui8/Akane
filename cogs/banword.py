# 組み込みライブラリ
import time

# 外部ライブラリ
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv  # python-dotenv
# import simplejson as json  # simplejson

# 自作モジュール
from modules.utils import send_error
from modules.decorators import ephemeral_check


load_dotenv()  # .env読み込み

##################################################


class BanListView(discord.ui.View):
    def __init__(self, cog, ctx, words, page, per=15, timeout=3600):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.words = words
        self.page = page
        self.per = per

    def make_embed(self):
        total = len(self.words)
        pages = (len(self.words) + self.per - 1) // self.per
        start = (self.page-1) * self.per
        chunk = self.words[start:start+self.per]
        desc = "\n".join(f"・`{w}`" for w in chunk)
        embed = discord.Embed(title="警告ワードリスト",
                              description=desc,
                              color=discord.Colour.yellow())
        embed.set_footer(text=f"ページ {self.page} / {pages} (全 {total:,} ワード)")
        return embed

    async def update(self):
        await self.ctx.edit_original_response(embed=self.make_embed(), view=self)

    @discord.ui.button(label="◀", style=discord.ButtonStyle.primary)
    async def prev(self, ctx: discord.Interaction, button: discord.ui.Button):
        if ctx.user.id != self.ctx.user.id:
            embed = discord.Embed(title=":x: エラー",
                                  description="コマンド実行者のみ操作できます",
                                  color=0xff0000)
            return await ctx.response.send_message(embed=embed, ephemeral=True)

        self.page = max(1, self.page-1)
        await ctx.response.defer()
        await self.update()

    @discord.ui.button(label="▶", style=discord.ButtonStyle.primary)
    async def next(self, ctx: discord.Interaction, button: discord.ui.Button):
        if ctx.user.id != self.ctx.user.id:
            embed = discord.Embed(title=":x: エラー",
                                  description="コマンド実行者のみ操作できます",
                                  color=0xff0000)
            return await ctx.response.send_message(embed=embed, ephemeral=True)

        pages = (len(self.words) + self.per - 1) // self.per
        self.page = min(pages, self.page+1)
        await ctx.response.defer()
        await self.update()

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True

        try:
            await self.ctx.edit_original_response(view=self)

        except Exception:
            pass


class BanReplyModal(discord.ui.Modal, title="警告メッセージ設定"):
    title_input = discord.ui.TextInput(
        label="タイトル",
        style=discord.TextStyle.short,
        max_length=100,
        required=False
    )
    body_input = discord.ui.TextInput(
        label="本文",
        style=discord.TextStyle.paragraph,
        max_length=600,
        required=True
    )
    reset_input = discord.ui.TextInput(
        label="警告メッセージを初期化",
        style=discord.TextStyle.short,
        max_length=1,
        required=False,
        placeholder="初期化する場合は【y】と入力"
    )

    def __init__(self, cog, guild_id):
        super().__init__()
        self.cog = cog
        self.guild_id = guild_id

    async def on_submit(self, ctx: discord.Interaction):
        await ctx.response.defer()

        # デフォにもどす
        if self.reset_input.value.lower() == "y":
            # DBから削除
            async with self.cog.dbm.pool.acquire() as conn:
                async with conn.transaction():
                    try:
                        # reply
                        await conn.execute(
                            "DELETE FROM banword_replies WHERE guild_id=$1",
                            self.guild_id
                        )

                    except Exception as e:
                        await send_error(ctx, "0x00003", None, self.bot.SUPPORT_SERVER, is_followup=True)
                        await self.cog.dbm.log_command(
                            ctx.user.id, "banword message", None,
                            ctx.guild.id if ctx.guild else None, result=f"0x00003 ({e})")
                        return

            # cacheも削除
            self.cog.reply_cache.pop(self.guild_id, None)

            embed = discord.Embed(title=":white_check_mark: 成功",
                                  description="警告メッセージを初期化しました",
                                  color=discord.Colour.green())
            return await ctx.followup.send(embed=embed, ephemeral=True)

        # DB更新
        async with self.cog.dbm.pool.acquire() as conn:
            async with conn.transaction():
                try:
                    # reply
                    await conn.execute(
                        "INSERT INTO banword_replies (guild_id, title, body) VALUES ($1, $2, $3) "
                        "ON CONFLICT(guild_id) DO UPDATE SET title=excluded.title, body=excluded.body",
                        self.guild_id, self.title_input.value, self.body_input.value
                    )

                except Exception as e:
                    await send_error(ctx, "0x00003", None, self.bot.SUPPORT_SERVER, is_followup=True)
                    await self.cog.dbm.log_command(
                        ctx.user.id, "banword message", None,
                        ctx.guild.id if ctx.guild else None, result=f"0x00003 ({e})")
                    return

        # cacheも更新
        self.cog.reply_cache[self.guild_id] = {
            "title": self.title_input.value,
            "body": self.body_input.value
        }

        embed = discord.Embed(title=":white_check_mark: 成功",
                              description="警告メッセージを更新しました",
                              color=discord.Colour.green())
        await ctx.followup.send(embed=embed, ephemeral=True)

##################################################


class BanWord(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.cache: dict[int, set[str]] = {}
        self.reply_cache: dict[int, dict[str, str]] = {}
        self.recent_responses: dict[tuple[int, str], float] = {}

    # Cog読み込み時
    @commands.Cog.listener()
    async def on_ready(self):
        # ---- DB読み込み＆チェック ----
        self.dbm = self.bot.get_cog("DatabaseManager")

        if not self.dbm:
            raise RuntimeError("banword: Database cog is not ready")

        if not await self.dbm.check_db():
            raise RuntimeError("banword: Database is not ready")

        #############################

        print("banword: Ready")

        self.bot.loop.create_task(self._async_load_all())  # DBの都合で仕方なくasyncにした

    async def _async_load_all(self):
        # DB
        async with self.dbm.pool.acquire() as conn:
            banwords = await conn.fetch("SELECT guild_id, word FROM banwords")
            banword_replies = await conn.fetch("SELECT guild_id, title, body FROM banword_replies")

        for gid, w in banwords:
            gid = int(gid)
            self.cache.setdefault(gid, set()).add(w)

        for gid, title, body in banword_replies:
            gid = int(gid)
            self.reply_cache[gid] = {"title": title, "body": body}

    #########################

    # /banwordコマンドをグループ化
    group = app_commands.Group(name="banword", description="警告ワードのコマンド")

    # banword検知
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        gid = message.guild.id

        if gid not in self.cache:
            return

        found = None

        for i in self.cache[gid]:
            if str(i) in str(message.content):  # 上手く検知されにくい
                found = i
                break

        if not found:
            return

        now = time.time()
        key = (gid, found)

        # こっちが連投するの防止 (10秒クールダウン)
        # if key in self.recent_responses and now - self.recent_responses[key] < 10:
        #     return

        self.recent_responses[key] = now

        # reply設定
        data = self.reply_cache.get(gid)

        if data:
            embed = discord.Embed(title=data["title"], description=data["body"], color=0xff0000)

        else:
            embed = discord.Embed(
                title=":warning: サーバー管理者より警告",
                description="このメッセージには不適切なワードが含まれています。",
                color=0xff0000
            )

        await message.reply(embed=embed, mention_author=False)

    # add
    @group.command(name="add", description="警告ワードを追加")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    @app_commands.describe(word="追加するワード")
    @ephemeral_check
    async def add(self, ctx: discord.Interaction, word: app_commands.Range[str, 1, 200]):
        await ctx.response.defer()

        ephemeral = ctx.extras.get('ephemeral', False)

        gid = ctx.guild_id

        # 重複チェック (DB側にも設定は入れてある)
        if gid in self.cache:
            if word in self.cache[gid]:
                await send_error(ctx, None, "そのワードは既に登録されています", None, is_followup=True)
                return

        else:
            self.cache[gid] = set()  # cache初期化 (エラー対策でif分けてる)

        # とりあえず各鯖 500 words まで
        if len(self.cache[gid]) >= 500:
            await send_error(
                ctx, None,
                "ワード数の登録上限 (500) に達しました。\n`/banword remove`で他のワードを削除してください。",
                None, is_followup=True
                )
            return

        self.cache[gid].add(word)

        # DB登録
        async with self.dbm.pool.acquire() as conn:
            async with conn.transaction():
                try:
                    # reply
                    await conn.execute("INSERT INTO banwords (guild_id, word) VALUES ($1, $2)", gid, word)

                except Exception as e:
                    await send_error(ctx, "0x00003", None, self.bot.SUPPORT_SERVER, is_followup=True)
                    await self.dbm.log_command(
                        ctx.user.id, "banword add", None,
                        ctx.guild.id if ctx.guild else None, result=f"0x00003 ({e})")
                    return

        embed = discord.Embed(title=":white_check_mark: 成功",
                              description="警告ワードリストに登録しました",
                              color=discord.Colour.green())
        await ctx.followup.send(embed=embed, ephemeral=ephemeral)
        await self.dbm.log_command(ctx.user.id, "banword add", [gid, word],
                                   ctx.guild.id if ctx.guild else None, result="Success")

    # remove
    @group.command(name="remove", description="警告ワードを削除")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    @app_commands.describe(word="削除するワード")
    @ephemeral_check
    async def remove(self, ctx: discord.Interaction, word: app_commands.Range[str, 1, 200]):
        await ctx.response.defer()

        ephemeral = ctx.extras.get('ephemeral', False)

        gid = ctx.guild_id

        if gid not in self.cache:
            await send_error(ctx, None, "そのワードは登録されていません", None, is_followup=True)
            return

        if word not in self.cache[gid]:
            await send_error(ctx, None, "そのワードは登録されていません", None, is_followup=True)
            return

        self.cache[gid].remove(word)

        # DBから削除
        async with self.dbm.pool.acquire() as conn:
            async with conn.transaction():
                try:
                    # reply
                    await conn.execute("DELETE FROM banwords WHERE guild_id=$1 AND word=$2", gid, word)

                except Exception as e:
                    await send_error(ctx, "0x00003", None, self.bot.SUPPORT_SERVER, is_followup=True)
                    await self.dbm.log_command(
                        ctx.user.id, "banword remove", None,
                        ctx.guild.id if ctx.guild else None, result=f"0x00003 ({e})")
                    return

        embed = discord.Embed(title=":white_check_mark: 成功",
                              description="警告ワードリストから削除しました",
                              color=discord.Colour.green())
        await ctx.followup.send(embed=embed, ephemeral=ephemeral)
        await self.dbm.log_command(ctx.user.id, "banword remove", [gid, word],
                                   ctx.guild.id if ctx.guild else None, result="Success")

    # clear
    @group.command(name="clear", description="警告ワードをすべて削除")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    @ephemeral_check
    async def clear(self, ctx: discord.Interaction):
        await ctx.response.defer()

        ephemeral = ctx.extras.get('ephemeral', False)

        gid = ctx.guild_id

        # cache側
        self.cache[gid] = set()

        # DB側も削除
        async with self.dbm.pool.acquire() as conn:
            async with conn.transaction():
                try:
                    # reply
                    await conn.execute("DELETE FROM banwords WHERE guild_id=$1", gid)

                except Exception as e:
                    await send_error(ctx, "0x00003", None, self.bot.SUPPORT_SERVER, is_followup=True)
                    await self.dbm.log_command(
                        ctx.user.id, "banword clear", None,
                        ctx.guild.id if ctx.guild else None, result=f"0x00003 ({e})")
                    return

        embed = discord.Embed(title=":white_check_mark: 成功",
                              description="警告ワードをすべて削除しました",
                              color=discord.Colour.green())
        await ctx.followup.send(embed=embed, ephemeral=ephemeral)
        await self.dbm.log_command(ctx.user.id, "banword clear", None,
                                   ctx.guild.id if ctx.guild else None, result="Success")

    # list
    @group.command(name="list", description="警告ワードリストを表示")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def list(self, ctx: discord.Interaction):
        await ctx.response.defer()

        gid = ctx.guild_id
        words = sorted(list(self.cache.get(gid, [])))

        if not words:
            embed = discord.Embed(title="警告ワードリスト",
                                  description="登録されているワードはありません",
                                  color=discord.Colour.yellow())
            # embed.set_footer(text="＊同じ警告ワードの検知は10秒間行われません")
            return await ctx.followup.send(embed=embed, ephemeral=False)

        view = BanListView(self, ctx, words, page=1)
        await ctx.followup.send(embed=view.make_embed(), view=view, ephemeral=False)

    # message
    @group.command(name="message", description="警告ワードへの返信文を設定")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def message(self, ctx: discord.Interaction):
        await ctx.response.send_modal(BanReplyModal(self, ctx.guild_id))


async def setup(bot: commands.Bot):
    await bot.add_cog(BanWord(bot))
