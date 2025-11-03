import functools


def ephemeral_check(func):

    @functools.wraps(func)
    async def wrapper(self, ctx, *args, **kwargs):
        # DBからユーザー設定を読み出し
        dbm = self.bot.get_cog("DatabaseManager")
        async with dbm.pool.acquire() as conn:
            try:
                user_setting = await conn.fetchval("""
                    SELECT ephemeral FROM user_settings WHERE user_id = $1
                """, ctx.user.id)
            except Exception:
                user_setting = False

        # ephemeralの設定を保存
        ctx.extras['ephemeral'] = not user_setting  # デフォルトは False

        # コマンドの処理を実行
        return await func(self, ctx, *args, **kwargs)

    return wrapper


def restrict_check(func):

    """コマンドが制限されているかをチェックするデコレーター"""
    @functools.wraps(func)
    async def wrapper(self, ctx, *args, **kwargs):
        try:
            # DMなら無条件で実行可能
            if not ctx.guild:
                ctx.extras['restricted'] = False
                return await func(self, ctx, *args, **kwargs)

            # サーバー管理者なら無条件で実行可能
            if ctx.user.guild_permissions.administrator:
                ctx.extras['restricted'] = False
                return await func(self, ctx, *args, **kwargs)

            cog = ctx.client.get_cog("Settings")

            if not cog:
                ctx.extras['restricted'] = False
                return await func(self, ctx, *args, **kwargs)

            guild_id = ctx.guild.id

            # キャッシュを利用して確認
            if guild_id in cog.cache:
                restricted = cog.cache[guild_id]

            else:
                restricted = await cog.fetch_restricted_commands(guild_id)

            # コマンドが制限されている場合
            if ctx.command.name in restricted:
                ctx.extras['restricted'] = True
                return await func(self, ctx, *args, **kwargs)

            # 親コマンドが制限されている場合
            parent_command = ctx.command.parent

            if parent_command and parent_command.name in restricted:
                ctx.extras['restricted'] = True
                return await func(self, ctx, *args, **kwargs)

            ctx.extras['restricted'] = False
            return await func(self, ctx, *args, **kwargs)

        except Exception:
            import traceback
            print(traceback.format_exc())

    return wrapper
