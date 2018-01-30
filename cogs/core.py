import asyncio
import importlib
import inspect
import json
import random
import traceback
import os

import aiohttp
import asyncpg
import discord
import io
from PIL import Image
from discord.ext import commands

import helper

import basicbot


class Core:
    def __init__(self, bot: basicbot.BasicBot):
        self.bot = bot
        self._last_result = None

    @commands.command(name='help')
    async def _help(self, ctx):
        owner = ctx.guild.get_member(self.bot.owner_id) or self.bot.get_user(self.bot.owner_id)
        await ctx.send(f"This bot is useless anyway tho....\nJust ask {owner.name} for help instead")

    @commands.command(aliases=['prefix'])
    @commands.bot_has_permissions(embed_links=True)
    async def prefixes(self, ctx):
        """Lists prefixes"""
        if isinstance(ctx.channel, discord.DMChannel):
            await ctx.send("There's no need for any prefix in DMs")
            return
        prefixes = await self.bot.get_prefix(ctx.message)
        mentions = commands.bot.when_mentioned(ctx.bot, ctx.message)
        prefixes = [i for i in prefixes if i not in mentions]
        emb = discord.Embed()
        val = ""
        counter = 0
        for p in prefixes:
            counter += 1
            if p.strip() != p:
                val += '(No <>) **{}.** <{}>\n'.format(counter, p)
            else:
                val += "**{}.** {}\n".format(counter, p)
        if not val:
            val = "No prefixes"
        emb.add_field(name="Prefixes for {} are".format(
            "PMs" if isinstance(ctx.channel, discord.DMChannel) else "this server"),
            value=val.strip())
        emb.set_footer(text="You can also just mention me")
        await ctx.send(embed=emb)

    @commands.command(aliases=['addprefix'])
    async def setprefix(self, ctx: commands.Context, prefix: str):
        """Sets prefix for the bot in this server"""
        if not (ctx.author.guild_permissions.administrator or self.bot.is_owner(ctx.author)):
            raise commands.CheckFailure("You can't change the prefix")
        # TODO: Implement

    @commands.command()
    async def removeprefix(self, ctx, prefix: str):
        """Removes prefix for the bot from this server"""
        if not (ctx.author.guild_permissions.administrator or self.bot.is_owner(ctx.author)):
            raise commands.CheckFailure("You can't change the prefix")
        # TODO: Implement

    @commands.command(hidden=True, aliases=['reloadconfig', 'reloadjson', 'loadjson'])
    @commands.is_owner()
    async def loadconfig(self, ctx):
        """
        Reload the config
        """
        try:
            with open("config.json") as file_in:
                config = json.load(file_in)
            self.bot.config = config
            if not await helper.react_or_false(ctx):
                await ctx.send("Successfully loaded config")
        except Exception as err:
            await ctx.send("Could not load reload config: `{}`".format(err))

    @commands.command(hidden=True)
    @commands.is_owner()
    async def load(self, ctx, *, extension: str):
        """
        Load an extension.
        """
        self.bot.logger.info("Loading " + extension)
        # Lets try importing first to prevent importing something that can not be
        try:
            importlib.import_module("cogs.{}".format(extension))
        except Exception as err:
            self.bot.logger.error("".join(traceback.format_exception(type(err), err.__cause__, err.__traceback__)))
            await ctx.send("Can not load `{}` -> `{}`".format(extension, err))
            return

        try:
            self.bot.unload_extension("cogs.{}".format(extension))
        except:
            pass

        try:
            self.bot.load_extension("cogs.{}".format(extension))
        except Exception as err:
            self.bot.logger.error("".join(traceback.format_exception(type(err), err.__cause__, err.__traceback__)))
            await ctx.send("Could not load `{}` -> `{}`".format(extension, err))
        else:
            if not await helper.react_or_false(ctx):
                await ctx.send("Loaded `{}`.".format(extension))

    @commands.command(hidden=True)
    @commands.is_owner()
    async def unload(self, ctx, *, extension: str):
        """Unloads an extension."""
        self.bot.logger.info("Unloading " + extension)
        try:
            self.bot.unload_extension("cogs.{}".format(extension))
        except Exception as err:
            self.bot.logger.error("".join(traceback.format_exception(type(err), err.__cause__, err.__traceback__)))
            await ctx.send("Could not unload `{}` -> `{}`".format(extension, err))
        else:
            if not await helper.react_or_false(ctx):
                await ctx.send("Unloaded `{}`.".format(extension))

    @commands.command(hidden=True)
    @commands.is_owner()
    async def debug(self, ctx, *, command: str):
        """
        Runs a debug command
        """
        env = {
            'self': self,
            'bot': self.bot,
            'ctx': ctx,
            'channel': ctx.channel,
            'author': ctx.author,
            'guild': ctx.guild,
            'message': ctx.message,
            '_': self._last_result
        }
        env.update(globals())

        has_been_awaited = False
        result_class = None
        try:
            result = eval(command, env)
            if inspect.isawaitable(result):
                result = await result
                has_been_awaited = True
            if result is not None:
                self._last_result = result
        except Exception as err:
            result = repr(err)
            result_class = "{}.{}".format(err.__class__.__module__, err.__class__.__name__)
        if result_class is None:
            result_class = "{}.{}".format(result.__class__.__module__, result.__class__.__name__)
        result_too_big = len(str(result)) > 2000
        if any([(self.bot.config.get(i) in str(result)) if i in self.bot.config.keys() else False
                for i in self.bot.config.get("unsafe_to_expose")]):
            await ctx.send("Doing this would reveal sensitive info!!!")
            return
        else:
            if ctx.channel.permissions_for(ctx.me).embed_links:
                color = discord.Color(0)
                if isinstance(result, discord.Colour):
                    color = result
                emb = discord.Embed(description="{}".format(result)[:2000],
                                    color=color)
                emb.set_footer(text="{} {} {}".format(
                    result_class,
                    "| Command has been awaited" if has_been_awaited else "",
                    "| Result has been cut" if result_too_big else "")
                )
                await ctx.send(embed=emb)
            else:
                await ctx.send("```xl\nOutput: {}\nOutput class: {} {} {}```".format(
                    str(result).replace("`", "\u02cb")[:1500],
                    result_class,
                    "| Command has been awaited" if has_been_awaited else "",
                    "| Result has been cut" if result_too_big else ""))

    @commands.command(aliases=['ping', 'marco'])
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def latency(self, ctx):
        """Reports bot latency"""
        if ctx.invoked_with == 'ping':
            msg = await ctx.send("Pong")
        elif ctx.invoked_with == 'marco':
            msg = await ctx.send("Polo")
        else:
            msg = await ctx.send("\u200b")
        latency = msg.created_at.timestamp() - ctx.message.created_at.timestamp()
        await ctx.send("That took {}ms. Discord reports latency of {}ms".format(int(latency * 1000),
                                                                                int(self.bot.latency * 1000)))

    @latency.error
    async def latency_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            if self.bot.is_owner(ctx.author):
                await ctx.reinvoke()
                return
        else:
            helper.handle_error(ctx, error)


def setup(bot):
    import importlib
    for v in globals().values():
        try:
            importlib.reload(v)
        except TypeError:
            pass
    bot.add_cog(Core(bot))
