# 組み込みライブラリ
import secrets
import os
from datetime import datetime, timedelta, timezone
import re
import time
import random
import string
import sqlite3
import asyncio
import traceback

# 外部ライブラリ
import discord
from discord import app_commands
from discord.ext import commands  # Bot Commands Framework
import simplejson as json  # simplejson

# 自作モジュール
from modules.utils import send_error
from modules.decorators import ephemeral_check, restrict_check


##################################################

# デッキを初期化
def create_deck():
    suits = ['♠', '♣', '♦', '♥']
    values = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
    deck = [f'{suit}{value}' for value in values for suit in suits]
    random.shuffle(deck)
    return deck

# 手札の合計を計算
def calculate_hand(hand):
    total = 0
    aces = 0

    for card in hand:
        value = card[1:]  # カードの値

        if value in ['J', 'Q', 'K']:
            total += 10

        elif value == 'A':
            total += 11
            aces += 1

        else:
            total += int(value)
    
    # エースが1点でカウントできるように調整
    while total > 21 and aces:
        total -= 10
        aces -= 1
    
    return total

# /blackjackのview
class BlackjackView(discord.ui.View):
    def __init__(self, dbm, author_id, deck, player_hand, dealer_hand, balance, bet, double, timeout=300):
        super().__init__(timeout=timeout)
        self.dbm = dbm
        self.author_id = author_id
        self.game_data = {
            "deck": deck,
            "player_hand": player_hand,
            "dealer_hand": dealer_hand
        }
        self.balance = balance
        self.bet = bet
        self.double = double
        self.message = None
        self.split = 0

        # SPLITできるか
        #if player_hand[0][1:] == player_hand[1][1:]:
        #    if self.double:
        #        self.add_buttons(param=0)
        #
        #    else:
        #        self.add_buttons(param=3)

        if self.double:
            self.add_buttons(param=2)

        else:
            self.add_buttons(param=4)

    # buttonのcallback
    async def button_callback(self, interaction: discord.Interaction):
        if self.game_data is None:
            return

        if interaction.user.id != self.author_id:
            embed = discord.Embed(title=":x: エラー",
                                  description="このメニューはコマンド実行者のみ操作できます。",
                                  color=0xff0000)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if self.split == 2:
            player_hand = self.game_data['player_hand_sub']

        else:
            player_hand = self.game_data['player_hand']
        
        deck = self.game_data['deck']
        dealer_hand = self.game_data['dealer_hand']
        
        # 手札の合計
        player_total = calculate_hand(player_hand)
        dealer_total = calculate_hand(dealer_hand)
        
        # ボタンが押された時の処理
        if interaction.data["custom_id"] == "hit":
            # ヒットした場合、新しいカードをプレイヤーに配る
            player_hand.append(deck.pop())
            player_total = calculate_hand(player_hand)
            
            # 21を超えたらバースト
            if player_total > 21:
                for item in self.children:
                    item.disabled = True  # 全てのUIコンポーネントを無効化

                try:
                    if self.message:
                        await self.message.edit(view=self)  # UI を無効化して更新

                except Exception:
                    pass

                embed = discord.Embed(title=f"BlackJack 🃏",
                            description=f"**BUST**\nディーラーの勝ち (-{self.bet:,} ZNY)\n**所持金**: {self.balance:,} ZNY",
                            color=discord.Colour.dark_magenta())
                embed.add_field(name=f"あなた | {player_total}", value=', '.join(player_hand), inline=False)
                embed.add_field(name=f"ディーラー | {calculate_hand([dealer_hand[0]])} + ?", value=f"{dealer_hand[0]}, ?", inline=False)
                await interaction.response.edit_message(embed=embed)
                self.game_data = None

            # BLACKJACK
            elif player_total == 21 and dealer_total != 21:
                # お金の処理を終わらせる
                async with self.dbm.pool.acquire() as conn:
                    await conn.execute('''
                                    UPDATE wallet_data
                                    SET balance = $1
                                    WHERE user_id = $2
                                    ''', self.balance + (self.bet * 2), interaction.user.id)

                for item in self.children:
                    item.disabled = True  # 全てのUIコンポーネントを無効化

                try:
                    if self.message:
                        await self.message.edit(view=self)  # UI を無効化して更新

                except Exception:
                    pass

                embed = discord.Embed(title=f"BlackJack 🃏",
                            description=f"**BLACKJACK**\nあなたの勝ち (+{self.bet:,} ZNY)\n**所持金**: {self.balance + (self.bet * 2):,} ZNY",
                            color=discord.Colour.dark_magenta())
                embed.add_field(name=f"あなた | {player_total}", value=', '.join(player_hand), inline=False)
                embed.add_field(name=f"ディーラー | {calculate_hand(dealer_hand)}", value=', '.join(dealer_hand), inline=False)
                await interaction.response.edit_message(embed=embed)
                self.game_data = None

            # EVEN
            elif player_total == 21 and dealer_total == 21:
                # お金の処理を終わらせる
                async with self.dbm.pool.acquire() as conn:
                    await conn.execute('''
                                    UPDATE wallet_data
                                    SET balance = $1
                                    WHERE user_id = $2
                                    ''', self.balance + self.bet, interaction.user.id)

                for item in self.children:
                    item.disabled = True  # 全てのUIコンポーネントを無効化

                try:
                    if self.message:
                        await self.message.edit(view=self)  # UI を無効化して更新

                except Exception:
                    pass

                embed = discord.Embed(title=f"BlackJack 🃏",
                            description=f"**EVEN**\n引き分け (±0 ZNY)\n**所持金**: {(self.balance + self.bet):,} ZNY",
                            color=discord.Colour.dark_magenta())
                embed.add_field(name=f"あなた | {player_total}", value=', '.join(player_hand), inline=False)
                embed.add_field(name=f"ディーラー | {calculate_hand(dealer_hand)}", value=', '.join(dealer_hand), inline=False)
                await interaction.response.edit_message(embed=embed)
                self.game_data = None

            else:
                # 手札と合計を表示
                embed = discord.Embed(title=f"BlackJack 🃏",
                                description="",
                                color=discord.Colour.dark_magenta())
                embed.add_field(name=f"あなた | {player_total}", value=', '.join(player_hand), inline=False)
                embed.add_field(name=f"ディーラー | {calculate_hand([dealer_hand[0]])} + ?", value=f"{dealer_hand[0]}, ?", inline=False)
                await interaction.response.edit_message(embed=embed)
        
        elif interaction.data["custom_id"] == "stand":
            # スタンドの場合、ディーラーがカードを引き始める
            dealer_total = calculate_hand(dealer_hand)

            while dealer_total < 17:
                dealer_hand.append(deck.pop())
                dealer_total = calculate_hand(dealer_hand)

            for item in self.children:
                item.disabled = True  # 全てのUIコンポーネントを無効化
            
            # 結果を判定
            if dealer_total > 21:
                # 先にお金の処理を終わらせる
                async with self.dbm.pool.acquire() as conn:
                    await conn.execute('''
                                    UPDATE wallet_data
                                    SET balance = $1
                                    WHERE user_id = $2
                                    ''', self.balance + int(self.bet * 1.5), interaction.user.id)

                description = f"**BUST**\nあなたの勝ち (+{int(self.bet * 0.5):,} ZNY)\n**所持金**: {self.balance + int(self.bet * 1.5):,} ZNY"

            elif player_total > dealer_total:
                # 先にお金の処理を終わらせる
                async with self.dbm.pool.acquire() as conn:
                    await conn.execute('''
                                    UPDATE wallet_data
                                    SET balance = $1
                                    WHERE user_id = $2
                                    ''', self.balance + int(self.bet * 1.5), interaction.user.id)

                description = f"**WIN**\nあなたの勝ち (+{int(self.bet * 0.5):,} ZNY)\n**所持金**: {self.balance + int(self.bet * 1.5):,} ZNY"

            elif player_total < dealer_total:
                description = f"**LOSE**\nディーラーの勝ち (-{self.bet:,} ZNY)\n**所持金**: {self.balance:,} ZNY"
            
            else:
                # 先にお金の処理を終わらせる
                async with self.dbm.pool.acquire() as conn:
                    await conn.execute('''
                                    UPDATE wallet_data
                                    SET balance = $1
                                    WHERE user_id = $2
                                    ''', self.balance + self.bet, interaction.user.id)

                description = f"**EVEN**\n引き分け (± 0 ZNY)\n**所持金**: {(self.balance+ self.bet):,} ZNY"

            embed = discord.Embed(title=f"BlackJack 🃏",
                                description=description,
                                color=discord.Colour.dark_magenta())
            embed.add_field(name=f"あなた | {player_total}", value=', '.join(player_hand), inline=False)
            embed.add_field(name=f"ディーラー | {dealer_total}", value=', '.join(dealer_hand), inline=False)
            await interaction.response.edit_message(embed=embed, view=self)
            self.game_data = None

        elif interaction.data["custom_id"] == "double":
            try:
                # DOUBLE DOWN
                player_hand.append(deck.pop())
                player_total = calculate_hand(player_hand)

                dealer_total = calculate_hand(dealer_hand)

                while dealer_total < 17:
                    dealer_hand.append(deck.pop())
                    dealer_total = calculate_hand(dealer_hand)

                for item in self.children:
                    item.disabled = True  # 全てのUIコンポーネントを無効化
                
                # 結果を判定
                if player_total == 21 and dealer_total != 21:
                    # 先にお金の処理を終わらせる
                    async with self.dbm.pool.acquire() as conn:
                        await conn.execute('''
                                        UPDATE wallet_data
                                        SET balance = $1
                                        WHERE user_id = $2
                                        ''', self.balance - self.bet + (self.bet * 2 * 2), interaction.user.id)

                    description = f"**BLACKJACK**\nあなたの勝ち (+{(self.bet * 2):,} ZNY)\n**所持金**: {self.balance - self.bet + (self.bet * 2 * 2):,} ZNY"

                elif player_total > 21:
                    # 先にお金の処理を終わらせる
                    async with self.dbm.pool.acquire() as conn:
                        await conn.execute('''
                                        UPDATE wallet_data
                                        SET balance = $1
                                        WHERE user_id = $2
                                        ''', self.balance - self.bet, interaction.user.id)

                    description = f"**BUST**\nディーラーの勝ち (-{(self.bet * 2):,} ZNY)\n**所持金**: {self.balance - int(self.bet):,} ZNY"

                elif dealer_total > 21:
                    # 先にお金の処理を終わらせる
                    async with self.dbm.pool.acquire() as conn:
                        await conn.execute('''
                                        UPDATE wallet_data
                                        SET balance = $1
                                        WHERE user_id = $2
                                        ''', self.balance - self.bet + int(self.bet * 2 * 1.5), interaction.user.id)

                    description = f"**BUST**\nあなたの勝ち (+{int(self.bet * 2 * 0.5):,} ZNY)\n**所持金**: {self.balance - self.bet + int(self.bet * 2 * 1.5):,} ZNY"

                elif player_total > dealer_total:
                    # 先にお金の処理を終わらせる
                    async with self.dbm.pool.acquire() as conn:
                        await conn.execute('''
                                        UPDATE wallet_data
                                        SET balance = $1
                                        WHERE user_id = $2
                                        ''', self.balance - self.bet + int(self.bet * 2 * 1.5), interaction.user.id)

                    description = f"**WIN**\nあなたの勝ち (+{int(self.bet * 2 * 0.5):,} ZNY)\n**所持金**: {self.balance - self.bet + int(self.bet * 2 * 1.5):,} ZNY"

                elif player_total < dealer_total:
                    # 先にお金の処理を終わらせる
                    async with self.dbm.pool.acquire() as conn:
                        await conn.execute('''
                                        UPDATE wallet_data
                                        SET balance = $1
                                        WHERE user_id = $2
                                        ''', self.balance - self.bet, interaction.user.id)

                    description = f"**LOSE**\nディーラーの勝ち (-{(self.bet * 2):,} ZNY)\n**所持金**: {self.balance - int(self.bet):,} ZNY"
                
                else:
                    # 先にお金の処理を終わらせる
                    async with self.dbm.pool.acquire() as conn:
                        await conn.execute('''
                                        UPDATE wallet_data
                                        SET balance = $1
                                        WHERE user_id = $2
                                        ''', self.balance + self.bet, interaction.user.id)

                    description = f"**EVEN**\n引き分け (±0 ZNY)\n**所持金**: {(self.balance + self.bet):,} ZNY"

                embed = discord.Embed(title=f"BlackJack 🃏",
                                    description=description,
                                    color=discord.Colour.dark_magenta())
                embed.add_field(name=f"あなた | {player_total}", value=', '.join(player_hand), inline=False)
                embed.add_field(name=f"ディーラー | {dealer_total}", value=', '.join(dealer_hand), inline=False)
                await interaction.response.edit_message(embed=embed, view=self)
                self.game_data = None

            except Exception:
                import traceback
                print(traceback.format_exc())

        # ボタンが押された時の処理
        elif interaction.data["custom_id"] == "split":
            self.split = 1

            # 2つ目の手札に分ける
            player_hand_sub = [player_hand.pop(1)]

            player_total = calculate_hand(player_hand)
            player_total_sub = player_total

            # 手札と合計を表示
            self.clear_items()

            if self.double:
                self.add_buttons(param=1)

            else:
                self.add_buttons(param=3)

            embed = discord.Embed(title=f"BlackJack 🃏",
                            description="",
                            color=discord.Colour.dark_magenta())
            embed.add_field(name=f"あなた | {player_total} / {player_total_sub}", value=f"{', '.join(player_hand)}\n{', '.join(player_hand_sub)}", inline=False)
            embed.add_field(name=f"ディーラー | {calculate_hand([dealer_hand[0]])} + ?", value=f"{dealer_hand[0]}, ?", inline=False)
            await interaction.response.edit_message(embed=embed)

    def add_buttons(self, param):
        button = discord.ui.Button(label="Hit", emoji="➕", style=discord.ButtonStyle.blurple, custom_id="hit")
        button.callback = self.button_callback
        self.add_item(button)

        button = discord.ui.Button(label="Stand", emoji="🛑", style=discord.ButtonStyle.blurple, custom_id="stand")
        button.callback = self.button_callback
        self.add_item(button)

        # Double & Split (初手)
        if param == 0:
            button = discord.ui.Button(label="Double", emoji="✖️", style=discord.ButtonStyle.blurple, custom_id="double")
            button.callback = self.button_callback
            self.add_item(button)

            button = discord.ui.Button(label="Split", emoji="✂️", style=discord.ButtonStyle.blurple, custom_id="split")
            button.callback = self.button_callback
            self.add_item(button)
        
        # Double & Split (2回目)
        elif param == 1:
            button = discord.ui.Button(label="Double", emoji="✖️", style=discord.ButtonStyle.blurple, custom_id="double")
            button.callback = self.button_callback
            self.add_item(button)

            button = discord.ui.Button(label="Split", emoji="✂️", style=discord.ButtonStyle.blurple)
            button.disabled = True
            self.add_item(button)

        # Double (初手, 2回目)
        elif param == 2:
            button = discord.ui.Button(label="Double", emoji="✖️", style=discord.ButtonStyle.blurple, custom_id="double")
            button.callback = self.button_callback
            self.add_item(button)

        # Double & Split 資金不足 (初手, 2回目)
        elif param == 3:
            button = discord.ui.Button(label="Double", emoji="✖️", style=discord.ButtonStyle.blurple)
            button.disabled = True
            self.add_item(button)

            button = discord.ui.Button(label="Split", emoji="✂️", style=discord.ButtonStyle.blurple)
            button.disabled = True
            self.add_item(button)

        # Double 資金不足 (初手, 2回目)
        elif param == 4:
            button = discord.ui.Button(label="Double", emoji="✖️", style=discord.ButtonStyle.blurple)
            button.disabled = True
            self.add_item(button)

    async def on_timeout(self):
        """タイムアウト時に全てのボタンとドロップダウンを無効化"""
        for item in self.children:
            item.disabled = True  # 全てのUIコンポーネントを無効化

        try:
            if self.message:
                await self.message.edit(view=self)  # UI を無効化して更新

        except Exception as e:
            print("[ERROR] タイムアウト時のUI更新エラー")
            traceback.print_exc()

        self.game_data = None

##################################################

''' コマンド '''


class Gamble(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Cog読み込み時

    @commands.Cog.listener()
    async def on_ready(self):
        ##### DB読み込み＆チェック #####
        self.dbm = self.bot.get_cog("DatabaseManager")

        if not self.dbm:
            raise RuntimeError("gamble: Database cog is not ready")

        if not await self.dbm.check_db():
            raise RuntimeError("gamble: Database is not ready")

        #############################

        print("gamble: Ready")

    #########################

    # slots

    @app_commands.command(name="slots", description="お金を賭けてスロットを回す")
    @app_commands.describe(amount="賭け金を入力")
    @ephemeral_check
    @restrict_check
    async def slots(self, ctx: discord.Interaction, amount: app_commands.Range[int, 1, 1000000]):
        await ctx.response.defer()
        ephemeral = ctx.extras.get('ephemeral', False)

        if ctx.extras.get('restricted', False):
            await send_error(ctx, None, "このコマンドはサーバー管理者によって実行が制限されています。", None, is_followup=True)
            return

        # DBでuser_idが存在するか確認
        async with self.dbm.pool.acquire() as conn:
            result = await conn.fetchrow('SELECT username, balance FROM wallet_data WHERE user_id = $1', ctx.user.id)

        if not result:
            await send_error(ctx, None, "あなたはウォレットを開設していません。\n`/wallet`コマンドを実行してからお試しください。", None, is_followup=True)
            await self.dbm.log_command(ctx.user.id, "slots", amount, ctx.guild.id if ctx.guild else None, result="Failed (Mistake)")
            return

        balance = result[1]

        if result[1] < amount:
            await send_error(ctx, None, "所持金が不足しています", None, is_followup=True)
            await self.dbm.log_command(ctx.user.id, "slots", amount, ctx.guild.id if ctx.guild else None, result="Failed (Mistake)")
            return

        # メッセージ送信前に結果を確定する
        slots = [1, 2, 3]
        #odds = [4.0, 6.0, 8.0, 15, 30, 50]
        #weights = [50, 30, 20, 15, 5, 1]
        odds = [4.0, 8.0, 15]
        weights = [1, 1, 1]
        emojis = ["<:SLOT_4:1310233526771384440>", "<:SLOT_5:1310233545909993502>", "<:SLOT_6:1310233563567886356>"]
        slot_result = random.choices(slots, k=3, weights=weights)
        bonus = (amount * -1)

        if len(set(slot_result)) == 1:
            bonus = int(amount * (odds[slot_result[0] - 1] - 1))
            wo = f"×{odds[slot_result[0] - 1]} WIN!"

        else:
            wo = "LOSE..."


        # 先にお金の処理を終わらせる
        async with self.dbm.pool.acquire() as conn:
            await conn.execute('''
                                UPDATE wallet_data
                                SET balance = $1
                                WHERE user_id = $2
                                ''', result[1] + bonus, ctx.user.id)

        try:
            await ctx.followup.send("**`___SLOTS___`**\n"
            "`|`<a:SLOT_M1:1310233252950446112><a:SLOT_M2:1310233262274117642><a:SLOT_M3:1310233271392534550>`|`\n"
            "`|         |`\n"
            "`|_________|`\n"
            f"**BET**: {amount:,} ZNY\n"
            f"**所持金**: {balance:,} ZNY", ephemeral=ephemeral)

            # 3回の編集を試みる
            edits = [f"`|`{emojis[slot_result[0] - 1]}<a:SLOT_M2:1310233262274117642><a:SLOT_M3:1310233271392534550>`|`\n",
                    f"`|`{emojis[slot_result[0] - 1]}<a:SLOT_M2:1310233262274117642>{emojis[slot_result[2] - 1]}`|`\n",
                    f"`|`{emojis[slot_result[0] - 1]}{emojis[slot_result[1] - 1]}{emojis[slot_result[2] - 1]}`|`\n",]

            for i in range(3):
                await asyncio.sleep(0.2)

                try:
                    content = "**`___SLOTS___`**\n" \
                            + f"{edits[i]}" \
                            + "`|         |`\n" \
                            + "`|_________|`\n" \
                            + f"**BET**: {amount:,} ZNY\n" \
                            + f"**所持金**: {balance:,} ZNY"

                    if i == 2:
                        content = "**`___SLOTS___`**\n" \
                            + f"{edits[2]}" \
                            + "`|         |`\n" \
                            + "`|_________|`\n" \
                            + f"**{wo}** ({int(bonus):+,} ZNY)\n" \
                            + f"**BET**: {amount:,} ZNY\n" \
                            + f"**所持金**: {(result[1] + bonus):,} ZNY"

                    await ctx.edit_original_response(content=content)

                except Exception:
                    break

            await self.dbm.log_command(ctx.user.id, "slots", amount, ctx.guild.id if ctx.guild else None, result=f"Success ({balance} {bonus:+,} ZNY)")

        except Exception:
            await send_error(ctx, None, f"不明なエラーが発生しましたが、スロットは正常に終了しました。\nスロット結果: **{bonus:+,} ZNY**", None, is_followup=True)
            await self.dbm.log_command(ctx.user.id, "slots", amount, ctx.guild.id if ctx.guild else None, result=f"Failed (Exception, OK: {balance} {bonus:+,} ZNY)")

    # coinflip

    @app_commands.command(name="coinflip", description="お金を賭けてコイントスする")
    @app_commands.describe(amount="賭け金を入力")
    @ephemeral_check
    @restrict_check
    async def coinflip(self, ctx: discord.Interaction, amount: app_commands.Range[int, 1, 30000]):
        await ctx.response.defer()
        ephemeral = ctx.extras.get('ephemeral', False)

        if ctx.extras.get('restricted', False):
            await send_error(ctx, None, "このコマンドはサーバー管理者によって実行が制限されています。", None, is_followup=True)
            return

        # DBでuser_idが存在するか確認
        async with self.dbm.pool.acquire() as conn:
            result = await conn.fetchrow('SELECT username, balance FROM wallet_data WHERE user_id = $1', ctx.user.id)

        if not result:
            await send_error(ctx, None, "あなたはウォレットを開設していません。\n`/wallet`コマンドを実行してからお試しください。", None, is_followup=True)
            await self.dbm.log_command(ctx.user.id, "coinflip", amount, ctx.guild.id if ctx.guild else None, result="Failed (Mistake)")
            return

        if result[1] < amount:
            await send_error(ctx, None, "所持金が不足しています", None, is_followup=True)
            await self.dbm.log_command(ctx.user.id, "coinflip", amount, ctx.guild.id if ctx.guild else None, result="Failed (Mistake)")
            return

        # メッセージ送信前に結果を確定する
        emojis = ["<:COIN_FRONT:1310228758246195220>", "<:COIN_BACK:1310228896079151184>"]
        cf_result = random.choice([True, False])
        bonus = (amount * -1)

        if cf_result is True:
            bonus = amount
            wo = f"WIN! ×2.0"
            emoji = emojis[0]

        else:
            wo = "LOSE..."
            emoji = emojis[1]


        # 先にお金の処理を終わらせる
        async with self.dbm.pool.acquire() as conn:
            await conn.execute('''
                            UPDATE wallet_data
                            SET balance = $1
                            WHERE user_id = $2
                            ''', result[1] + bonus, ctx.user.id)

        try:
            await ctx.followup.send("**`__コイントス__`**\n"
                f"<a:COINFLIP:1310231581960437760> 抽選中...\n"
                f"**BET**: {amount:,} ZNY\n"
                f"**所持金**: {result[1]:,} ZNY", ephemeral=ephemeral)

            # 編集を試みる
            await asyncio.sleep(0.8)

            try:
                content = "**`__コイントス__`**\n" \
                        + f"{emoji} **{wo}** ({bonus:+,} ZNY)\n" \
                        + f"**BET**: {amount:,} ZNY\n" \
                        + f"**所持金**: {(result[1] + bonus):,} ZNY"

                await ctx.edit_original_response(content=content)

            except Exception:
                pass

            await self.dbm.log_command(ctx.user.id, "coinflip", amount, ctx.guild.id if ctx.guild else None, result=f"Success ({result[1]} {bonus:+,} ZNY)")

        except Exception:
            await send_error(ctx, None, f"不明なエラーが発生しましたが、抽選は正常に終了しました。\n抽選結果: **{bonus:+,} ZNY**", None, is_followup=True)
            await self.dbm.log_command(ctx.user.id, "coinflip", amount, ctx.guild.id if ctx.guild else None, result=f"Failed (Exception, OK: {result[1]} {bonus:+,} ZNY)")


    # blackjack
    @app_commands.command(name="blackjack", description="ブラックジャック")
    @app_commands.describe(amount="賭け金を入力")
    @ephemeral_check
    @restrict_check
    async def blackjack(self, ctx: discord.Interaction, amount: app_commands.Range[int, 100, 500000]):
        global game_data

        await ctx.response.defer()
        
        ephemeral = ctx.extras.get('ephemeral', False)

        if ctx.extras.get('restricted', False):
            await send_error(ctx, None, "このコマンドはサーバー管理者によって実行が制限されています。", None, is_followup=True)
            return

        # DBでuser_idが存在するか確認
        async with self.dbm.pool.acquire() as conn:
            result = await conn.fetchrow('SELECT username, balance FROM wallet_data WHERE user_id = $1', ctx.user.id)

        if not result:
            await send_error(ctx, None, "あなたはウォレットを開設していません。\n`/wallet`コマンドを実行してからお試しください。", None, is_followup=True)
            await self.dbm.log_command(ctx.user.id, "blackjack", amount, ctx.guild.id if ctx.guild else None, result="Failed (Mistake)")
            return

        balance = result[1]

        if balance < amount:
            await send_error(ctx, None, "所持金が不足しています", None, is_followup=True)
            await self.dbm.log_command(ctx.user.id, "blackjack", amount, ctx.guild.id if ctx.guild else None, result="Failed (Mistake)")
            return
        
        # Double出来る余裕があるか
        if amount * 2 > balance:
            double = False

        else:
            double = True

        deck = create_deck()
        
        # プレイヤーとディーラーにカードを配る
        player_hand = [deck.pop(), deck.pop()]
        dealer_hand = [deck.pop(), deck.pop()]
        
        # プレイヤーの手札の合計
        player_total = calculate_hand(player_hand)

        # Blackjackしていたとき
        if player_total == 21:
            if calculate_hand(dealer_hand) == 21:
                # メッセージを送信
                embed = discord.Embed(title=f"BlackJack 🃏",
                                    description=f"**EVEN**\n引き分け (±0 ZNY)\n**所持金**: {balance:,} ZNY",
                                    color=discord.Colour.dark_magenta())
                embed.add_field(name=f"あなた | {player_total}", value=', '.join(player_hand), inline=False)
                embed.add_field(name=f"ディーラー | {calculate_hand(dealer_hand)}", value=', '.join(dealer_hand), inline=False)
                await ctx.followup.send(embed=embed)
                await self.dbm.log_command(ctx.user.id, "blackjack", amount, ctx.guild.id if ctx.guild else None, result=f"Success ({balance} +0 ZNY)")
                return

            else:
                # 先にお金の処理を終わらせる
                async with self.dbm.pool.acquire() as conn:
                    await conn.execute('''
                                    UPDATE wallet_data
                                    SET balance = $1
                                    WHERE user_id = $2
                                    ''', balance + amount, ctx.user.id)

                # メッセージを送信
                embed = discord.Embed(title=f"BlackJack 🃏",
                                    description=f"**BLACKJACK**\nあなたの勝ち (+{amount:,} ZNY)",
                                    color=discord.Colour.dark_magenta())
                embed.add_field(name=f"あなた | {player_total}", value=', '.join(player_hand), inline=False)
                embed.add_field(name=f"ディーラー | {calculate_hand(dealer_hand)}", value=', '.join(dealer_hand), inline=False)
                await ctx.followup.send(embed=embed)
                await self.dbm.log_command(ctx.user.id, "blackjack", amount, ctx.guild.id if ctx.guild else None, result=f"Success ({balance + (amount * 2)} +{amount * 2} ZNY)")
                return
        
        # 先にお金の処理を終わらせる
        async with self.dbm.pool.acquire() as conn:
            await conn.execute('''
                            UPDATE wallet_data
                            SET balance = $1
                            WHERE user_id = $2
                            ''', balance - amount, ctx.user.id)

        # viewを作成
        view = BlackjackView(self.dbm, ctx.user.id, deck, player_hand, dealer_hand, balance - amount, amount, double)
        
        # メッセージを送信
        embed = discord.Embed(title=f"BlackJack 🃏",
                              description="",
                              color=discord.Colour.dark_magenta())
        embed.add_field(name=f"あなたの手札 | {player_total}", value=', '.join(player_hand), inline=False)
        embed.add_field(name=f"ディーラー | {calculate_hand([dealer_hand[0]])} + ?", value=f"{dealer_hand[0]}, ?", inline=False)
        view.message = await ctx.followup.send(embed=embed, view=view)
        await self.dbm.log_command(ctx.user.id, "blackjack", amount, ctx.guild.id if ctx.guild else None, result="Success")

    #########################


async def setup(bot: commands.Bot):
    await bot.add_cog(Gamble(bot))
