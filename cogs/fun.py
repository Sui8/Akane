# 組み込みライブラリ
import random

# 外部ライブラリ
import discord
from discord import app_commands
from discord.ext import commands  # Bot Commands Framework

# 自作モジュール
from modules.utils import send_error
from modules.decorators import ephemeral_check, restrict_check


##################################################

''' コマンド '''


class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Cog読み込み時
    @commands.Cog.listener()
    async def on_ready(self):
        ##### DB読み込み＆チェック #####
        self.dbm = self.bot.get_cog("DatabaseManager")

        if not self.dbm:
            raise RuntimeError("fun: Database cog is not ready")

        if not await self.dbm.check_db():
            raise RuntimeError("fun: Database is not ready")

        #############################

        print("fun: Ready")

    #########################

    # cat
    @app_commands.command(name="cat", description="ﾈｺﾁｬﾝ")
    @ephemeral_check
    @restrict_check
    async def cat(self, ctx: discord.Interaction):
        await ctx.response.defer()
        ephemeral = ctx.extras.get('ephemeral', False)
        
        if ctx.extras.get('restricted', False):
            await send_error(ctx, None, "このコマンドはサーバー管理者によって実行が制限されています。", None, is_followup=True)
            return

        nekos = ["🐱( '-' 🐱 )ﾈｺﾁｬﾝ", "ﾆｬﾝฅ(>ω< )ฅﾆｬﾝ♪",
                 "ฅ•ω•ฅﾆｬﾆｬｰﾝ✧", "ฅ( ̳• ·̫ • ̳ฅ)にゃあ",
                 "ﾆｬｯ(ฅ•ω•ฅ)", "ฅ•ω•ฅにぁ？",
                 "( ฅ•ω•)ฅ ﾆｬｰ!", "ฅ(´ω` ฅ)ﾆｬｰ",
                 "(/・ω・)/にゃー!",
                 "(*´ω｀*ฅ)ﾆｬｰ", "ฅ^•ω•^ฅﾆｬｰ",
                 "(/ ･ω･)/にゃー", "└('ω')┘ﾆｬｱｱｱｱｱｱｱｱｱｱ!!!!",
                 "(/・ω・)/にゃー！", "ฅ•ω•ฅﾆｬｰ",
                 "壁]ωФ)ﾆｬｰ", "ฅ(=･ω･=)ฅﾆｬｰ",
                 "(*ΦωΦ)ﾆｬｰ", "にゃーヽ(•̀ω•́ )ゝ✧",
                 "ฅ•ω•ฅﾆｬｰ♥♡", "ﾆｬｰ(/｡>ω< )/",
                 "(」・ω・)」うー！(／・ω・)／にゃー！",
                 "ฅฅ*)ｲﾅｲｲﾅｲ･･･ ฅ(^ •ω•*^ฅ♡ﾆｬｰ",
                 "ﾆｬｰ(´ฅ•ω•ฅ｀)ﾆｬｰ", "ฅ(･ω･ฅ)ﾝﾆｬｰ♡",
                 "ﾆｬｰ(ฅ *`꒳´ * )ฅ", "ฅ(^ •ω•*^ฅ♡ﾆｬｰ",
                 "๑•̀ㅁ•́ฅ✧にゃ!!", "ﾆｬｯ(ฅ•ω•ฅ)♡",
                 "ฅ^•ﻌ•^ฅﾆｬｰ", "ฅ( *`꒳´ * ฅ)ﾆｬｰ",
                 "ฅ(๑•̀ω•́๑)ฅﾆｬﾝﾆｬﾝ!", "ฅ(・ω・)ฅにゃー💛",
                 "ฅ(○•ω•○)ฅﾆｬ～ﾝ♡", "Σฅ(´ω｀；ฅ)ﾆｬｰ!?",
                 "ฅ(*´ω｀*ฅ)ﾆｬｰ", "ﾆｬ-( ฅ•ω•)( •ω•ฅ)ﾆｬｰ",
                 "ฅ(^ •ω•*^ฅ♡ﾆｬｰ", "ฅ•ω•ฅﾆｬﾆｬｰﾝ✧ｼｬｰ ฅ(`ꈊ´ฅ)",
                 "ﾆｬﾝฅ(>ω< )ฅﾆｬﾝ♪", "ฅ( ̳• ·̫ • ̳ฅ)にゃあ",
                 "ฅ(*°ω°*ฅ)*ﾆｬｰｵ", "ฅ•ω•ฅにぁ？", "♪(ฅ•∀•)ฅ ﾆｬﾝ",
                 "ฅ(◍ •̀ω• ́◍)ฅﾆｬﾝﾆｬﾝがお➰🌟", "=͟͟͞͞(๑•̀ㅁ•́ฅ✧ﾆｬｯ",
                 "ฅ(=✧ω✧=)ฅﾆｬﾆｬｰﾝ✧", "ﾆｬｰ(ฅ *`꒳´ * )ฅฅ( *`꒳´ * ฅ)ﾆｬｰ",
                 "ฅ(๑•̀ω•́๑)ฅﾆｬﾝﾆｬﾝｶﾞｵｰ★", "_(　　_ΦДΦ)_ ﾆ\"ｬｧ\"ｧ\"ｧ\"",
                 "ฅ(>ω<ฅ)ﾆｬﾝ♪☆*。", "ฅ(○•ω•○)ฅﾆｬ～ﾝ❣", "ฅ(°͈ꈊ°͈ฅ)ﾆｬｰ",
                 "(ฅ✧ω✧ฅ)ﾆｬ", "(ฅฅ)にゃ♡", "ฅ^•ﻌ•^ฅﾆｬﾝ",
                 "ヾ(⌒(_´,,−﹃−,,`)_ゴロにゃん",
                 "ฅ•ω•ฅﾆｬﾆｬｰﾝ✧", "๑•̀ㅁ•́ฅ✧にゃ!!",
                 "ヾ(⌒(_*Φ ﻌ Φ*)_ﾆｬｰﾝ♡",
                 "ᗦ↞◃ ᗦ↞◃ ᗦ↞◃ ᗦ↞◃ ฅ(^ω^ฅ) ﾆｬ～"]
        await ctx.followup.send(random.choice(nekos), ephemeral=ephemeral)
        await self.dbm.log_command(ctx.user.id, "cat", None, ctx.guild.id if ctx.guild else None, result="Success")

    # dice

    @app_commands.command(name="dice", description="サイコロを振ります")
    @app_commands.describe(pcs="サイコロの個数")
    @app_commands.describe(maximum="サイコロの最大値")
    @ephemeral_check
    @restrict_check
    async def dice(self, ctx: discord.Interaction, pcs: app_commands.Range[int, 1, 100] = 1, maximum: app_commands.Range[int, 1, 999] = 6):
        await ctx.response.defer()
        ephemeral = ctx.extras.get('ephemeral', False)

        if ctx.extras.get('restricted', False):
            await send_error(ctx, None, "このコマンドはサーバー管理者によって実行が制限されています。", None, is_followup=True)
            return

        # maximumが6以下なら絵文字を使用する
        if maximum > 6:
            dices = [random.randint(1, maximum) for i in range(pcs)]

        else:
            word_list = [":one:", ":two:", ":three:",
                            ":four:", ":five:", ":six:"]
            word_list = word_list[:(maximum - 1)]
            dices = [random.choice(word_list) for i in range(pcs)]

        await ctx.followup.send(f":game_die: {', '.join(map(str, dices))}が出たよ", ephemeral=ephemeral)
        await self.dbm.log_command(ctx.user.id, "dice", [pcs, maximum], ctx.guild.id if ctx.guild else None, result="Success")

    # omikuji

    @app_commands.command(name="omikuji", description="おみくじ")
    @app_commands.describe(pcs="引く枚数")
    @ephemeral_check
    @restrict_check
    async def omikuji(self, ctx: discord.Interaction, pcs: app_commands.Range[int, 1, 100] = 1):
        await ctx.response.defer()
        ephemeral = ctx.extras.get('ephemeral', False)

        if ctx.extras.get('restricted', False):
            await send_error(ctx, None, "このコマンドはサーバー管理者によって実行が制限されています。", None, is_followup=True)
            return

        omikuji_list = ["大大凶", "大凶", "凶", "末吉",
                        "小吉", "中吉", "吉", "大吉", "大大吉"]
        kuji_results = [""] * pcs
        points = 0

        if pcs > 1:
            for i in range(pcs):
                j = random.choice(omikuji_list)
                points += omikuji_list.index(j) + 1
                kuji_results[i] = f"**{j}**"

            await ctx.followup.send(f"今日の運勢は... {', '.join(map(str, kuji_results))}！"
                                            f"（{pcs}連おみくじ総合運勢: **{omikuji_list[(points // pcs) - 1]}）**", ephemeral=ephemeral)

        else:
            await ctx.followup.send(f"今日の運勢は... **{random.choice(omikuji_list)}**！", ephemeral=ephemeral)

        await self.dbm.log_command(ctx.user.id, "omikuji", pcs, ctx.guild.id if ctx.guild else None, result="Success")

    # janken

    @app_commands.command(name="janken", description="じゃんけん")
    @restrict_check
    async def janken(self, ctx: discord.Interaction):
        await ctx.response.defer()
        #ephemeral = ctx.extras.get('ephemeral', False)

        if ctx.extras.get('restricted', False):
            await send_error(ctx, None, "このコマンドはサーバー管理者によって実行が制限されています。", None, is_followup=True)
            return

        button1 = discord.ui.Button(label="ぐー", style=discord.ButtonStyle.primary, custom_id="j_g")
        button2 = discord.ui.Button(label="ちょき", style=discord.ButtonStyle.success, custom_id="j_c")
        button3 = discord.ui.Button(label="ぱー", style=discord.ButtonStyle.danger, custom_id="j_p")
        view = discord.ui.View(timeout=60)
        view.add_item(button1)
        view.add_item(button2)
        view.add_item(button3)
        await ctx.followup.send("最初はぐー、じゃんけん", view=view, ephemeral=False)
        await self.dbm.log_command(ctx.user.id, "janken", None, ctx.guild.id if ctx.guild else None, result="Success")

    #########################

    # エラー出力

    async def cog_command_error(self, ctx: discord.Interaction, error):
        embed = discord.Embed(title="エラー",
                              description="不明なエラーが発生しました。",
                              color=0xff0000)
        await ctx.reply(embed=embed, mention_author=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(Fun(bot))
