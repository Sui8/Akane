# 組み込みライブラリ
import os
import datetime


# 外部ライブラリ
import discord
from discord import app_commands
from discord.ext import commands  # Bot Commands Framework
from dotenv import load_dotenv  # python-dotenv
import requests
from bs4 import BeautifulSoup

# 自作モジュール
from modules.utils import send_error
from modules.decorators import ephemeral_check, restrict_check


load_dotenv()  # .env読み込み

##################################################

''' 定数群 '''

VERSION = os.getenv("VERSION")

##################################################

''' 関数群 '''


def track_package(tracking_code):
    """
    日本郵便の追跡サービスから現在のステータスと履歴情報を取得する関数。

    Args:
        tracking_code (str): 追跡番号。

    Returns:
        dict: 現在のステータスと履歴情報を含む辞書。
    """
    url = "https://www.post.japanpost.jp/receive/tracking/result.php"
    params = {"code": tracking_code}

    try:
        # ページを取得
        response = requests.get(url, params=params)
        response.encoding = "UTF-8"
        soup = BeautifulSoup(response.text, "html.parser")

        # ステータス取得
        status_header = soup.find("h2", class_="uline2 sp-t20 sp-b20")

        if status_header:
            status_div = status_header.find_next("div", class_="boxBorder radius5")

            if status_div:
                current_status = status_div.find("p", class_="arrange-c txtStatus").text.strip()

                if "お問い合わせ番号が見つかりません" in current_status:
                    return {"error": "追跡番号が見つかりませんでした。"}

            else:
                return {"error": "ステータス情報が見つかりませんでした。"}

        else:
            return {"error": "ステータスヘッダーが見つかりませんでした。"}

        # 履歴情報取得
        timeline = soup.find("div", {"class": "timeline", "id": "timeline"})
        if timeline:
            entries = []

            for dl in timeline.find_all("dl"):
                # 日付情報（<dd>内の<span class="date">から取得）
                date_span = dl.find("span", class_="date")
                date = date_span.text.strip() if date_span else "日時不明"

                # 詳細とステータス（<dt>から取得）
                details_dt = dl.find("dt")
                details_text = details_dt.text.strip() if details_dt else "詳細不明"

                # 改行や余計なスペースを削除
                details_text = details_text.replace("\u3000", "").strip()  # 全角スペースを取り除く
                lines = details_text.split("\n")  # 改行で分割

                # 1行目はdetails、3行目はstatus
                details = lines[0].strip() if len(lines) > 0 else "詳細不明"
                status = lines[2].strip() if len(lines) > 2 else "ステータス不明"

                # 1つのエントリとして保存
                entries.append({"date": date, "details": details, "status": status})

            return {"status": current_status, "history": entries}

        else:
            if "お問い合わせ番号が見つかりません" not in current_status:
                return {"error": "履歴情報が見つかりませんでした。"}

    except Exception:
        return {"error": "不明なエラーが発生しました。"}

##################################################


''' コマンド '''


class JpPost(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Cog読み込み時
    @commands.Cog.listener()
    async def on_ready(self):
        # ---- DB読み込み＆チェック ----
        self.dbm = self.bot.get_cog("DatabaseManager")

        if not self.dbm:
            raise RuntimeError("jppost: Database cog is not ready")

        if not await self.dbm.check_db():
            raise RuntimeError("jppost: Database is not ready")

        #############################

        print("jppost: ready")

    #########################

    # help

    @app_commands.command(name="track", description="日本郵便の荷物を追跡します")
    @app_commands.describe(number="追跡番号")
    @app_commands.checks.cooldown(2, 30)
    @ephemeral_check
    @restrict_check
    async def track(self, ctx: discord.Interaction, number: app_commands.Range[str, 1, 30]):
        ephemeral = ctx.extras.get('ephemeral', False)

        await ctx.response.defer()

        if ctx.extras.get('restricted', False):
            await send_error(ctx, None, "このコマンドはサーバー管理者によって実行が制限されています。", None, is_followup=True)
            return

        number.replace("-", "").replace(" ", "").replace("　", "")  # ハイフン除去

        result = track_package(number)

        if "error" in result:
            await send_error(ctx, None, result['error'], None, is_followup=True)
            await self.dbm.log_command(ctx.user.id, "jppost", number, ctx.guild.id if ctx.guild else None, result="Failed")
            return

        embed = discord.Embed(title="追跡結果", description="",
                              timestamp=datetime.datetime.now(), color=0xdc143c)

        description = ""

        for entry in result["history"]:
            description += f"**{entry['status']}**\n{entry['date']}\n取扱局: {entry['details']}\n\n"

        description = description[:1000]

        embed.add_field(name=f"現在のステータス: {result['status']}", value=description)
        embed.set_footer(text=f"追跡番号: {number}")

        # URLボタン
        button = discord.ui.Button(label="Webで見る",
                                   style=discord.ButtonStyle.link,
                                   url=f"https://www.post.japanpost.jp/receive/tracking/result.php?code={number}")
        view = discord.ui.View()
        view.add_item(button)

        await ctx.followup.send(embed=embed, view=view, ephemeral=ephemeral)
        await self.dbm.log_command(ctx.user.id, "jppost", number, ctx.guild.id if ctx.guild else None, result="Success")

    #########################

    ''' クールダウン '''

    @track.error
    async def stats_on_command_error(self, ctx: discord.Interaction, error: app_commands.AppCommandError):
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
    await bot.add_cog(JpPost(bot))
