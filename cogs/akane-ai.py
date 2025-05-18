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
from google import genai  # google-generativeai
from google.genai import types
from google.genai.types import Content
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
DEFAULT_MODEL = "gemini-2.0-flash"
DEFAULT_MODEL_NAME = "Gemini 2.0 Flash"
DEFAULT_MODEL_CREDIT = 1

MODELS = {"default": ["Gemini 2.0 Flash", 1, ["user", "vip", "admin"]],
          "gemini-2.5-flash-preview-04-17": ["Gemini 2.5 Flash (Preview 04-17)", 3, ["vip", "admin"]],
          "gemini-2.0-flash-lite": ["Gemini 2.0 Flash-Lite", 1, ["user", "vip", "admin"]],
          "gemini-2.0-flash-preview-image-generation": ["Gemini 2.0 Flesh (Preview 画像生成)", 15, ["vip", "admin"]],
          "gemini-1.5-flash": ["Gemini 1.5 Flash", 3, ["user", "vip", "admin"]],
          "gemini-1.5-flash-8b": ["Gemini 1.5 Flash-8B", 3, ["user", "vip", "admin"]]}

IMAGE_MODELS = ["gemini-2.0-flash-preview-image-generation"]

safety_settings = [
    types.SafetySetting(
        category="HARM_CATEGORY_HARASSMENT",
        threshold="BLOCK_NONE"
        ),
    types.SafetySetting(
        category="HARM_CATEGORY_HATE_SPEECH",
        threshold="BLOCK_NONE"
        ),
    types.SafetySetting(
        category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
        threshold="BLOCK_NONE"
        )]

IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp",
               "image/heic", "image/heif"}

MAX_FILE_SIZE = 15 * 1024 * 1024  # 15MB (バイト)

AI_ROLES = {"user": ["一般", 50], "vip": ["VIP", 350], "admin": ["管理者", 10000]}
AI_STATUS = ["active", "banned"]

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

client = genai.Client(api_key=GOOGLE_API_KEY)

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
                         f"`{'/ai model'.ljust(12)}` AIのモデルを変更する\n"
                         f"`{'/ai clear_log'.ljust(12)}` 現在のキャラクターの会話履歴をリセット\n"
                         f"`{'/ai clear_log_all'.ljust(12)}` 全会話履歴のリセット\n"
                         f"`{'/ai my_stats'.ljust(12)}` 自分の統計情報の表示\n"
                         f"`{'/ai stats'.ljust(12)}` 統計情報の表示",
                    inline=False)
    embed.set_footer(text="不具合等はサポートサーバーまでご連絡ください")

    return embed


def gemini(text, flag, attachment, chara, ai_model):
    '''
    Gemini本体処理

    Parameters:
    ----------
    text : str
        入力
    flag : int
        0: text, 1: image
    attachment : all
        flag = 0: history(list), flag = 1: image(list)
    chara : str
        キャラクター
    ai_model : str
        AIモデル

    Returns:
    ----------
    image: image
        完成した画像
    '''
    # テキストモード
    if flag == 0:
        # 画像出力モデルの場合
        if ai_model in IMAGE_MODELS:
            try:
                response = client.models.generate_content(
                    model=ai_model,
                    contents=[text],
                    config=types.GenerateContentConfig(
                        temperature=1,
                        top_p=0.95,
                        top_k=40,
                        max_output_tokens=8192,
                        response_modalities=["image", "text"],
                        safety_settings=safety_settings,
                        response_mime_type="text/plain",
                    )
                )
                
                
                # レスの取り出し
                parts = response.candidates[0].content.parts
                text = next((part.text for part in parts if part.text), None)
                image = next((part.inline_data for part in parts if part.inline_data), None)

                # 画像があれば取り出しとく
                if image:
                    image_bytes = io.BytesIO(image.data)
                    image_bytes.seek(0)

                else:
                    image_bytes = None

                # 返答の調整
                # 改行の削除
                formated_response = text
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
                    final_response += "\n\n※16行以上の返答は省略されました"

                return [True, final_response], image_bytes, "image"

            except Exception as e:
                return [False, e], None, None

        # キャラクター削除に対応したプロンプト設定
        if chara in CHARACTERS:
            prompt = SYSTEM_PROMPTS[chara]

        elif chara == "all":
            prompt = "過去のUserとの対話記録を全て参照して、Userの発言に応答してください。チャットなので、返答はなるべく100字以内でお願いします。lang:ja"

        else:
            prompt = "あなたは優秀なチャットボットです。Userの発言に応答してください。チャットなので、返答はなるべく100字以内でお願いします。[必ず日本語で応答すること]"

        # AIモデル削除に対応した設定
        if ai_model in MODELS:
            use_model = ai_model
        
        # 今の設定では別にいらんけど一応
        elif ai_model == "default":
            use_model = DEFAULT_MODEL
        
        else:
            use_model = DEFAULT_MODEL

        # システムプロンプトを会話ログの先頭に追加
        attachment.insert(0, {"role": "user", "parts": [{"text": prompt}]})
        attachment.insert(1, {"role": "model", "parts": [{"text": "理解しました"}]})

        chat = client.chats.create(model=use_model,
                                   config=types.GenerateContentConfig(
                                       safety_settings=safety_settings,
                                       temperature=0.9,
                                       top_p=1,
                                       top_k=5,
                                       max_output_tokens=512,
                                       system_instruction=prompt),
                                   history=attachment)

        # Geminiにメッセージを投げて返答を待つ。エラーはエラーとして返す。
        try:
            response = chat.send_message(text)

        except Exception as e:
            return [False, e], None, None

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

            return [True, final_response], iofile, "text"

    # 画像モード
    else:
        # 画像出力モデルの場合
        if ai_model in IMAGE_MODELS:
            try:
                response = client.models.generate_content(
                    model=ai_model,
                    contents=[
                    text,
                    *attachment,
                    ],
                    config=types.GenerateContentConfig(
                        temperature=1,
                        top_p=0.95,
                        top_k=40,
                        max_output_tokens=8192,
                        response_modalities=["image", "text"],
                        safety_settings=safety_settings,
                        response_mime_type="text/plain",
                    )
                )
                
                
                # レスの取り出し
                parts = response.candidates[0].content.parts
                text = next((part.text for part in parts if part.text), None)
                image = next((part.inline_data for part in parts if part.inline_data), None)

                # 画像があれば取り出しとく
                if image:
                    image_bytes = io.BytesIO(image.data)
                    image_bytes.seek(0)

                else:
                    image_bytes = None

                # 返答の調整
                # 改行の削除
                formated_response = text
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
                    final_response += "\n\n※16行以上の返答は省略されました"

                return [True, final_response], image_bytes, "image"

            except Exception as e:
                return [False, e], None, None

        # キャラクター削除に対応したプロンプト設定
        if chara in CHARACTERS:
            prompt = SYSTEM_PROMPTS[chara]

        elif chara == "all":
            prompt = "過去のUserとの対話記録を全て参照して、Userの発言に応答してください。チャットなので、返答はなるべく100字以内でお願いします。lang:ja"

        else:
            prompt = "あなたは優秀なチャットボットです。Userの発言に応答してください。チャットなので、返答はなるべく100字以内でお願いします。lang:ja"

        # AIモデル削除に対応した設定
        if ai_model in MODELS:
            use_model = ai_model
        
        # 今の設定では別にいらんけど一応
        elif ai_model == "default":
            use_model = DEFAULT_MODEL
        
        else:
            use_model = DEFAULT_MODEL

        # Geminiに画像を投げて返答を待つ。エラーはエラーとして返す。
        try:
            response = client.models.generate_content(
                model=use_model,
                contents=[
                    text,
                    *attachment,
                ],
                config=types.GenerateContentConfig(
                    safety_settings=safety_settings,
                    temperature=0.4,
                    top_p=1,
                    top_k=32,
                    max_output_tokens=512,
                    system_instruction=prompt)
            )

        except Exception as e:
            return [False, e], None, None

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

            return [True, final_response], iofile, "text"


# キャラクター選択ドロップダウン
class SelectView(View):
    def __init__(self, main_instance, author: discord.User, *, timeout: int = 300):
        super().__init__(timeout=timeout)
        self.main = main_instance
        self.author = author


    @discord.ui.select(
        cls=Select,
        placeholder="キャラクターを選択",
        disabled=False,
        options=[
            discord.SelectOption(label="キャラクターなし", value="normal", description="通常のチャットボット"),
            discord.SelectOption(label="全ての会話ログ", value="all", description="全キャラクターとの会話ログを読みこむ"),
            discord.SelectOption(label="琴葉茜", value="akane", description="合成音声キャラクター"),
            discord.SelectOption(label="琴葉葵", value="aoi", description="合成音声キャラクター"),
            discord.SelectOption(label="人狼（β版）", value="jinrou", description="人狼ゲーム"),
            discord.SelectOption(label="ずんだもん", value="zundamon", description="ずんずんPJ"),
            discord.SelectOption(label="アナゴさん", value="anagosan", description="サザエさん"),
            discord.SelectOption(label="ひろゆき", value="hiroyuki", description="2ちゃんねる"),
            discord.SelectOption(label="古明地こいし", value="koishi", description="東方Project"),
            discord.SelectOption(label="後藤ひとり", value="bocchi", description="ぼっち・ざ・ろっく！ [新システム]"),
            discord.SelectOption(label="ベジータ", value="vegeta", description="ドラゴンボール [新システム]"),
            discord.SelectOption(label="博麗霊夢", value="reimu", description="東方Project [新システム]"),
            discord.SelectOption(label="霧雨魔理沙", value="marisa", description="東方Project [新システム]"),
            discord.SelectOption(label="野獣先輩", value="yaju", description="淫夢ファミリー [新システム]"),
            discord.SelectOption(label="牧瀬紅莉栖", value="kurisu", description="STEINS;GATE [新システム]"),
            discord.SelectOption(label="サトシ", value="satoshi", description="ポケットモンスター [新システム]")
        ],
    )
    async def selectMenu(self, ctx: discord.Interaction, select: Select):
        if ctx.user.id != self.author.id:
            embed = discord.Embed(title="エラー",
                                  description="コマンド実行者以外は使用できません",
                                  color=discord.Colour.red())
            await ctx.response.send_message(embed=embed, ephemeral=True)
            return

        try:
            async with self.main.dbm.pool.acquire() as conn:
                async with conn.transaction():
                    try:
                        await conn.execute('''
                        UPDATE ai_talk_data
                        SET chara = $1
                        WHERE user_id = $2
                        ''', select.values[0], ctx.user.id)

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

            # 「全て」の場合
            elif select.values[0] == "all":
                selected_chara = "全ての会話ログ"

            else:
                selected_chara = CHARACTERS[select.values[0]][0]

            select.disabled = True
            embed = discord.Embed(title="",
                                  description=f"✅ キャラクターを**{selected_chara}**に変更しました",
                                  color=discord.Colour.red())
            await ctx.response.edit_message(embed=embed, view=None)
            return

        except Exception as e:
            print(e)


# モデル選択ドロップダウン
class ModelSelectView(View):
    def __init__(self, main_instance, author: discord.User, *, timeout: int = 300):
        super().__init__(timeout=timeout)
        self.main = main_instance
        self.author = author

    @discord.ui.select(
        cls=Select,
        placeholder="AIモデルを選択",
        disabled=False,
        options=[
            discord.SelectOption(label="Gemini 2.0 Flash", value="default", description="通常の会話向け (デフォルト) [1クレジット]"),
            discord.SelectOption(label="Gemini 2.5 Flash (Preview 04-17)", value="gemini-2.5-flash-preview-04-17", description="高性能、高レート制限 (VIP限定) [3クレジット]"),
            discord.SelectOption(label="Gemini 2.0 Flash (Preview 画像生成)", value="gemini-2.0-flash-preview-image-generation", description="画像生成、高レート制限 (VIP限定) [15クレジット]"),
            discord.SelectOption(label="Gemini 2.0 Flash-Lite", value="gemini-2.0-flash-lite", description="やや軽量 [3クレジット]"),
            discord.SelectOption(label="Gemini 1.5 Flash", value="gemini-1.5-flash", description="以前のバージョン [3クレジット]"),
            discord.SelectOption(label="Gemini 1.5 Flash-8B", value="gemini-1.5-flash-8b", description="低知能タスク向け [3クレジット]")
        ],
    )
    async def selectMenu(self, ctx: discord.Interaction, select: Select):
        if ctx.user.id != self.author.id:
            embed = discord.Embed(title="エラー",
                                  description="コマンド実行者以外は使用できません",
                                  color=discord.Colour.red())
            await ctx.response.send_message(embed=embed, ephemeral=True)
            return

        model_permission = MODELS[select.values[0]][2]

        try:
            async with self.main.dbm.pool.acquire() as conn:
                role = await conn.fetchval("""
                        SELECT role
                        FROM ai_talk_data 
                        WHERE user_id = $1
                    """, ctx.user.id)
                
                # 権限不足
                if not role in model_permission:
                    embed = discord.Embed(title="エラー",
                                          description="このモデルを使用する権限がありません。\n別のモデルをお試し下さい。\n※以下のボタンは5分でタイムアウトします",
                                          color=discord.Colour.red())
                    await ctx.response.edit_message(embed=embed, view=ModelSelectView(self.main, author=ctx.user))
                    return
                
                async with conn.transaction():
                    try:
                        await conn.execute('''
                        UPDATE ai_talk_data
                        SET ai_model = $1
                        WHERE user_id = $2
                        ''', select.values[0], ctx.user.id)

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

            # モデル名取得
            selected_model = MODELS[select.values[0]][0]

            select.disabled = True
            embed = discord.Embed(title="",
                                  description=f"✅ AIモデルを**{selected_model}**に変更しました",
                                  color=discord.Colour.red())
            await ctx.response.edit_message(embed=embed, view=None)
            return

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
                SELECT message_count, saving_count, chara, status, ai_model, role, credit
                FROM ai_talk_data 
                WHERE user_id = $1
            """, ctx.user.id)

        # アカウント登録済みか
        if data:
            message_count, saving_count, chara, status, ai_model, role, credit = data

            saving_count = json.loads(saving_count)

            if status == "active":
                status_ = "正常"

            elif status == "banned":
                status_ = "利用禁止 (BAN)"
            
            else:
                status_ = "利用不可"

            # キャラクター削除対応
            if chara in CHARACTERS:
                present_chara = CHARACTERS[chara][0]

            elif chara == "all":
                present_chara = "全会話ログ"

            else:
                present_chara = "キャラクターなし"

            # AIモデル削除対応
            if ai_model in MODELS:
                present_model = MODELS[ai_model][0]
                model_credit = MODELS[ai_model][1]
                model_name = f"`{present_model}` (費用: {model_credit}クレジット)"

            elif ai_model == "default":
                present_model = DEFAULT_MODEL_NAME
                model_credit = MODELS[ai_model][1]
                model_name = f"`{present_model}` (費用: {model_credit}クレジット)"

            else:
                model_name = "不明"

            # クレジット
            if role in AI_ROLES:
                plan = AI_ROLES[role][0]
                max_credit = AI_ROLES[role][1]

            else:
                plan = "不明"
                max_credit = "--"

        else:
            message_count = 0
            saving_count = {"all" :0, "akane": 0}
            present_chara = "未設定"
            plan = "なし"
            status_ = "未利用"
            credit = 0
            max_credit = 0

        embed = discord.Embed(title=f"Akane AI 統計 (@{ctx.user.name})",
                              description=f"**総会話回数**: {message_count:,}回\n"
                                          f"**キャラクター**: {present_chara}\n"
                                          f"**保存中の会話履歴**: 直近{saving_count.get(chara, 0):,}回"
                                          f" (全キャラ: {saving_count.get("all", 0):,}回)\n\n"
                                          f"**AIモデル**: {model_name}\n"
                                          f"**プラン**: {plan} (状態: {status_})\n"
                                          f"**クレジット**: {credit}/{max_credit}\n",
                              color=discord.Colour.red())
        await ctx.followup.send(embed=embed, ephemeral=ephemeral)

        await self.dbm.log_command(ctx.user.id, "ai my_stats", None, ctx.guild.id if ctx.guild else None, result="Success")


    # clear_log
    @group.command(name="clear_log", description="現在のキャラクターとの会話履歴を消去する")
    @ephemeral_check
    @restrict_check
    async def clear_log(self, ctx: discord.Interaction):
        await ctx.response.defer()
        ephemeral = ctx.extras.get('ephemeral', False)

        if ctx.extras.get('restricted', False):
            await send_error(ctx, None, "このコマンドはサーバー管理者によって実行が制限されています。", None, is_followup=True)
            return

        async with self.dbm.pool.acquire() as conn:
            result = await conn.fetch("""
                SELECT saving_count, chara
                FROM ai_talk_data 
                WHERE user_id = $1
            """, ctx.user.id)

        # 取り出し
        record = result[0]
        saving_count = json.loads(record["saving_count"])
        chara = record["chara"]

        # アカウント登録済みか
        if saving_count:
            saving_count[chara] = 0

            async with self.dbm.pool.acquire() as conn:
                async with conn.transaction():
                    try:
                        await conn.execute('''
                        UPDATE ai_talk_data
                        SET saving_count = $1
                        WHERE user_id = $2
                        ''', json.dumps(saving_count), ctx.user.id)

                    except Exception as e:
                        await send_error(ctx, "0x00003", None, self.bot.SUPPORT_SERVER, is_followup=True)
                        await self.dbm.log_command(ctx.user.id, "ai clear_log", None, ctx.guild.id if ctx.guild else None, result=f"0x00003 ({e})")
                        return

            embed = discord.Embed(title=f":white_check_mark: 完了",
                                  description=f"`{CHARACTERS[chara][0]}`との会話履歴を消去しました",
                                  color=discord.Colour.red())
            await ctx.followup.send(embed=embed, ephemeral=ephemeral)

        else:
            await send_error(ctx, None, "あなたはまだ会話を行っていません", None, is_followup=True)

        await self.dbm.log_command(ctx.user.id, "ai clear_log", None, ctx.guild.id if ctx.guild else None, result="Success")


    # clear_log_all
    @group.command(name="clear_log_all", description="AIとの会話履歴を全て消去する")
    @ephemeral_check
    @restrict_check
    async def clear_log_all(self, ctx: discord.Interaction):
        await ctx.response.defer()
        ephemeral = ctx.extras.get('ephemeral', False)

        if ctx.extras.get('restricted', False):
            await send_error(ctx, None, "このコマンドはサーバー管理者によって実行が制限されています。", None, is_followup=True)
            return

        async with self.dbm.pool.acquire() as conn:
            saving_count, chara = await conn.fetchval("""
                SELECT saving_count, chara
                FROM ai_talk_data 
                WHERE user_id = $1
            """, ctx.user.id)

        # アカウント登録済みか
        if saving_count:
            saving_count = {"all": 0, "akane": 0}

            async with self.dbm.pool.acquire() as conn:
                async with conn.transaction():
                    try:
                        await conn.execute('''
                        UPDATE ai_talk_data
                        SET saving_count = $1
                        WHERE user_id = $2
                        ''', json.dumps(saving_count), ctx.user.id)

                    except Exception as e:
                        await send_error(ctx, "0x00003", None, self.bot.SUPPORT_SERVER, is_followup=True)
                        await self.dbm.log_command(ctx.user.id, "ai clear_log_all", None, ctx.guild.id if ctx.guild else None, result=f"0x00003 ({e})")
                        return

            embed = discord.Embed(title=f":white_check_mark: 完了",
                                  description=f"`{CHARACTERS[chara][0]}`との会話履歴を消去しました",
                                  color=discord.Colour.red())
            await ctx.followup.send(embed=embed, ephemeral=ephemeral)

        else:
            await send_error(ctx, None, "あなたはまだ会話を行っていません", None, is_followup=True)

        await self.dbm.log_command(ctx.user.id, "ai clear_log_all", None, ctx.guild.id if ctx.guild else None, result="Success")


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
            view = SelectView(self, author=ctx.user)

            # キャラクター削除対応
            if chara in CHARACTERS:
                present_chara = CHARACTERS[chara][0]

            else:
                present_chara = "キャラクターなし"

            embed = discord.Embed(title=f"キャラクター変更",
                                  description=f"現在のキャラクター: **{present_chara}**\n"
                                               "※以下の変更ボタンは5分でタイムアウトします",
                                  color=discord.Colour.red())
            await ctx.followup.send(embed=embed, view=view, ephemeral=False)

        else:
            await send_error(ctx, None, "あなたはまだ会話を行っていません。\n1回以上会話してから実行してください。", None, is_followup=True)

        await self.dbm.log_command(ctx.user.id, "ai chara", None, ctx.guild.id if ctx.guild else None, result="Success")

    # model
    @group.command(name="model", description="AIモデルを変更する")
    @ephemeral_check
    @restrict_check
    async def model(self, ctx: discord.Interaction):
        await ctx.response.defer()

        if ctx.extras.get('restricted', False):
            await send_error(ctx, None, "このコマンドはサーバー管理者によって実行が制限されています。", None, is_followup=True)
            return

        async with self.dbm.pool.acquire() as conn:
            ai_model = await conn.fetchval("""
                SELECT ai_model
                FROM ai_talk_data
                WHERE user_id = $1
            """, ctx.user.id)

        if ai_model:
            view = ModelSelectView(self, author=ctx.user)

            # モデル削除対応
            if ai_model in MODELS:
                present_model = MODELS[ai_model][0]

            else:
                present_model = DEFAULT_MODEL_NAME

            embed = discord.Embed(title=f"AIモデル変更",
                                  description=f"現在のモデル: **{present_model}**\n"
                                               "※以下の変更ボタンは5分でタイムアウトします",
                                  color=discord.Colour.red())
            await ctx.followup.send(embed=embed, view=view, ephemeral=False)

        else:
            await send_error(ctx, None, "あなたはまだ会話を行っていません。\n1回以上会話してから実行してください。", None, is_followup=True)

        await self.dbm.log_command(ctx.user.id, "ai model", None, ctx.guild.id if ctx.guild else None, result="Success")

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
        if message.author.bot or message.mention_everyone or \
            isinstance(message.channel, discord.DMChannel) or \
            message.content.startswith("::") or message.content.startswith("//"):
            return

        # メイン処理
        if message.channel.name == "akane-ai":
            try:
                async with message.channel.typing():
                    # 添付ファイルの処理
                    image_parts = []

                    async with aiohttp.ClientSession() as session:
                        for attachment in message.attachments:
                            if attachment.content_type in IMAGE_TYPES:
                                async with session.get(attachment.url) as resp:
                                    if resp.status == 200:
                                        img_bytes = await resp.read()

                                        part = types.Part.from_bytes(
                                            data=img_bytes,
                                            mime_type=attachment.content_type  # よーわからん
                                        )
                                        image_parts.append(part)

                                        # とりあえず最大4枚まで
                                        if len(image_parts) >= 4:
                                            break
                    
                    # 画像があるとき
                    if image_parts:
                        # キャラクター設定取得
                        async with self.dbm.pool.acquire() as conn:
                            try:
                                result = await conn.fetchrow("""
                                            SELECT chara, saving_count, status, ai_model, role, credit, last_message FROM ai_talk_data WHERE user_id = $1
                                        """, message.author.id)

                            except Exception as e:
                                import traceback
                                print(traceback.format_exc())
                                result = ["akane", json.loads({"all": 0, "akane": 0}), DEFAULT_MODEL, "user", 0, datetime.datetime.now()]

                        # 会話歴あり
                        if result:
                            chara, saving_count, status, ai_model, role, credit, last_message = result
                            saving_count = json.loads(saving_count)

                            # BANされてるか
                            if status == "banned":
                                try:
                                    await message.add_reaction("❌")

                                except Exception:
                                    pass

                                return

                            # 日付チェックしてクレジット補給後、クレジットが足りるか確認
                            today = datetime.datetime.now().date()

                            if last_message.date() < today:
                                credit = AI_ROLES[role][1]

                            credit_per = MODELS[ai_model][1]

                            if credit - credit_per < 0:
                                try:
                                    await message.add_reaction("💸")

                                except Exception:
                                    pass

                                return
                            
                            if ai_model == "default":
                                ai_model = DEFAULT_MODEL

                        else:
                            # 会話が初めてならデータ作成＆説明
                            history = []
                            chara = "akane"
                            saving_count = json.loads({"all": 1, "akane": 1})

                            async with self.dbm.pool.acquire() as conn:
                                async with conn.transaction():
                                    try:
                                        await conn.execute(''' 
                                            INSERT INTO ai_talk_data (user_id, message_count, saving_count, chara, status, ai_model, role, credit, last_message)
                                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, now())
                                        ''', message.author.id, 1, json.dumps(saving_count), chara, "active", "default", "user", max(AI_ROLES["user"] - credit_per["default"][1], 0))

                                    except Exception:
                                        await message.reply(":x: システムエラーが発生しました。時間を空けてお試しください。",
                                                mention_author=False)
                                        return

                            embed = help_embed(0)
                            await message.reply(embed=embed)

                        # メッセージが空か
                        if len(message.content) == 0:
                            content = "この画像は何ですか？軽く説明と感想を述べてください。"

                        else:
                            content = message.content

                        # 今は画像4枚までしか投げられない
                        mode = "image"
                        response, iofile, file_type = gemini(content, 1, image_parts, chara, ai_model)

                    # 画像がない (テキスト) or 読み込めない場合
                    else:
                        if len(message.content) == 0:
                            return

                        # 会話ログ取得
                        async with self.dbm.pool.acquire() as conn:
                            try:
                                result = await conn.fetchrow("""
                                    SELECT chara, saving_count, status, ai_model, role, credit, last_message FROM ai_talk_data WHERE user_id = $1
                                """, message.author.id)

                            except Exception as e:
                                import traceback
                                print(traceback.format_exc())
                                result = ["akane", json.loads({"all": 0, "akane": 0}), DEFAULT_MODEL, "user", 0, datetime.datetime.now()]

                        # 会話歴あり
                        if result:
                            chara, saving_count, status, ai_model, role, credit, last_message = result
                            saving_count = json.loads(saving_count)
                            history = []

                            # BANされてるか
                            if status == "banned":
                                try:
                                    await message.add_reaction("❌")

                                except Exception:
                                    pass

                                return

                            # 日付チェックしてクレジット補給後、クレジットが足りるか確認
                            today = datetime.datetime.now().date()

                            if last_message.date() < today:
                                credit = AI_ROLES[role][1]

                            credit_per = MODELS[ai_model][1]

                            if credit - credit_per < 0:
                                try:
                                    await message.add_reaction("💸")

                                except Exception:
                                    pass

                                return
                            
                            if ai_model == "default":
                                ai_model = DEFAULT_MODEL

                            async with self.dbm.pool.acquire() as conn:
                                try:
                                    query = """
                                        SELECT message, timestamp
                                        FROM (
                                            SELECT message, timestamp
                                            FROM ai_talk_logs
                                            WHERE user_id = $1 AND chara = $2
                                            ORDER BY timestamp DESC
                                            LIMIT $3
                                        ) AS recent_logs
                                        ORDER BY timestamp ASC;
                                        """
                                    history_raw = await conn.fetch(query, message.author.id, chara, saving_count.get(chara, 0))

                                    # 生データから中身を取り出して整形
                                    history = [row['message'] for row in history_raw]
                                    history = [message for json_str in history for message in json.loads(json_str)]

                                except Exception:
                                    history = []

                        # 会話が初めてならデータ作成＆説明
                        else:
                            history = []
                            chara = "akane"
                            saving_count = json.loads({"all": 1, "akane": 1})

                            async with self.dbm.pool.acquire() as conn:
                                async with conn.transaction():
                                    try:
                                        await conn.execute(''' 
                                            INSERT INTO ai_talk_data (user_id, message_count, saving_count, chara, status, ai_model, role, credit, last_message)
                                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, now())
                                        ''', message.author.id, 1, json.dumps(saving_count), chara, "active", "default", "user", max(AI_ROLES["user"] - credit_per["default"][1], 0))

                                    except Exception:
                                        await message.reply(":x: システムエラーが発生しました。時間を空けてお試しください。",
                                                mention_author=False)
                                        return

                            embed = help_embed(0)
                            await message.reply(embed=embed)

                        content = message.content
                        
                        # Geminiにデータ投げる
                        mode = "text"
                        response, iofile, file_type = gemini(content, 0, history, chara, ai_model)

                # 正常な返答があれば履歴保存
                if response and response[0]:
                    # 履歴保存
                    if len(response[1]) > 0:
                        talk_data = [{"role": "user", "parts": [{"text": content}]}, {"role": "model", "parts": [{"text": response[1]}]}]
                        
                        # (画像モードのときはスキップしておく)
                        if mode == "text":
                            # ログ保存数が300件未満か
                            if saving_count.get(chara, 0) < 300:
                                saving_count.setdefault(chara, 0)
                                saving_count[chara] += 1

                            if saving_count.get("all", 0) < 300:
                                saving_count.setdefault("all", 0)
                                saving_count["all"] += 1

                        # クレジット消費 (0にならない対策)
                        credit = max(credit - credit_per, 0)

                        async with self.dbm.pool.acquire() as conn:
                            async with conn.transaction():
                                try:
                                    await conn.execute(''' 
                                        INSERT INTO ai_talk_logs (user_id, channel_id, guild_id, message, chara, timestamp)
                                        VALUES ($1, $2, $3, $4, $5, $6)
                                    ''', message.author.id, message.channel.id, message.guild.id, json.dumps(talk_data), chara, datetime.datetime.now())
                                    query = """
                                                UPDATE ai_talk_data
                                                SET 
                                                    message_count = message_count + 1,
                                                    saving_count = $2,
                                                    credit = $3,
                                                    last_message = now()
                                                WHERE user_id = $1;
                                            """
                                    await conn.execute(query, message.author.id, json.dumps(saving_count), credit)

                                except Exception as e:
                                    print(f"{e} ERROR")
                                    pass

                        # 文字数が1000を超えたらカット
                        if len(response[1]) > 1000:
                            response = f"{response[1][:1000]}\n\n※1,000文字を超える内容は省略されました※"

                        else:
                            response = response[1]

                        # 31行目からのファイル or 画像を添付するか
                        try:
                            if iofile is None:
                                await message.reply(response, mention_author=False)
                                return

                            else:
                                if file_type == "text":
                                    await message.reply(response + "\n\n※16行以上の返答は省略されました",
                                                        file=discord.File(fp=iofile, filename="response.txt"), mention_author=False)
                                    return
                                
                                elif file_type == "image":
                                    await message.reply(response,
                                                        file=discord.File(fp=iofile, filename="image.png"), mention_author=False)
                                    return

                        except Exception as e:
                            print(e)

                else:
                    # エラーログ出力
                    if str(response[1]).startswith("429"):
                        embed = discord.Embed(title="混雑中",
                                            description="Akane AIが混雑しています。しばらくお待ちください。",
                                            color=0xff0000)
                        embed.set_footer(text=f"Report ID: {message.id}")
                        await message.reply(embed=embed, mention_author=False)

                    elif str(response[1]).startswith("500"):
                        embed = discord.Embed(title="混雑中またはエラー",
                                            description="サーバーが混雑しているか、内部エラーが発生しています。\n"
                                                        "**30分～1時間程度**時間を空けると完全に解決される場合がありますが、このままご利用いただけます。",
                                            color=0xff0000)
                        embed.set_footer(text=f"Report ID: {message.id}")
                        await message.reply(embed=embed, mention_author=False)

                    # 例外エラー
                    else:
                        embed = discord.Embed(title="エラー",
                                            description="不明なエラーが発生しました。しばらく時間を空けるか、不適切な内容を削除してください。",
                                            color=0xff0000)
                        embed.set_footer(text=f"Report ID: {message.id}")
                        await message.reply(embed=embed, mention_author=False)

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

        else:
            return
        

    # ai_refill

    @commands.command()
    @commands.is_owner()
    async def ai_refill(self, ctx: discord.Interaction, userid: int):
        # DBでuser_idが存在するか確認
        async with self.dbm.pool.acquire() as conn:
            result = await conn.fetchrow('SELECT credit, role FROM ai_talk_data WHERE user_id = $1', userid)

        if result:
            credit, role = result
            new_credit = AI_ROLES[role][1]

            async with self.dbm.pool.acquire() as conn:
                async with conn.transaction():
                    try:
                        await conn.execute('''
                                           UPDATE ai_talk_data
                                           SET credit = $1
                                           WHERE user_id = $2
                                           ''', new_credit, userid)

                    except Exception as e:
                        await ctx.reply(":x: データベースへの書き込みに失敗しました", mention_author=False)
                        return

            await ctx.reply(f":white_check_mark: `{userid}`のクレジットを補充しました", mention_author=False)

        else:
            await ctx.reply(":x: そのユーザーのデータは作成されていません", mention_author=False)

    # ai_role

    @commands.command()
    @commands.is_owner()
    async def ai_role(self, ctx: discord.Interaction, userid: int, role: str):
        if not role in AI_ROLES.keys():
            await ctx.reply(":x: そのロールは存在しません", mention_author=False)
            return

        # DBでuser_idが存在するか確認
        async with self.dbm.pool.acquire() as conn:
            result = await conn.fetchval('SELECT role FROM ai_talk_data WHERE user_id = $1', userid)

        if result:
            new_role = role.lower()
            new_credit = AI_ROLES[new_role][1]

            async with self.dbm.pool.acquire() as conn:
                async with conn.transaction():
                    try:
                        await conn.execute('''
                                           UPDATE ai_talk_data
                                           SET credit = $1, role = $2
                                           WHERE user_id = $3
                                           ''', new_credit, new_role, userid)

                    except Exception as e:
                        await ctx.reply(":x: データベースへの書き込みに失敗しました", mention_author=False)
                        return

            await ctx.reply(f':white_check_mark: `{userid}`のロールを`{AI_ROLES[new_role][0]} ("{new_role}")`に変更しました', mention_author=False)

        else:
            await ctx.reply(":x: そのユーザーのデータは作成されていません", mention_author=False)

    # ai_status

    @commands.command()
    @commands.is_owner()
    async def ai_status(self, ctx: discord.Interaction, userid: int, status: str):
        if not status in AI_STATUS.keys():
            await ctx.reply(":x: そのステータスは存在しません", mention_author=False)
            return

        # DBでuser_idが存在するか確認
        async with self.dbm.pool.acquire() as conn:
            result = await conn.fetchval('SELECT status FROM ai_talk_data WHERE user_id = $1', userid)

        if result:
            new_status = status.lower()

            async with self.dbm.pool.acquire() as conn:
                async with conn.transaction():
                    try:
                        await conn.execute('''
                                           UPDATE ai_talk_data
                                           SET status = $1
                                           WHERE user_id = $2
                                           ''', new_status, userid)

                    except Exception as e:
                        await ctx.reply(":x: データベースへの書き込みに失敗しました", mention_author=False)
                        return

            await ctx.reply(f':white_check_mark: `{userid}`のステータスを`{new_status}`に変更しました', mention_author=False)

        else:
            await ctx.reply(":x: そのユーザーのデータは作成されていません", mention_author=False)

    #########################

    # エラー出力
    async def cog_command_error(self, ctx: discord.Interaction, error):
        embed = discord.Embed(title="エラー",
                              description="不明なエラーが発生しました。",
                              color=0xff0000)
        await ctx.reply(embed=embed, mention_author=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(Akane_ai(bot))
