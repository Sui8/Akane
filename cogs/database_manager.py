# 組み込みライブラリ
import asyncio
import time
import os
from datetime import datetime

# 外部ライブラリ
from discord.ext import commands
from discord import app_commands
import asyncpg # asyncpg
from dotenv import load_dotenv  # python-dotenv
import simplejson as json  # simplejson

load_dotenv()  # .env読み込み

##################################################

DATABASE = os.getenv("DATABASE")

##################################################

class DatabaseManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.pool = None
        self.last_checked = 0  # 最後に接続をチェックした時間
        self.cache_timeout = 60  # 接続状態キャッシュの有効期限 (秒)


    async def cog_load(self):
        # 接続プールを作成
        self.pool = await asyncpg.create_pool(
            dsn=DATABASE,
            min_size=5,  # プール内の最小接続数
            max_size=15,  # プール内の最大接続数
            statement_cache_size=0
        )
        print("PostgreSQL pool has been created.")


    async def cog_unload(self):
        # 接続プールを閉じる
        if self.pool:
            await self.pool.close()
            print("PostgreSQL pool has been closed.")

    ###########################

    async def log_command(self, user_id, command, args=None, guild_id=None, result="Success"):
        """コマンド実行ログをDBに保存する関数"""
        timestamp = datetime.now()

        if isinstance(args, list):
            args = json.dumps(args)

        elif isinstance(args, int):
            args = str(args)

        elif isinstance(args, float):
            args = str(args)

        async with self.pool.acquire() as connection:
            try:
                await connection.execute(
                    """
                    INSERT INTO command_logs (user_id, command, args, guild_id, timestamp, result)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """, 
                    user_id, command, args, guild_id, timestamp, result
                )
            except Exception as e:
                print(e)

    async def check_db(self):
        """DB接続の確認"""
        if self.pool:
            return True

        else:
            return False


async def setup(bot: commands.Bot):
    await bot.add_cog(DatabaseManager(bot))
