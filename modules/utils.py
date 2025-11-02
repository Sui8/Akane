import discord


async def send_error(ctx: discord.Interaction, error_code: str = None, custom_text: str = None, url: str = None, is_followup=False):
    if custom_text:
        text = custom_text

    else:
        text = "システムエラーが発生しました。"

    if error_code:
        text += f"\nサポートサーバーまでお問い合わせください。\nエラーコード: {error_code}"

        if url:
            button = discord.ui.Button(label="サポートサーバー", style=discord.ButtonStyle.link, url=url)
            view = discord.ui.View()
            view.add_item(button)

        else:
            view = None

    else:
        view = None

    embed = discord.Embed(
        title=":x: エラー",
        description=text,
        color=0xff0000)

    if view:
        if is_followup:
            await ctx.followup.send(embed=embed, view=view, ephemeral=True)

        else:
            await ctx.response.send_message(embed=embed, view=view, ephemeral=True)

    else:
        if is_followup:
            await ctx.followup.send(embed=embed, ephemeral=True)

        else:
            await ctx.response.send_message(embed=embed, ephemeral=True)
