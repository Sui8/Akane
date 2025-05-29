# 組み込みライブラリ
from datetime import datetime, timedelta, timezone
import random
import ast
import asyncio
import asyncpg

# 外部ライブラリ
import discord
from discord import app_commands
from discord.ext import commands  # Bot Commands Framework
import simplejson as json  # simplejson
import jaconv  # jaconv (カタカナ変換)

# 自作モジュール
from modules.utils import send_error
from modules.decorators import ephemeral_check, restrict_check

##################################################

rarity_mapping = {"0": "PROMO", "10": "PROMO", "30": "PROMO", "40": "PROMO", "50": "PROMO", "1": "◇1", "2": "◇2",
                                "3": "◇3", "4": "◇4", "5": "☆1", "6": "☆2",
                                "7": "☆3", "70": "☆3",
                                "8": "👑", "81": "👑", "82": "👑", "83": "👑",
                                "11": "＊1", "12": "＊2"}
cardtype_mapping = {"0": "グッズ", "1": "ポケモンのどうぐ", "2": "サポート", "3": "スタジアム", "4": "たねポケモン",
                    "5": "1進化ポケモン", "6": "2進化ポケモン", "7": "たねポケモン (ex)", "8": "1進化ポケモン (ex)",
                    "9": "2進化ポケモン (ex)"}
type_mapping = {"0": "草", "1": "炎", "2": "水", "3": "雷", "4": "超", "5": "闘",
                "6": "悪", "7": "鋼", "8": "ドラゴン", "9": "無色"}
energy_mapping = {"0": "<:Grass_Energy:1368063994723700898>", "1": "<:Fire_Energy:1368064051480891474>",
                  "2": "<:Water_Energy:1368064328565129317>", "3": "<:Electric_Energy:1368064437289881611>",
                  "4": "<:Psychic_Energy:1368064487571198062>", "5": "<:Fighting_Energy:1368064580496134165>",
                  "6": "<:Dark_Energy:1368064627258167357>", "7": "<:Steel_Energy:1368064661622095912>",
                  "8": "<:Dragon_Energy:1368064703783239720>", "9": "<:Colorless_Energy:1368064742668894238>"}
damage_type_mapping = {"0": "+", "1": "×"}
type_color_mapping = {"0": 0x93bb3b, "1": 0xe55837, "2": 0x2ca0db, "3": 0xfada00, "4": 0xa16aa8, "5": 0xd28916,
                      "6": 0x052f2e, "7": 0xc3ced2, "8": 0xbba92e, "9": 0xe9e6e1, "10": 0x89cbea, "11": 0xc197c1,
                      "12": 0xf4c282, "13": 0xafd484}
get_source_mapping = {"A11": "[A1] 最強の遺伝子 リザードン", "A12": "[A1] 最強の遺伝子 ミュウツー", "A13": "[A1] 最強の遺伝子 ピカチュウ",
                      "A1": "[A1] 最強の遺伝子", "A1a": "[A1a] 幻のいる島", "A21": "[A2] 時空の激闘 ディアルガ", "A22": "[A2] 時空の激闘 パルキア",
                      "A2": "[A2] 時空の激闘", "A2a": "[A2a] 超克の光", "A2b": "[A2b] シャイニングハイ",
                      "A31": "[A3] 双天の守護者 ソルガレオ", "A32": "[A3] 双天の守護者 ルナアーラ", "A3": "[A3] 双天の守護者",
                      "A3a": "[A3a] 異次元クライシス",
                      "A1p": "PROMO-A Vol.1", "A1p2": "PROMO-A Vol.2", "A1ap": "PROMO-A Vol.3", "A2p": "PROMO-A Vol.4",
                      "A2ap": "PROMO-A Vol.5", "A2bp": "PROMO-A Vol.6", "A3p": "PROMO-A Vol.7", "A3p2": "PROMO-A Vol.8",
                      "ATS": "ショップ", "APS": "プレミアムショップ", "ACP": "キャンペーン", "AMS": "ミッション", "AGC": "ゲットチャレンジ"}
major_packs = ["A11", "A12", "A13", "A21", "A22", "A31", "A32"]
promo_a_packs = ["A1p", "A1p2", "A1ap", "A2p", "A2ap", "A2bp", "A3p", "ATS", "APS", "ACP", "AMS", "AGC"]

##################################################

# パック開封関数
async def pick_cards(self, pack_id, pcs):
    # ゴッドパック
    if random.random() < 0.0005:
        god_pack = True

    else:
        god_pack = False

    # パック種類の確認
    if pack_id in ["A11", "A12", "A13"]:
        where = f"pack_id IN ('A1', '{pack_id}')"

    elif pack_id in ["A21", "A22"]:
        where = f"pack_id IN ('A2', '{pack_id}')"

    elif pack_id in ["A31", "A32"]:
        where = f"pack_id IN ('A3', '{pack_id}')"

    else:
        where = f"pack_id = '{pack_id}'"

    async with self.dbm.pool.acquire() as conn:
        if god_pack:
            # 1回のDB読み込みで pack_name, pull_rate, pcs, カードリストを取得
            pack_info = await conn.fetchrow(f"""
                SELECT pack_name, god_rate, pcs
                FROM packs
                WHERE {where}
            """)

        else:
            # 1回のDB読み込みで pack_name, pull_rate, pcs, カードリストを取得
            pack_info = await conn.fetchrow(f"""
                SELECT pack_name, pull_rate, pcs
                FROM packs
                WHERE {where}
            """)

        pack_name = pack_info["pack_name"]
        pull_rate = json.loads(pack_info["pull_rate"])  # JSONをPythonの辞書に変換
        card_pcs = pack_info["pcs"]

        # すべての pack_id に対応するカード情報を一度に取得
        all_cards = await conn.fetch("""
            SELECT card_name, rarity
            FROM cards
            WHERE pack = $1
        """, pack_id)

        # レアリティごとにカードを分類（辞書に格納）
        rarity_to_cards = {}

        # クラウンレア
        rarity_to_cards[8] = []

        for record in all_cards:
            rarity = record["rarity"]
            card_name = record["card_name"]

            if rarity not in rarity_to_cards:
                rarity_to_cards[rarity] = []

            # クラウン
            if 81 <= rarity <= 89:
                rarity_to_cards[8].append(card_name)

            rarity_to_cards[rarity].append(card_name)

        # カード取得開始
        selected_cards = []

        if pcs == "10":
            common_count = 0

            for j in range(10):
                for i in range(1, card_pcs + 1):
                    rarity_prob = pull_rate.get(str(i))  # i枚目のレアリティ確率を取得

                    # レアリティを確率に基づいて選択
                    rarities = list(rarity_prob.keys())
                    probabilities = list(rarity_prob.values())
                    selected_rarity = int(random.choices(rarities, probabilities)[0])

                    if selected_rarity in [10, 1, 2]:
                        common_count += 1
                        
                    else:
                        # Python側でレアリティごとのカードリストから選択
                        selected_card = random.choice(rarity_to_cards[selected_rarity])
                        f_rarity = rarity_mapping.get(str(selected_rarity), "不明")
                        selected_cards.append(f"・{selected_card} ({f_rarity})")
            
            if common_count != 0:
                selected_cards.append(f"・ノーマルカード ×{common_count}")

        else:
            for i in range(1, card_pcs + 1):
                rarity_prob = pull_rate.get(str(i))  # i枚目のレアリティ確率を取得

                # レアリティを確率に基づいて選択
                rarities = list(rarity_prob.keys())
                probabilities = list(rarity_prob.values())
                selected_rarity = int(random.choices(rarities, probabilities)[0])

                if selected_rarity == 8:
                    selected_rarity = 80 + random.randint(1, 3)

                # Python側でレアリティごとのカードリストから選択
                selected_card = random.choice(rarity_to_cards[selected_rarity])
                f_rarity = rarity_mapping.get(str(selected_rarity), "不明")
                selected_cards.append(f"・{selected_card} ({f_rarity})")

        return [pack_name, selected_cards]

##################################################

''' コマンド '''

class PokePoke(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Cog読み込み時

    @commands.Cog.listener()
    async def on_ready(self):
        ##### DB読み込み＆チェック #####
        self.dbm = self.bot.get_cog("DatabaseManager")

        if not self.dbm:
            raise RuntimeError("pokepoke: Database cog is not ready")

        if not await self.dbm.check_db():
            raise RuntimeError("pokepoke: Database is not ready")

        #############################

        print("pokepoke: Ready")

    #########################

    # コマンドをグループ化
    group = app_commands.Group(name="poke", description="ポケポケ関係のコマンド")

    # open
    @group.command(name="open", description="ポケポケパック開封シミュレーター")
    @app_commands.checks.cooldown(2, 3)
    @app_commands.describe(pack="開封するパック")
    @app_commands.choices(pack=[
        discord.app_commands.Choice(name="[A3a] 異次元クライシス", value="A3a"),
        discord.app_commands.Choice(name="[A3] 双天の守護者 ソルガレオ", value="A31"),
        discord.app_commands.Choice(name="[A3] 双天の守護者 ルナアーラ", value="A32"),
        discord.app_commands.Choice(name="[A2b] シャイニングハイ", value="A2b"),
        discord.app_commands.Choice(name="[A2a] 超克の光", value="A2a"),
        discord.app_commands.Choice(name="[A2] 時空の激闘 ディアルガ", value="A21"),
        discord.app_commands.Choice(name="[A2] 時空の激闘 パルキア", value="A22"),
        discord.app_commands.Choice(name="[A1a] 幻のいる島", value="A1a"),
        discord.app_commands.Choice(name="[A1] 最強の遺伝子 リザードン", value="A11"),
        discord.app_commands.Choice(name="[A1] 最強の遺伝子 ミュウツー", value="A12"),
        discord.app_commands.Choice(name="[A1] 最強の遺伝子 ピカチュウ", value="A13"),
        discord.app_commands.Choice(name="[PROMO] PROMO-A Vol.8", value="A3p2"),
        discord.app_commands.Choice(name="[PROMO] PROMO-A Vol.7", value="A3p"),
        discord.app_commands.Choice(name="[PROMO] PROMO-A Vol.6", value="A2bp"),
        discord.app_commands.Choice(name="[PROMO] PROMO-A Vol.5", value="A2ap"),
        discord.app_commands.Choice(name="[PROMO] PROMO-A Vol.4", value="A2p"),
        discord.app_commands.Choice(name="[PROMO] PROMO-A Vol.3", value="A1ap"),
        discord.app_commands.Choice(name="[PROMO] PROMO-A Vol.2", value="A1p2"),
        discord.app_commands.Choice(name="[PROMO] PROMO-A Vol.1", value="A1p")])
    @app_commands.describe(pcs="開封数")
    @app_commands.choices(pcs=[
        discord.app_commands.Choice(name="1パック", value="1"),
        discord.app_commands.Choice(name="10パック", value="10")])
    @ephemeral_check
    @restrict_check
    async def open(self, ctx: discord.Interaction, pack: str, pcs: str = None):
        try:
            ephemeral = ctx.extras.get('ephemeral', False)
            await ctx.response.defer()

            if ctx.extras.get('restricted', False):
                await send_error(ctx, None, "このコマンドはサーバー管理者によって実行が制限されています。", None, is_followup=True)
                return

            pack_name, selected_cards = await pick_cards(self, pack, pcs)

            # タイトルをパック数に応じて変更する
            if pcs == "10":
                title_pcs = "10パック"

            else:
                title_pcs = "1パック"

            embed = discord.Embed(
                title=f"@{ctx.user.name} の開封結果",
                description="",
                color=discord.Colour(random.randint(0, 0xFFFFFF)))
            embed.add_field(name=f"{pack_name} ({title_pcs})",
                            value='\n'.join(selected_cards), inline=True)
            embed.set_footer(text="このシミュレーターはポケポケ非公式です")

            # 2回目以降
            async def button_callback(interaction):
                if interaction.user != ctx.user:
                    embed = discord.Embed(title="エラー",
                                          description="コマンド実行者以外は使用できません",
                                          color=0xff0000)
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return

                pack_name, selected_cards = await pick_cards(self, pack, pcs)

                embed = discord.Embed(
                    title=f"@{interaction.user.name} の開封結果",
                    description="",
                    color=discord.Colour(random.randint(0, 0xFFFFFF)))
                embed.add_field(name=f"{pack_name} ({title_pcs})",
                                value='\n'.join(selected_cards), inline=True)
                embed.set_footer(text="このシミュレーターはポケポケ非公式です")

                # ボタンにコールバックを設定
                button = discord.ui.Button(label="もう一度開封", style=discord.ButtonStyle.primary)
                button.callback = button_callback

                # ビューにボタンを追加
                view = discord.ui.View(timeout=300)
                view.add_item(button)

                # タイムアウト後の処理
                async def on_timeout():
                    # ドロップダウンを無効にする（ビューがタイムアウトした後）
                    for item in view.children:
                        item.disabled = True

                    await interaction.edit_original_response(view=view)

                view.on_timeout = on_timeout

                await interaction.response.send_message(embed=embed, view=view, ephemeral=ephemeral)


            # ボタンにコールバックを設定
            button = discord.ui.Button(label="もう一度開封", style=discord.ButtonStyle.primary)
            button.callback = button_callback

            # ビューにボタンを追加
            view = discord.ui.View(timeout=300)
            view.add_item(button)

            # タイムアウト後の処理
            async def on_timeout():
                # ドロップダウンを無効にする（ビューがタイムアウトした後）
                for item in view.children:
                    item.disabled = True

                await ctx.edit_original_response(view=view)

            view.on_timeout = on_timeout

            await ctx.followup.send(embed=embed, view=view, ephemeral=ephemeral)
            await self.dbm.log_command(ctx.user.id, "poke open", [pack, pcs], ctx.guild.id if ctx.guild else None, result="Success")

        except Exception as e:
            import traceback
            print(traceback.format_exc())


    # info
    @group.command(name="info", description="ポケポケのカード情報を表示する (最大25件まで検索可能)")
    @app_commands.checks.cooldown(2, 3)
    @app_commands.describe(name="カード名")
    @ephemeral_check
    @restrict_check
    async def info(self, ctx: discord.Interaction, name: app_commands.Range[str, 1, 10]):
        await ctx.response.defer()
        ephemeral = ctx.extras.get('ephemeral', False)

        if ctx.extras.get('restricted', False):
            await send_error(ctx, None, "このコマンドはサーバー管理者によって実行が制限されています。", None, is_followup=True)
            return

        # 1. 半角カナ・半角英数字を全角カナ・全角英数字に置換
        name_z = jaconv.h2z(name, kana=True, ascii=True, digit=True)

        # 2. ひらがな＜－＞カタカナに置換
        name_kana = jaconv.hira2kata(name_z)
        name_hira = jaconv.kata2hira(name_z)

        async with self.dbm.pool.acquire() as conn:
            # 1回のDB読み込みで pack_name, pull_rate, pcs, カードリストを取得
            # ついでにidが存在するデータも取りに行く
            result = await conn.fetch(f"""
                SELECT c.card_name, c.card_id, c.rarity, c.hp, c.type, c.cardtype, 
                    c.evolution_from, c.description, 
                    COALESCE(cs.description, c.spec_id::TEXT) AS spec_desc,
                    COALESCE(sk.description, NULL) AS skill_desc,
                    COALESCE(sk.skill_name, NULL) AS skill_name,
                    COALESCE(ca.description, NULL) AS ability_desc,
                    COALESCE(ca.ability_name, NULL) AS ability_name,
                    COALESCE(ca.damage, NULL) AS ability_damage,
                    COALESCE(ca.damage_type, NULL) AS ability_damage_type,  
                    COALESCE(ca.energy, NULL) AS ability_energy,
                    c.away, c.effective, c.pack,
                    GREATEST(
                        similarity(c.card_name, $1),
                        similarity(c.card_name, $2),
                        similarity(c.card_name, $3)
                    ) AS similarity_score
                FROM cards c
                LEFT JOIN card_specs cs ON c.spec_id = cs.spec_id
                LEFT JOIN card_skills sk ON c.skill_id = sk.skill_id
                LEFT JOIN card_abilities ca ON ca.ability_id = CAST(c.ability_id[1] AS INTEGER)
                WHERE c.card_name ILIKE $1 OR c.card_name ILIKE $2 OR c.card_name ILIKE $3
                ORDER BY similarity_score DESC, c.card_id 
                LIMIT 25
            """, f"%{name_z}%", f"%{name_kana}%", f"%{name_hira}%")

        if not result:
            embed = discord.Embed(title=":x: 検索失敗",
                                description="一致するカードが見つかりませんでした",
                                color=0xff0000)
            await ctx.followup.send(embed=embed, ephemeral=True)
            return

        # ドロップダウンの選択肢を作成
        try:
            options = []
            labels = {}

            for card in result:
                # pack_nameのフォーマット
                if card['pack'] in major_packs:
                    pack = card['pack'][:2]

                elif card['pack'] in promo_a_packs:
                    pack = "P-A"

                else:
                    pack = card['pack']

                # card_idのフォーマット
                if int(card['card_id']) > 1000:
                    id = str(card['card_id'])[-3:]

                else:
                    # PROMO-A
                    id = str(card['card_id']).zfill(3)

                f_rarity = rarity_mapping.get(str(card['rarity']), "不明")
                label = f"{card['card_name']} ({f_rarity}) [{pack} {id}]"
                labels[str(card['card_id'])] = label
                options.append(discord.SelectOption(label=label, value=card['card_id']))
            
            # ドロップダウンメニューとボタンを作成
            select = discord.ui.Select(placeholder="カードを選んでください", options=options)
            
            # ドロップダウンが選ばれた時のコールバック
            async def select_callback(interaction):
                if interaction.user != ctx.user:
                    embed = discord.Embed(title=":x: エラー",
                                          description="コマンド実行者以外は使用できません",
                                          color=0xff0000)
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return

                # 選ばれたカードの名前を取得
                try:
                    selected_card_id = interaction.data['values'][0]
                    selected_card_label = labels[selected_card_id]
                    selected_card = next(card for card in result if str(card['card_id']) == selected_card_id)

                    # ドロップダウンを作成
                    select = discord.ui.Select(placeholder="他のカードを見る", options=options)
                    select.callback = select_callback
                    view = discord.ui.View(timeout=600)
                    view.add_item(select)

                    # タイムアウト後の処理
                    async def on_timeout():
                        # ドロップダウンを無効にする（ビューがタイムアウトした後）
                        for item in view.children:
                            item.disabled = True

                        await interaction.edit_original_response(view=view)

                    view.on_timeout = on_timeout

                    # カードの説明を作成
                    information = cardtype_mapping.get(str(selected_card['cardtype']), '不明')

                    # 未対応カードの応急処置
                    if information == "不明":
                        information = "このカードは未対応です"
                        color = 0xffffff

                    # ポケモンの場合
                    elif int(selected_card['cardtype']) >= 4:
                        information += f" / {energy_mapping.get(str(selected_card['type']), '不明')}\n"
                        information += f"【HP】{selected_card['hp']}\n"
                        information += f"【弱点】{energy_mapping.get(str(selected_card['effective']), '')}\n"

                        if selected_card['away'] >= 0:
                            information += f"【にげる】{'<:Colorless_Energy:1368064742668894238>' * int(selected_card['away'])}\n"

                        # 進化ポケモン
                        if str(selected_card['cardtype']) in ["5", "6", "8", "9"]:
                            information += f"【進化元】{selected_card['evolution_from']}\n"

                        information += f"【入手方法】{get_source_mapping.get(str(selected_card['pack']), '不明')}"

                        # ワザ
                        if selected_card['ability_name']:
                            # energy
                            energy_list = ast.literal_eval(selected_card['ability_energy'])
                            energy = "".join(energy_mapping[str(x)] for x in energy_list)

                            # damage_type
                            if selected_card['ability_damage_type']:
                                damage_type = damage_type_mapping.get(str(selected_card['ability_damage_type']), "")

                            else:
                                damage_type = ""

                            information += f"\n\n**{energy} {selected_card['ability_name']} {selected_card['ability_damage'] if selected_card['ability_damage'] is not None else ''}{damage_type}**"

                            if selected_card['ability_desc']:
                                information += f"\n{selected_card['ability_desc']}"

                        color = type_color_mapping.get(str(selected_card['type']), 0xffffff)

                    # それ以外の場合
                    else:
                        information += f"\n【入手方法】{get_source_mapping.get(str(selected_card['pack']), '不明')}"

                        if selected_card['spec_desc']:
                            information += f"\n\n【効果】{selected_card['spec_desc']}"

                        color = type_color_mapping.get(str(int(selected_card['cardtype']) + 10), 0xffffff)

                    embed = discord.Embed(title=f"{selected_card_label}",
                                          description=information,
                                          color=color)
                    # クレジット
                    embed.set_footer(text="画像引用元: deviantart.com/biochao")

                    await interaction.response.edit_message(embed=embed, view=view)
                except:
                    import traceback
                    print(traceback.format_exc())

            select.callback = select_callback
            view = discord.ui.View(timeout=600)
            view.add_item(select)

            # タイムアウト後の処理
            async def on_timeout():
                # ドロップダウンを無効にする（ビューがタイムアウトした後）
                for item in view.children:
                    item.disabled = True

                await ctx.edit_original_response(view=view)

            view.on_timeout = on_timeout
            
            embed = discord.Embed(title=":mag: 検索結果",
                                  description=f"{len(options)}件見つかりました\nカードを選択してください",
                                  color=discord.Colour.green())
            await ctx.followup.send(embed=embed, view=view, ephemeral=ephemeral)
            await self.dbm.log_command(ctx.user.id, "poke info", name, ctx.guild.id if ctx.guild else None, result="Success")

        except Exception as e:
            print(e)
            import traceback
            print(traceback.format_exc())

    #########################

    ''' クールダウン '''

    @open.error
    async def open_on_command_error(self, ctx: discord.Interaction, error: app_commands.AppCommandError):
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
    await bot.add_cog(PokePoke(bot))
