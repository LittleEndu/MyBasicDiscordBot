import asyncio
import concurrent.futures
import datetime
import itertools
import json
import logging
import os
import sys

import discord
import logbook
from discord.ext import commands

import helper


class BasicBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=_prefix)

        # Get config
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

        # Remove default help and add reload
        self.remove_command("help")
        self.add_command(self.reload)

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

    # Other functions

    @commands.command()
    @commands.is_owner()
    async def reload(self, ctx):
        import importlib
        for v in globals().values():
            try:
                importlib.reload(v)
            except TypeError:
                pass
        if not await helper.react_or_false(ctx):
            await ctx.send("Reloaded all base modules")


async def _prefix(bot: BasicBot, message: discord.Message):
    # TODO: Actual prefix support
    prefixes = []

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
