import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
from datetime import datetime
import json
import os
import asyncio

CONFIG_FILE = "like_channels.json"

class LikeCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api_key = "RebelTheLvB09"
        self.api_base = "https://likes.api.freefireofficial.com/api"
        self.session = aiohttp.ClientSession()
        self.config_data = self._load_config()

    def _load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    data.setdefault("servers", {})
                    return data
            except json.JSONDecodeError:
                print("[WARN] Config file corrupt. Resetting.")
        default = {"servers": {}}
        self._save_config(default)
        return default

    def _save_config(self, config=None):
        config = config or self.config_data
        with open(CONFIG_FILE + ".tmp", "w") as f:
            json.dump(config, f, indent=4)
        os.replace(CONFIG_FILE + ".tmp", CONFIG_FILE)

    async def check_channel(self, ctx: commands.Context):
        if ctx.guild is None:
            return False
        allowed = self.config_data["servers"].get(str(ctx.guild.id), {}).get("like_channels", [])
        return str(ctx.channel.id) in allowed

    async def cog_unload(self):
        await self.session.close()

    @commands.hybrid_command(name="setlikechannel", description="Allow/block the use of /like in a specific channel.")
    @commands.has_permissions(administrator=True)
    @app_commands.describe(channel="Channel to toggle access for /like command.")
    async def set_like_channel(self, ctx, channel: discord.TextChannel):
        if not ctx.guild:
            return await ctx.send("This command must be used in a server.", ephemeral=True)

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
    @app_commands.describe(uid="Player UID", region="Region (e.g., bd, eu, us, br)")
    async def like_command(self, ctx, region: str = None, uid: str = None):
        is_slash = ctx.interaction is not None

        if not await self.check_channel(ctx):
            return await ctx.send("❌ This channel is not allowed for `/like`.", ephemeral=is_slash)

        if uid is None and region and region.isdigit():
            uid, region = region, None

        if not uid or not region:
            return await ctx.send("❌ Please provide both region and UID. Example: `/like bd 1234567890`", ephemeral=is_slash)

        url = f"{self.api_base}/{region.lower()}/{uid}?key={self.api_key}"

        try:
            async with ctx.typing():
                async with self.session.get(url) as resp:
                    if resp.status == 404:
                        return await self._player_not_found(ctx, uid, is_slash)
                    if resp.status != 200:
                        return await self._error(ctx, "Error", f"Server returned: {resp.status}", is_slash)

                    data = await resp.json()
                    await self._send_result(ctx, data, uid, region, is_slash)

        except asyncio.TimeoutError:
            await self._error(ctx, "Timeout", "The server took too long to respond.", is_slash)
        except Exception as e:
            print("Unexpected error:", e)
            await self._error(ctx, "Unexpected Error", str(e), is_slash)

    async def _send_result(self, ctx, data, uid, region, ephemeral):
        embed = discord.Embed(
            timestamp=datetime.utcnow(),
            color=0x00FFFF if data.get("status") == 1 else 0xFF0000
        )
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        embed.set_image(url="https://i.imgur.com/K4paoIa.gif")
        embed.set_footer(text="👨‍💻 Developed by Mikey FF Bot Developer Team")

        if data.get("status") == 1:
            res = data["response"]
            nickname = res.get("PlayerNickname", "Unknown").replace("\u3164", " ")
            embed.title = "🔰 REBEL  LIKE  ADDED 🔰"
            embed.description = (
                "✨ **PLAYER INFO** ✨\n"
                f"👤 Nickname       : `{nickname}`\n"
                f"🆔 UID            : `{uid}`\n"
                f"🌍 Region         : `{region.upper()}`\n"
                f"🏅 Player Level   : `{res.get('PlayerLevel', 'N/A')}`\n\n"
                "🔥 **LIKE STATUS** 🔥\n"
                f"📉 Likes Before   : `{res.get('LikesbeforeCommand', 'N/A')}`\n"
                f"✅ Likes Added    : `{res.get('LikesGivenByAPI', 'N/A')}`\n"
                f"📈 Likes After    : `{res.get('LikesafterCommand', 'N/A')}`\n\n"
                "🔐 **API INFO** 🔐\n"
                f"🧾 Remaining Quota : `{res.get('KeyRemainingRequests', 'N/A')}`\n"
                f"🕒 Key Expires At  : `{self._format_time(res.get('KeyExpiresAt'))}`\n\n"
                "💬 Need Help? Join our Discord: https://discord.gg/9yCkYfh3Nh"
            )
        else:
            embed.title = "⚠️ Max Likes Sent Already"
            embed.description = (
                "❌ You've already sent max likes today to this player.\n"
                "Try again tomorrow.\n\n"
                "💬 Need Help? Join our Discord: https://discord.gg/9yCkYfh3Nh"
            )

        await ctx.send(embed=embed, ephemeral=ephemeral)

    async def _player_not_found(self, ctx, uid, ephemeral):
        embed = discord.Embed(
            title="Player Not Found ❌",
            description=f"UID `{uid}` not found or not accessible.\nMake sure it's correct.",
            color=0xE74C3C
        )
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        embed.set_image(url="https://i.imgur.com/K4paoIa.gif")
        await ctx.send(embed=embed, ephemeral=ephemeral)

    async def _error(self, ctx, title, desc, ephemeral):
        embed = discord.Embed(title=title, description=desc, color=0x7289DA)
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        embed.set_image(url="https://i.imgur.com/K4paoIa.gif")
        await ctx.send(embed=embed, ephemeral=ephemeral)

    def _format_time(self, iso_str):
        try:
            dt = datetime.fromisoformat(iso_str)
            return dt.strftime("%d %B %Y, %I:%M %p")
        except:
            return iso_str or "N/A"

async def setup(bot: commands.Bot):
    await bot.add_cog(LikeCommands(bot))
