import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
from datetime import datetime
import json
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

CONFIG_FILE = "like_channels.json"

class LikeCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api_key = "RebelTheLvB09"
        self.api_base = "https://likes.api.freefireofficial.com/api"
        self.session = aiohttp.ClientSession()
        self.config_data = self._load_config()

    def _load_config(self) -> dict:
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    data.setdefault("servers", {})
                    return data
            except json.JSONDecodeError:
                print(f"[WARN] Corrupt config file '{CONFIG_FILE}', resetting.")
        default = {"servers": {}}
        self._save_config(default)
        return default

    def _save_config(self, config: dict = None):
        config = config or self.config_data
        temp_file = CONFIG_FILE + ".tmp"
        with open(temp_file, "w") as f:
            json.dump(config, f, indent=4)
        os.replace(temp_file, CONFIG_FILE)

    async def check_channel(self, ctx: commands.Context) -> bool:
        if ctx.guild is None:
            return False  # block in DMs

        allowed_channels = self.config_data["servers"].get(str(ctx.guild.id), {}).get("like_channels", [])
        return str(ctx.channel.id) in allowed_channels

    async def cog_unload(self):
        await self.session.close()

    @commands.hybrid_command(name="setlikechannel", description="Allow/block the use of /like in a specific channel.")
    @commands.has_permissions(administrator=True)
    @app_commands.describe(channel="Channel to toggle access for /like command.")
    async def set_like_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        if not ctx.guild:
            return await ctx.send("This command must be used in a server.", ephemeral=True)

        if ctx.author != ctx.guild.owner and not ctx.author.guild_permissions.administrator:
            return await ctx.send("❌ Only the server owner or admins can configure this.", ephemeral=True)

        guild_id = str(ctx.guild.id)
        server_cfg = self.config_data["servers"].setdefault(guild_id, {})
        like_channels = server_cfg.setdefault("like_channels", [])
        channel_id = str(channel.id)

        if channel_id in like_channels:
            like_channels.remove(channel_id)
            message = f"❌ {channel.mention} is no longer allowed for `/like`."
        else:
            like_channels.append(channel_id)
            message = f"✅ {channel.mention} is now allowed for `/like`."

        self._save_config()
        await ctx.send(message, ephemeral=True)

    @commands.hybrid_command(name="like", description="Send likes to a Free Fire player.")
    @app_commands.describe(
        uid="Player UID (numbers only, at least 6 digits)",
        region="Region (e.g., bd, eu, br, us)"
    )
    async def like_command(self, ctx: commands.Context, region: str = None, uid: str = None):
        is_slash = ctx.interaction is not None

        if not await self.check_channel(ctx):
            return await ctx.send("❌ You can only use this command in a specific allowed channel.", ephemeral=is_slash)

        if uid is None and region and region.isdigit():
            uid, region = region, None

        if not region or not uid:
            return await ctx.send("❌ Please specify the region and UID.\nExample: `/like bd 2792480170`", ephemeral=is_slash)

        region = region.lower()
        url = f"{self.api_base}/{region}/{uid}?key={self.api_key}"

        try:
            async with ctx.typing():
                async with self.session.get(url) as resp:
                    if resp.status == 404:
                        return await self._send_player_not_found(ctx, uid, ephemeral=is_slash)

                    if resp.status != 200:
                        return await self._send_error_embed(ctx, "Error", f"Unexpected server response: {resp.status}", ephemeral=is_slash)

                    data = await resp.json()
                    await self._build_response_embed(ctx, data, region, uid, is_slash)

        except asyncio.TimeoutError:
            await self._send_error_embed(ctx, "Timeout", "The server did not respond in time.", ephemeral=is_slash)
        except Exception as e:
            print(f"[CRITICAL] Unexpected error: {e}")
            await self._send_error_embed(ctx, "Error", "An unexpected error occurred.", ephemeral=is_slash)

    async def _build_response_embed(self, ctx: commands.Context, data: dict, region: str, uid: str, ephemeral: bool):
        embed = discord.Embed(
            timestamp=datetime.utcnow(),
            color=0x00FFFF if data.get("status") == 1 else 0xFF5555
        )
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        embed.set_image(url="https://i.imgur.com/K4paoIa.gif")
        embed.set_footer(text="👨‍💻 Developed by Mikey FF Bot Developer Team")

        if data.get("status") == 1:
            response = data.get("response", {})
            nickname = response.get("PlayerNickname", "Unknown").replace("\u3164", " ")
            level = response.get("PlayerLevel", "N/A")
            likes_before = response.get("LikesbeforeCommand", "N/A")
            likes_after = response.get("LikesafterCommand", "N/A")
            likes_added = response.get("LikesGivenByAPI", "N/A")

            embed.title = "🔰 REBEL  LIKE  ADDED 🔰"
            embed.description = (
                "✨ **PLAYER INFO** ✨\n"
                f"👤 Nickname       : `{nickname}`\n"
                f"🆔 UID            : `{uid}`\n"
                f"🌍 Region         : `{region.upper()}`\n"
                f"🏅 Player Level   : `{level}`\n\n"
                "🔥 **LIKE STATUS** 🔥\n"
                f"📉 Likes Before   : `{likes_before}`\n"
                f"✅ Likes Added    : `{likes_added}`\n"
                f"📈 Likes After    : `{likes_after}`\n\n"
                "💬 Need Help? Join our Discord: https://discord.gg/9yCkYfh3Nh"
            )
        else:
            embed.title = "⚠️ Max Likes Sent Already"
            embed.description = (
                "❌ You’ve already sent the max likes for this player today.\n"
                "Please try again tomorrow.\n\n"
                "💬 Need Help? Join our Discord: https://discord.gg/9yCkYfh3Nh"
            )

        await ctx.send(embed=embed, ephemeral=ephemeral)

    async def _send_player_not_found(self, ctx, uid, ephemeral=True):
        embed = discord.Embed(
            title="Player Not Found ❌",
            description=f"UID `{uid}` not found or inaccessible.\n\n"
                        "• Make sure the UID is correct.\n"
                        "• Try again with a different region.",
            color=0xE74C3C
        )
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        embed.set_image(url="https://i.imgur.com/K4paoIa.gif")
        embed.add_field(name="Need Help?", value="https://discord.gg/9yCkYfh3Nh", inline=False)
        await ctx.send(embed=embed, ephemeral=ephemeral)

    async def _send_error_embed(self, ctx, title: str, description: str, ephemeral=True):
        embed = discord.Embed(
            title=title,
            description=description,
            color=0x7289DA
        )
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        embed.set_image(url="https://i.imgur.com/K4paoIa.gif")
        embed.add_field(name="Need Help?", value="https://discord.gg/9yCkYfh3Nh", inline=False)
        await ctx.send(embed=embed, ephemeral=ephemeral)

async def setup(bot: commands.Bot):
    await bot.add_cog(LikeCommands(bot))
