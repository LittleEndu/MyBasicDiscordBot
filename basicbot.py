import asyncio
import concurrent.futures
import datetime
import importlib
import inspect
import itertools
import json
import logging
import os
import os.path
import shutil
import sys
import traceback

import discord
import logbook
from discord.ext import commands

import helper


class BasicBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=_prefix)

        # Get config
        if not os.path.isfile("config.json"):
            shutil.copy('exampleconfig.json', 'config.json')
        with open("config.json") as file_in:
            config = json.load(file_in)
        self.config = config
        self.executor = concurrent.futures.ThreadPoolExecutor()

        # Setup logbook
        if not os.path.isdir("logs"):
            os.makedirs("logs")
        self.logger = logbook.Logger("Control")
        self.logger.handlers.append(
            logbook.FileHandler("logs/" + str(datetime.datetime.now().date()) + ".log", level="TRACE", bubble=True))
        self.logger.handlers.append(logbook.StreamHandler(sys.stderr, level='INFO', bubble=True))
        logging.root.setLevel(logging.INFO)
        self.dms = logbook.Logger("DirectMessage")
        self.dms.handlers.append(
            logbook.FileHandler("logs/" + str(datetime.datetime.now().date()) + ".dms.log", level="TRACE", bubble=True))
        self.dms.handlers.append(logbook.StreamHandler(sys.stderr, level='INFO', bubble=True))

        # Remove default help and add other commands
        self.remove_command("help")
        for i in [self.reload, self.load, self.unload, self.debug, self.loadconfig, self._latency]:
            self.add_command(i)
        self._last_result = None

        # alias for when I might fck up
        self.info = self.logger.info
        self.trace = self.logger.trace

    async def on_ready(self):
        self.logger.info('Logged in as')
        self.logger.info(self.user.name)
        self.logger.info(self.user.id)
        self.logger.info("{} commands".format(len(self.commands)))
        self.logger.info('------')

    async def on_message(self, message: discord.Message):
        if isinstance(message.channel, discord.DMChannel):
            if not message.author == self.user:
                self.dms.info("New DM from {}\n{}".format(message.author, message.content))
            else:
                self.dms.info("Sending a DM to {}\n{}".format(message.channel.recipient, message.content))
        await self.process_commands(message)

    async def get_prefix(self, message: discord.Message):
        if isinstance(message.channel, discord.DMChannel):
            return [
                f'{message.channel.me.mention} ',
                "".join(itertools.takewhile(lambda k: not k.isalnum(), message.content))
            ]  # mention needs to be first to get triggered
        return await super().get_prefix(message)

    async def on_command_error(self, ctx: commands.Context, err):
        if hasattr(ctx.command, "on_error"):
            return
        await helper.handle_error(ctx, err)

    # Commands

    @commands.command(aliases=['reloadall', 'loadall'], hidden=True)
    @commands.is_owner()
    async def reload(self, ctx):
        for ext in set([i.replace("cogs.", "") for i in self.extensions.keys()] + self.config.get('auto_load', [])):
            await self.load_cog(ctx, ext, True)
        await ctx.send("Reloaded already loaded cogs and cogs under auto_load")

    async def load_cog(self, ctx, extension, silent=False):
        self.logger.info("Loading " + extension)
        try:
            importlib.import_module("cogs.{}".format(extension))
        except Exception as err:
            self.logger.error("".join(traceback.format_exception(type(err), err.__cause__, err.__traceback__)))
            await ctx.send("Can not load `{}` -> `{}`".format(extension, err))
            return
        try:
            self.unload_extension("cogs.{}".format(extension))
        except:
            pass
        try:
            self.load_extension("cogs.{}".format(extension))
        except Exception as err:
            self.logger.error("".join(traceback.format_exception(type(err), err.__cause__, err.__traceback__)))
            await ctx.send("\u26a0 Could not load `{}` -> `{}`".format(extension, err))
        else:
            if not silent and not await helper.react_or_false(ctx):
                await ctx.send("Loaded `{}`.".format(extension))

    @commands.command(hidden=True, aliases=['reloadconfig', 'reloadjson', 'loadjson'])
    @commands.is_owner()
    async def loadconfig(self, ctx):
        """
        Reload the config
        """
        try:
            with open("config.json") as file_in:
                config = json.load(file_in)
            self.config = config
            if not await helper.react_or_false(ctx):
                await ctx.send("Successfully loaded config")
        except Exception as err:
            await ctx.send("Could not reload config: `{}`".format(err))

    @commands.command(hidden=True)
    @commands.is_owner()
    async def load(self, ctx, *, extension: str):
        """
        Load an extension.
        """
        await self.load_cog(ctx, extension)

    @commands.command(hidden=True)
    @commands.is_owner()
    async def unload(self, ctx, *, extension: str):
        """Unloads an extension."""
        self.logger.info("Unloading " + extension)
        try:
            self.unload_extension("cogs.{}".format(extension))
        except Exception as err:
            self.logger.error("".join(traceback.format_exception(type(err), err.__cause__, err.__traceback__)))
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
        self.trace(f"Running debug command: {ctx.message.content}")
        env = {
            'bot': self,
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
        if any([(self.config.get(i) in str(result)) if i in self.config.keys() else False
                for i in self.config.get("unsafe_to_expose")]):
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

    @commands.command(name='latency', aliases=['ping', 'marco'])
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def _latency(self, ctx):
        """Reports bot latency"""
        if ctx.invoked_with == 'ping':
            msg = await ctx.send("Pong")
        elif ctx.invoked_with == 'marco':
            msg = await ctx.send("Polo")
        else:
            msg = await ctx.send("\u200b")
        latency = msg.created_at.timestamp() - ctx.message.created_at.timestamp()
        await ctx.send("That took {}ms. Discord reports latency of {}ms".format(int(latency * 1000),
                                                                                int(self.latency * 1000)))

    @_latency.error
    async def latency_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            if self.is_owner(ctx.author):
                await ctx.reinvoke()
                return
        else:
            helper.handle_error(ctx, error)


async def _prefix(bot: BasicBot, message: discord.Message):
    prefixes = []
    if os.path.isfile('prefixes.json'):
        guild_id = message.guild.id
        with open('prefixes.json') as file_in:
            data = json.load(file_in)
        prefixes = data.get(str(guild_id), [])

    return commands.when_mentioned_or(*prefixes)(bot, message)


if __name__ == '__main__':
    bb = BasicBot()
    bb.logger.info("\n\n\n")
    bb.logger.info("Initializing")
    if bb.config.get('token', ""):
        for ex in bb.config.get('auto_load', []):
            try:
                bb.load_extension("cogs.{}".format(ex))
                bb.logger.info("Successfully loaded {}".format(ex))
            except Exception as e:
                bb.logger.info('Failed to load extension {}\n{}: {}'.format(ex, type(e).__name__, e))
        bb.logger.info("Logging in...")
        bb.run(bb.config['token'])
    else:
        bb.logger.info("Please add the token to the config file!")
        asyncio.get_event_loop().run_until_complete(bb.close())
