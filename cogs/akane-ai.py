# 組み込みライブラリ
import os
import re
import datetime
import io

# 外部ライブラリ
import discord
from discord import app_commands
from discord.ui import Select, View
from discord.ext import commands  # Bot Commands Framework
import aiohttp  # aiohttp
from dotenv import load_dotenv  # python-dotenv
import google.generativeai as genai  # google-generativeai
import simplejson as json  # simplejson
import asyncpg  # asyncpg

# 自作モジュール
from modules.utils import send_error
from modules.decorators import ephemeral_check, restrict_check


load_dotenv()  # .env読み込み

##################################################

''' 定数群 '''

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")  # Gemini API Key

##################################################

''' 初期処理 '''

# Gemini
AIMODEL_NAME = "gemini-2.0-flash"

text_generation_config = {
    "temperature": 0.9,
    "top_p": 1,
    "top_k": 1,
    "max_output_tokens": 512,
}

image_generation_config = {
    "temperature": 0.4,
    "top_p": 1,
    "top_k": 32,
    "max_output_tokens": 512,
}

safety_settings = [
    {
        "category": "HARM_CATEGORY_DANGEROUS",
        "threshold": "BLOCK_NONE",
    },
    {
        "category": "HARM_CATEGORY_HARASSMENT",
        "threshold": "BLOCK_NONE",
    },
    {
        "category": "HARM_CATEGORY_HATE_SPEECH",
        "threshold": "BLOCK_NONE",
    },
    {
        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "threshold": "BLOCK_NONE",
    },
    {
        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
        "threshold": "BLOCK_NONE",
    },
]

# Prompts
CHARACTERS = {
    "akane": ["琴葉茜", "akane.txt"], "aoi": ["琴葉葵", "aoi.txt"], "jinrou": ["人狼（β版）", "jinrou.txt"], 
    "zundamon": ["ずんだもん", "zundamon.txt"], "anagosan": ["アナゴさん", "anagosan.txt"],
    "hiroyuki": ["ひろゆき", "hiroyuki.txt"], "koishi": ["古明地こいし", "koishi.txt"], 
    "bocchi": ["後藤ひとり", "bocchi.txt"], "vegeta": ["ベジータ", "vegeta.txt"],
    "reimu": ["博麗霊夢", "reimu.txt"], "marisa": ["霧雨魔理沙", "marisa.txt"], 
    "yaju": ["野獣先輩", "yaju.txt"], "kurisu": ["牧瀬紅莉栖", "kurisu.txt"],
    "satoshi": ["サトシ", "satoshi.txt"]
}
SYSTEM_PROMPTS = {}

for character_key, (character_name, filename) in CHARACTERS.items():
    with open(f"data/prompts/{filename}", encoding="UTF-8") as f:
        SYSTEM_PROMPTS[character_key] = f.read()

genai.configure(api_key=GOOGLE_API_KEY)

##################################################

''' 関数群 '''


def help_embed(mode):
    '''
    helpコマンドのembed生成

    Parameters:
    ----------
    mode: int
        0: 初回  1: helpコマンド

    Returns:
    ----------
    embed: discord.Embed()
        embedデータ
    '''
    if mode == 1:
        desc = "AIチャットのヘルプメニューです。"

    else:
        desc = "AIチャットのご利用ありがとうございます。"

    embed = discord.Embed(title="Akane AI ヘルプ",
                          description=desc,
                          color=discord.Colour.red())
    embed.add_field(name="機能紹介",
                    value="・AkaneとのAIトーク\n"
                          "・画像認識",
                    inline=False)
    embed.add_field(name="注意事項",
                    value="・AIと会話しない場合は、メッセージの先頭に`::`または`//`を付けてください。\n"
                          "・会話履歴はAkaneと各ユーザー間で保存されます (直近300件まで)。他のユーザーとの会話に割り込むことはできません。\n"
                         f"・会話に不調を感じる場合は、`/ai clear_log`と送信し、会話履歴をリセットしてください。\n"
                          "・現在は一部のサーバーオーナー向けに機能を開放しています。\n"
                          "・Discord規約や公序良俗に反する発言を行ったり、Akaneにそのような発言を促す行為を禁止します。",
                    inline=False)
    embed.add_field(name="コマンド",
                    value="※以下のコマンドはチャットに送信することで使用できます\n"
                         f"`{'/ai help'.ljust(12)}` このヘルプ画面を表示する\n"
                         f"`{'/ai chara'.ljust(12)}` AIのキャラクターを変更する\n"
                         f"`{'/ai clear_log'.ljust(12)}` 会話履歴のリセット\n"
                         f"`{'/ai my_stats'.ljust(12)}` 自分の統計情報の表示\n"
                         f"`{'/ai stats'.ljust(12)}` 統計情報の表示",
                    inline=False)
    embed.set_footer(text="不具合等はサポートサーバーまでご連絡ください")

    return embed


def gemini(text, flag, attachment, chara):
    '''
    Gemini本体処理

    Parameters:
    ----------
    text : str
        入力
    flag : int
        0: text, 1: image
    attachment : all
        flag = 0: history(list), flag = 1: image(image)
    chara : str
        キャラクター

    Returns:
    ----------
    image: image
        完成した画像
    '''
    # テキストモード
    if flag == 0:
        # キャラクター削除に対応したプロンプト設定
        if chara in CHARACTERS:
            prompt = SYSTEM_PROMPTS[chara]

        else:
            prompt = "あなたは優秀なチャットボットです。Userの発言に応答してください。チャットなので、返答はなるべく100字以内でお願いします。lang:ja"

        text_model = genai.GenerativeModel(model_name=AIMODEL_NAME,
                                           safety_settings=safety_settings,
                                           generation_config=text_generation_config,
                                           system_instruction=prompt)
        chat = text_model.start_chat(history=attachment)

        # Geminiにメッセージを投げて返答を待つ。エラーはエラーとして返す。
        try:
            response = chat.send_message(text)

        except Exception as e:
            return [False, e], None

        else:
            # 返答の調整
            # 改行の削除
            formated_response = response.text
            # 正規表現で@everyone、@here、ユーザー宛てメンションを抽出
            pattern = r"(@everyone|@here|<@!?[0-9]+>)"
            formated_response = re.sub(pattern, r"`\1`", formated_response)
            formated_response = re.sub(r'(\n){3,}', '\n', formated_response)
            formated_response = formated_response.splitlines()

            formated_response = [item for item in formated_response if item.strip()]
            
            if len(formated_response) <= 15:
                iofile = None
                final_response = "\n".join(formated_response)

            else:
                final_response = '\n'.join(formated_response[:15])
                remaining_response = "※16行目以降の内容\n\n" + '\n'.join(formated_response[15:])

                iofile = io.StringIO(remaining_response)

            return [True, final_response], iofile

    # 画像モード
    else:
        # キャラクター削除に対応したプロンプト設定
        if chara in CHARACTERS:
            prompt = SYSTEM_PROMPTS[chara]

        else:
            prompt = "あなたは優秀なチャットボットです。Userの発言に応答してください。チャットなので、返答はなるべく100字以内でお願いします。lang:ja"

        image_model = genai.GenerativeModel(model_name=AIMODEL_NAME,
                                            safety_settings=safety_settings,
                                            generation_config=image_generation_config,
                                            system_instruction=prompt)
        image_parts = [{"mime_type": "image/jpeg", "data": attachment}]
        prompt_parts = [image_parts[0], f"\n{text if text else 'この画像は何ですか？'}"]

        # Geminiに画像を投げて返答を待つ。エラーはエラーとして返す。
        try:
            response = image_model.generate_content(prompt_parts)

        except Exception as e:
            return [False, e], None

        else:
            # 返答の調整
            # 改行の削除
            formated_response = response.text
            # 正規表現で@everyone、@here、ユーザー宛てメンションを抽出
            pattern = r"(@everyone|@here|<@!?[0-9]+>)"
            formated_response = re.sub(pattern, r"`\1`", formated_response)
            formated_response = re.sub(r'(\n){3,}', '\n', formated_response[0])
            formated_response = formated_response.splitlines()

            formated_response = [item for item in formated_response if item.strip()]

            if len(formated_response) <= 15:
                iofile = None
                final_response = "\n".join(formated_response)

            else:
                final_response = '\n'.join(formated_response[:15])
                remaining_response = "※16行目以降の内容\n\n" + '\n'.join(formated_response[15:])

                iofile = io.StringIO(remaining_response)

            return [True, final_response], iofile


# キャラクター選択ドロップダウン
class SelectView(View):
    def __init__(self, main_instance, *, timeout: int = 60):
        super().__init__(timeout=timeout)
        self.main = main_instance


    @discord.ui.select(
        cls=Select,
        placeholder="キャラクターを選択",
        disabled=False,
        options=[
            discord.SelectOption(label="キャラクターなし", value="normal", description="通常のチャットボット"),
            discord.SelectOption(label="琴葉茜", value="akane", description="合成音声キャラクター"),
            discord.SelectOption(label="琴葉葵", value="aoi", description="合成音声キャラクター"),
            discord.SelectOption(label="人狼（β版）", value="jinrou", description="人狼ゲーム"),
            discord.SelectOption(label="ずんだもん", value="zundamon", description="ずんずんPJ"),
            discord.SelectOption(label="アナゴさん", value="anagosan", description="サザエさん"),
            discord.SelectOption(label="ひろゆき", value="hiroyuki", description="2ちゃんねるの創設者"),
            discord.SelectOption(label="古明地こいし", value="koishi", description="東方Project"),
            discord.SelectOption(label="後藤ひとり", value="bocchi", description="ぼっち・ざ・ろっく！ [新システム]"),
            discord.SelectOption(label="ベジータ", value="vegeta", description="ドラゴンボール [新システム]"),
            discord.SelectOption(label="博麗霊夢", value="reimu", description="東方Project [新システム]"),
            discord.SelectOption(label="霧雨魔理沙", value="marisa", description="東方Project [新システム]"),
            discord.SelectOption(label="野獣先輩", value="yaju", description="真夏の夜の淫夢 [新システム]"),
            discord.SelectOption(label="牧瀬紅莉栖", value="kurisu", description="STEINS;GATE [新システム]"),
            discord.SelectOption(label="サトシ", value="satoshi", description="ポケットモンスター [新システム]")
        ],
    )
    async def selectMenu(self, ctx: discord.Interaction, select: Select):
        try:
            async with self.main.dbm.pool.acquire() as conn:
                async with conn.transaction():
                    try:
                        await conn.execute('''
                        UPDATE ai_talk_data
                        SET chara = $1, saving_count = $2
                        WHERE user_id = $3
                        ''', select.values[0], 0, ctx.user.id)

                    except Exception:
                        embed = discord.Embed(title="エラー",
                                              description="システムエラーが発生しました。\n"
                                                          "サポートサーバーまでお問い合わせください。\n"
                                                          "エラーコード: 0x00003",
                                              color=discord.Colour.red())
                        button = discord.ui.Button(label="サポートサーバー", style=discord.ButtonStyle.link, url=self.main.bot.SUPPORT_SERVER)
                        view = discord.ui.View()
                        view.add_item(button)
                        return await ctx.message.reply(embed=embed, view=view)

            # キャラクターなしの場合
            if select.values[0] == "normal":
                selected_chara = "キャラクターなし"

            else:
                selected_chara = CHARACTERS[select.values[0]][0]

            select.disabled = True
            #await ctx.response.edit_message(view=self)
            await ctx.response.edit_message(view=SelectView(self.main))
            embed = discord.Embed(title="",
                                  description=f"✅ {ctx.user.mention} のキャラクターを**{selected_chara}**に変更しました",
                                  color=discord.Colour.red())
            return await ctx.message.reply(embed=embed)

        except Exception as e:
            print(e)


##################################################

''' コマンド '''


class Akane_ai(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    # Cog読み込み時
    @commands.Cog.listener()
    async def on_ready(self):
        ##### DB読み込み＆チェック #####
        self.dbm = self.bot.get_cog("DatabaseManager")

        if not self.dbm:
            raise RuntimeError("akane-ai: Database cog is not ready")

        if not await self.dbm.check_db():
            raise RuntimeError("akane-ai: Database is not ready")

        #############################

        print("akane-ai: Ready")

    #########################

    # /aiコマンドをグループ化
    group = app_commands.Group(name="ai", description="Akane AIのコマンド")

    # help
    @group.command(name="help", description="Akane AIのヘルプを表示します")
    @ephemeral_check
    @restrict_check
    async def help(self, ctx: discord.Interaction):
        await ctx.response.defer()
        ephemeral = ctx.extras.get('ephemeral', False)

        if ctx.extras.get('restricted', False):
            await send_error(ctx, None, "このコマンドはサーバー管理者によって実行が制限されています。", None, is_followup=True)
            return

        embed = help_embed(1)
        await ctx.followup.send(embed=embed, ephemeral=ephemeral)

        await self.dbm.log_command(ctx.user.id, "ai help", None, ctx.guild.id if ctx.guild else None, result="Success")

    # my_stats
    @group.command(name="my_stats", description="自分の統計情報を表示する")
    @ephemeral_check
    @restrict_check
    async def my_stats(self, ctx: discord.Interaction):
        await ctx.response.defer()
        ephemeral = ctx.extras.get('ephemeral', False)

        if ctx.extras.get('restricted', False):
            await send_error(ctx, None, "このコマンドはサーバー管理者によって実行が制限されています。", None, is_followup=True)
            return

        async with self.dbm.pool.acquire() as conn:
            data = await conn.fetchrow("""
                SELECT message_count, saving_count, chara, status
                FROM ai_talk_data 
                WHERE user_id = $1
            """, ctx.user.id)

        # アカウント登録済みか
        if data:
            message_count, saving_count, chara, status = data

            if status == "active":
                status_ = "正常"

            elif status == "banned":
                status_ = "利用禁止 (BAN)"
            
            else:
                status_ = "利用不可"

            # キャラクター削除対応
            if chara in CHARACTERS:
                present_chara = CHARACTERS[chara][0]

            else:
                present_chara = "キャラクターなし"

        else:
            message_count = 0
            saving_count = 0
            present_chara = "未設定"
            status_ = "未利用"

        embed = discord.Embed(title=f"Akane AI 統計 (@{ctx.user.name})",
                              description=f"**総会話回数**: {message_count}回\n**保存中の会話履歴**: 直近{saving_count}回\n"
                                          f"**キャラクター**: {present_chara}\n**ステータス**: {status_}",
                              color=discord.Colour.red())
        await ctx.followup.send(embed=embed, ephemeral=ephemeral)

        await self.dbm.log_command(ctx.user.id, "ai my_stats", None, ctx.guild.id if ctx.guild else None, result="Success")


    # clear_log
    @group.command(name="clear_log", description="保存中の会話履歴を全て消去する")
    @ephemeral_check
    @restrict_check
    async def clear_log(self, ctx: discord.Interaction):
        await ctx.response.defer()
        ephemeral = ctx.extras.get('ephemeral', False)

        if ctx.extras.get('restricted', False):
            await send_error(ctx, None, "このコマンドはサーバー管理者によって実行が制限されています。", None, is_followup=True)
            return

        async with self.dbm.pool.acquire() as conn:
            saving_count = await conn.fetchval("""
                SELECT saving_count
                FROM ai_talk_data 
                WHERE user_id = $1
            """, ctx.user.id)

        # アカウント登録済みか
        if saving_count:
            async with self.dbm.pool.acquire() as conn:
                async with conn.transaction():
                    try:
                        await conn.execute('''
                        UPDATE ai_talk_data
                        SET saving_count = $1
                        WHERE user_id = $2
                        ''', 0, ctx.user.id)

                    except Exception as e:
                        await send_error(ctx, "0x00003", None, self.bot.SUPPORT_SERVER, is_followup=True)
                        await self.dbm.log_command(ctx.user.id, "ai clear_log", None, ctx.guild.id if ctx.guild else None, result=f"0x00003 ({e})")
                        return

            embed = discord.Embed(title=f":white_check_mark: 完了",
                                  description="保存中の会話履歴を全て消去しました",
                                  color=discord.Colour.red())
            await ctx.followup.send(embed=embed, ephemeral=ephemeral)

        else:
            await send_error(ctx, None, "あなたはまだ会話を行っていません", None, is_followup=True)

        await self.dbm.log_command(ctx.user.id, "ai clear_log", None, ctx.guild.id if ctx.guild else None, result="Success")


    # chara
    @group.command(name="chara", description="AIのキャラクターを変更する")
    @ephemeral_check
    @restrict_check
    async def chara(self, ctx: discord.Interaction):
        await ctx.response.defer()

        if ctx.extras.get('restricted', False):
            await send_error(ctx, None, "このコマンドはサーバー管理者によって実行が制限されています。", None, is_followup=True)
            return

        async with self.dbm.pool.acquire() as conn:
            chara = await conn.fetchval("""
                SELECT chara
                FROM ai_talk_data
                WHERE user_id = $1
            """, ctx.user.id)

        if chara:
            view = SelectView(self)

            # キャラクター削除対応
            if chara in CHARACTERS:
                present_chara = CHARACTERS[chara][0]

            else:
                present_chara = "キャラクターなし"

            embed = discord.Embed(title=f"キャラクター変更",
                                  description=f"現在のキャラクター: **{present_chara}**\n"
                                               ":warning: キャラクターを変更すると保存中の会話履歴が全て消去されます\n"
                                               "※以下の変更ボタンは60秒でタイムアウトします",
                                  color=discord.Colour.red())
            await ctx.followup.send(embed=embed, view=view, ephemeral=False)

        else:
            await send_error(ctx, None, "あなたはまだ会話を行っていません。\n1回以上会話してから実行してください。", None, is_followup=True)

        await self.dbm.log_command(ctx.user.id, "ai chara", None, ctx.guild.id if ctx.guild else None, result="Success")

    # stats
    @group.command(name="stats", description="Akane AIの統計情報を表示します")
    @ephemeral_check
    @restrict_check
    async def stats(self, ctx: discord.Interaction):
        await ctx.response.defer()
        ephemeral = ctx.extras.get('ephemeral', False)

        if ctx.extras.get('restricted', False):
            await send_error(ctx, None, "このコマンドはサーバー管理者によって実行が制限されています。", None, is_followup=True)
            return

        async with self.dbm.pool.acquire() as conn:
            result = await conn.fetchrow("""
                SELECT COUNT(*) AS total_users, 
                    SUM(message_count) AS total_message_count 
                FROM ai_talk_data
            """)

        if result:
            total_users = result[0]
            total_message_count = result[1] if result[1] is not None else 0  # SUMがNULLの場合は0を設定

            embed = discord.Embed(title="Akane AI 統計情報",
                                  description="", color=discord.Colour.red())
            embed.add_field(name="総会話回数", value=f"{total_message_count:,}回")
            embed.add_field(name="総ユーザー数", value=f"{total_users:,}人")
            embed.add_field(name="AIモデル", value=f"`{AIMODEL_NAME}`")
            embed.set_footer(text=f"Akane v{self.bot.VERSION}")
            await ctx.followup.send(embed=embed, ephemeral=ephemeral)

            await self.dbm.log_command(ctx.user.id, "ai stats", None, ctx.guild.id if ctx.guild else None, result="Success")

        else:
            await send_error(ctx, "0x00101", None, self.bot.SUPPORT_SERVER, is_followup=True)

            await self.dbm.log_command(ctx.user.id, "ai stats", None, ctx.guild.id if ctx.guild else None, result="0x00101")


    # #akane-ai
    @commands.Cog.listener("on_message")
    async def ai_talk(self, message):
        # Bot, 全体メンション, DM, 特定Prefix, コマンドは無視
        try:
            if message.author.bot or message.mention_everyone or \
                    isinstance(message.channel, discord.DMChannel) or \
                    message.content.startswith("::") or message.content.startswith("//"):
                return

            # メイン処理
            elif message.channel.name == "akane-ai":
                async with message.channel.typing():
                    # 画像データかどうか（画像は過去ログ使用不可）
                    if message.attachments:
                        flag = 1

                        for attachment in message.attachments:
                            # 対応していない画像形式なら弾く処理
                            if not any(attachment.filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']):
                                await message.reply(":x: 画像が読み取れません。ファイルを変更してください。\n"
                                                    "対応しているファイル形式: ```.png .jpg .jpeg .gif .webp```",
                                                    mention_author=False)
                                return

                            async with aiohttp.ClientSession() as session:
                                async with session.get(attachment.url) as resp:
                                    if resp.status != 200:
                                        await message.reply(":x: 画像が読み取れません。時間を空けてお試しください。",
                                                            mention_author=False)
                                        return

                                    image_data = await resp.read()

                                    bracket_pattern = re.compile(r'<[^>]+>')
                                    cleaned_text = bracket_pattern.sub('', message.content)

                                    async with self.dbm.pool.acquire() as conn:
                                        try:
                                            chara = await conn.fetchval("""
                                                SELECT chara FROM ai_talk_data WHERE user_id = %1
                                            """, message.author.id)

                                        except Exception:
                                            chara = "akane"

                                    if not chara:
                                        chara = "akane"

                                        async with self.dbm.pool.acquire() as conn:
                                            async with conn.transaction():
                                                try:
                                                    await conn.execute(''' 
                                                        INSERT INTO ai_talk_data (user_id, message_count, saving_count, chara, status)
                                                        VALUES ($1, $2, $3, $4, $5)
                                                    ''', message.author.id, 1, 1, chara, "active")

                                                except Exception:
                                                    await message.reply(":x: システムエラーが発生しました。時間を空けてお試しください。",
                                                            mention_author=False)
                                                    return

                                        embed = help_embed()
                                        await message.reply(embed=embed)

                                    response, iofile = gemini(cleaned_text, 1, image_data, chara)

                    else:
                        # 文章モード (過去データ読み取り)
                        flag = 0

                        async with self.dbm.pool.acquire() as conn:
                            try:
                                result = await conn.fetchrow("""
                                    SELECT chara, saving_count FROM ai_talk_data WHERE user_id = $1
                                """, message.author.id)

                            except Exception as e:
                                import traceback
                                print(traceback.format_exc())
                                result = ["akane", 0]

                        # 会話したことがあるか
                        if result:
                            chara, saving_count = result

                            async with self.dbm.pool.acquire() as conn:
                                async with conn.transaction():
                                    try:
                                        query = """
                                            SELECT message, timestamp
                                            FROM (
                                                SELECT message, timestamp
                                                FROM ai_talk_logs
                                                WHERE user_id = $1
                                                ORDER BY timestamp DESC
                                                LIMIT $2
                                            ) AS recent_logs
                                            ORDER BY timestamp ASC;
                                            """
                                        history_raw = await conn.fetch(query, message.author.id, saving_count)

                                        # 生データから中身を取り出して整形
                                        history = [row['message'] for row in history_raw]
                                        history = [message for json_str in history for message in json.loads(json_str)]

                                    except Exception:
                                        history = []
                            
                            response, iofile = gemini(message.content, 0, history, chara)

                        # 会話が初めてならデータ作成＆インストラクション
                        else:
                            history = []
                            chara = "akane"

                            async with self.dbm.pool.acquire() as conn:
                                async with conn.transaction():
                                    try:
                                        await conn.execute(''' 
                                            INSERT INTO ai_talk_data (user_id, message_count, saving_count, chara, status)
                                            VALUES ($1, $2, $3, $4, $5)
                                        ''', message.author.id, 1, 1, chara, "active")

                                    except Exception:
                                        await message.reply(":x: システムエラーが発生しました。時間を空けてお試しください。",
                                                mention_author=False)
                                        return

                            embed = help_embed(0)
                            await message.reply(embed=embed)
                            response, iofile = gemini(message.content, 0, history, chara)

                    # 正常な返答があれば履歴保存
                    if response and response[0]:
                        # 文章モードのみ履歴保存
                        if len(response[1]) > 0 and flag == 0:
                            talk_data = [{"role": "user", "parts": [message.content]}, {"role": "model", "parts": [response[1]]}]

                            async with self.dbm.pool.acquire() as conn:
                                async with conn.transaction():
                                    try:
                                        await conn.execute(''' 
                                            INSERT INTO ai_talk_logs (user_id, channel_id, guild_id, message, timestamp)
                                            VALUES ($1, $2, $3, $4, $5)
                                        ''', message.author.id, message.channel.id, message.guild.id, json.dumps(talk_data), datetime.datetime.now())
                                        query = """
                                                    UPDATE ai_talk_data
                                                    SET 
                                                        message_count = message_count + 1,
                                                        saving_count = CASE 
                                                            WHEN saving_count < 300 THEN saving_count + 1
                                                            ELSE saving_count
                                                        END
                                                    WHERE user_id = $1;
                                                """
                                        await conn.execute(query, message.author.id)

                                    except Exception as e:
                                        print(e)
                                        pass

                            # 文字数が1000を超えたらカット
                            if len(response) > 1000:
                                response = f"{response[1][:1000]}\n\n※1000文字を超える内容は省略されました※"

                            else:
                                response = response[1]

                            # 31行目からのファイルを添付するか
                            try:
                                if iofile is None:
                                    await message.reply(response, mention_author=False)
                                    return

                                else:
                                    await message.reply(response + "\n\n※16行以上の返答は省略されました",
                                                        file=discord.File(fp=iofile, filename="response.txt"), mention_author=False)
                                    return

                            except Exception as e:
                                print(e)

                        # 画像モード
                        elif len(response[1]) > 0 and flag == 1:
                            # メッセージカウントを増やす
                            async with self.dbm.pool.acquire() as conn:
                                async with conn.transaction():
                                    try:
                                        query = """
                                                    UPDATE ai_talk_data
                                                    SET 
                                                        message_count = message_count + 1,
                                                    WHERE user_id = $1;
                                                """
                                        await conn.execute(query, message.author.id)

                                    except Exception:
                                        pass

                            if len(response) > 1000:
                                response = f"{response[1][:1000]}\n\n※1000文字を超える内容は省略されました※"

                            else:
                                response = response[1]

                            # 31行目からのファイルを添付するか
                            if iofile is None:
                                await message.reply(response, mention_author=False)
                                return

                            else:
                                await message.reply(response + "\n\n※16行以上の返答は省略されました", file=iofile, mention_author=False)
                                return

                    else:
                        # エラーログ出力
                        if str(response[1]).startswith("429"):
                            embed = discord.Embed(title="混雑中",
                                                    description="Akane AIが混雑しています。しばらくお待ちください。",
                                                    color=0xff0000)
                            embed.set_footer(text=f"Report ID: {message.id}")
                            await message.reply(embed=embed, mention_author=False)
                            return

                        elif str(response[1]).startswith("500"):
                            embed = discord.Embed(title="混雑中またはエラー",
                                                    description="サーバーが混雑しているか、内部エラーが発生しています。\n"
                                                                "**30分～1時間程度**時間を空けると完全に解決される場合がありますが、このままご利用いただけます。",
                                                    color=0xff0000)
                            embed.set_footer(text=f"Report ID: {message.id}")
                            await message.reply(embed=embed, mention_author=False)
                            return

                        # 例外エラー
                        else:
                            embed = discord.Embed(title="エラー",
                                                    description="不明なエラーが発生しました。しばらく時間を空けるか、不適切な内容を削除してください。",
                                                    color=0xff0000)
                            embed.set_footer(text=f"Report ID: {message.id}")
                            await message.reply(embed=embed, mention_author=False)
                            return

                        if message.attachments:
                            value = "（画像）"

                        else:
                            value = message.content

                        # エラーを専用チャンネルに投げておく
                        error_log = self.bot.get_channel(self.bot.ERROR_LOG)
                        embed = discord.Embed(title="エラー",
                                            description="AIチャットにてエラーが発生しました。",
                                            timestamp=datetime.datetime.now(),
                                            color=0xff0000)
                        embed.add_field(name="メッセージ内容", value=value)
                        embed.add_field(name="エラー内容", value=response[1])
                        embed.add_field(name="ギルドとチャンネル", value=f"{message.guild.name} (ID: {message.guild.id})\n#{message.channel.id}")
                        embed.add_field(name="ユーザー", value=f"{message.author.mention} (ID: {message.author.id})")
                        embed.set_footer(text=f"Report ID: {message.id}")
                        await error_log.send(embed=embed)
                        return

        except Exception as e:
            import traceback
            print(traceback.format_exc())
            print(e)

    #########################

    # エラー出力
    async def cog_command_error(self, ctx: discord.Interaction, error):
        embed = discord.Embed(title="エラー",
                              description="不明なエラーが発生しました。",
                              color=0xff0000)
        await ctx.reply(embed=embed, mention_author=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(Akane_ai(bot))
