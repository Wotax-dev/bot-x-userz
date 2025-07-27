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
        self.api_url = "https://async-likes.vercel.app"
        self.session = aiohttp.ClientSession()
        self.cooldowns = {}
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
        # Default fallback
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
            return True
        allowed_channels = self.config_data["servers"].get(str(ctx.guild.id), {}).get("like_channels", [])
        return not allowed_channels or str(ctx.channel.id) in allowed_channels

    async def cog_unload(self):
        await self.session.close()

    # ──────────────── SETLIKECHANNEL COMMAND ──────────────── #

    @commands.hybrid_command(name="setlikechannel", description="Allow or block the use of /like in a specific channel.")
    @commands.has_permissions(administrator=True)
    @app_commands.describe(channel="Channel to toggle access for /like command.")
    async def set_like_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        if not ctx.guild:
            return await ctx.send("This command must be used in a server.", ephemeral=True)

        guild_id = str(ctx.guild.id)
        server_cfg = self.config_data["servers"].setdefault(guild_id, {})
        like_channels = server_cfg.setdefault("like_channels", [])
        channel_id = str(channel.id)

        if channel_id in like_channels:
            like_channels.remove(channel_id)
            message = f" {channel.mention} removed from allowed channels."
        else:
            like_channels.append(channel_id)
            message = f"✅ {channel.mention} is now allowed for `/like`."

        self._save_config()
        await ctx.send(message, ephemeral=True)

    # ──────────────── LIKE COMMAND ──────────────── #

    @commands.hybrid_command(name="like", description="Send likes to a Free Fire player.")
    @app_commands.describe(
        uid="Player UID (numbers only, at least 6 digits)",
        region="Region (e.g., ME, IND, BR, US)"
    )
    async def like_command(self, ctx: commands.Context, region: str = None, uid: str = None):
        is_slash = ctx.interaction is not None

        # Permissions check
        if not await self.check_channel(ctx):
            return await ctx.send(" This command is not available in this channel.", ephemeral=is_slash)

        # Cooldown check
        # cooldown = 30
        # user_id = ctx.author.id
        # last_used = self.cooldowns.get(user_id)
        # if last_used:
        #     remaining = cooldown - (datetime.now() - last_used).seconds
        #     if remaining > 0:
        #         return await ctx.send(
        #             f"⏳ {ctx.author.mention}, please wait `{remaining}`s before retrying.",
        #             ephemeral=is_slash
        #         )
        # self.cooldowns[user_id] = datetime.now()

        # Input validation
        if uid is None and region and region.isdigit():
            uid, region = region, None

        if not region or not uid:
            return await ctx.send("Please specify the region and UID.\nExample: `!like me 12345678`", ephemeral=is_slash)

        region_map = {
            "ind": "ind",
            "br": "nx", "us": "nx", "sac": "nx", "na": "nx"
        }
        region_server = region_map.get(region.lower(), "ag")

        try:
            async with ctx.typing():
                async with self.session.get(f"{self.api_url}/like?uid={uid}&region={region_server}&key=wotax2025") as resp:
                    if resp.status == 404:
                        return await self._send_player_not_found(ctx, uid, ephemeral=is_slash)
                    elif resp.status != 200:
                        print(f"[ERROR] API {resp.status} - {await resp.text()}")
                        return await self._send_api_error(ctx, ephemeral=is_slash)

                    data = await resp.json()
                    await self._build_response_embed(ctx, data, region, is_slash)

        except asyncio.TimeoutError:
            await self._send_error_embed(ctx, "Timeout", "The server did not respond in time.", ephemeral=is_slash)
        except Exception as e:
            print(f"[CRITICAL] Unexpected error: {e}")
            await self._send_error_embed(ctx, "Error", "An unexpected error occurred.", ephemeral=is_slash)

    # ──────────────── EMBED HELPERS ──────────────── #

    async def _build_response_embed(self, ctx: commands.Context, data: dict, region: str, ephemeral: bool):
        embed = discord.Embed(
            title="⚡LIKE BOT BY USERZZZ⚡",
            timestamp=datetime.now(),
            color=0x2ECC71 if data.get("status") == 1 else 0x5865F2
        )
        embed.set_image(url="https://i.imgur.com/xzUP5cS.gif")
       

        if data.get("status") == 1:
            player = data.get("player", {})
            likes = data.get("likes", {})

            embed.description = (
    "**💥 ACCOUNT INFO 💥**\n"
        f"**Player Nickname:** {player.get('nickname', 'Unknown')}\n"
        f"**Player UID:** {player.get('uid', 'Unknown')}\n"
        f"**Region:** {player.get('region', region.upper())}\n\n"
        "**RESULT STATUS**\n"
        f"**Added:** +{likes.get('added_by_api', 0)}\n"
        f"**Before:** {likes.get('before', 'N/A')}\n"
        f"**After:** {likes.get('after', 'N/A')}"
    )
         
        else:
            embed.description = (
               
                f"MAX LIKES\nThis UID has already received the maximum likes today."
            )

        embed.set_footer(text="🕷️DEVELOPED BY USERZZZ🕷️")
        if ctx.guild and ctx.guild.id != 1363548112756539733:
            embed.description += "\n\nJoin for support <3 : https://discord.gg/9yCkYfh3Nh"

        await ctx.send(embed=embed, ephemeral=ephemeral)

    async def _send_player_not_found(self, ctx, uid, ephemeral=True):
        embed = discord.Embed(
            title="Player Not Found",
            description=f"UID `{uid}` not found or inaccessible.\n",
            color=0x7289DA
        )
        embed.add_field(name="Tips", value="• Check the UID\n• Try a different region", inline=False)
        await ctx.send(embed=embed, ephemeral=ephemeral)

    async def _send_api_error(self, ctx, ephemeral=True):
        embed = discord.Embed(
            
            description=f"{ctx.author.mention} Failed to process request — try again later.",
            color=0xF39C12
        )
        embed.set_image(url="https://i.imgur.com/xzUP5cS.gif")
        await ctx.send(embed=embed, ephemeral=ephemeral)

    async def _send_error_embed(self, ctx, title: str, description: str, ephemeral=True):
        embed = discord.Embed(title=title, description=description, color=0x7289DA)
        embed.set_image(url="https://i.imgur.com/xzUP5cS.gif")
        await ctx.send(embed=embed, ephemeral=ephemeral)

# ─────────────────── SETUP FUNCTION ─────────────────── #

async def setup(bot: commands.Bot):
    await bot.add_cog(LikeCommands(bot))
