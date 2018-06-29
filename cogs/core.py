import json
import os

import discord
from discord.ext import commands

import basicbot
import helper


class Core:
    def __init__(self, bot: basicbot.BasicBot):
        self.bot = bot
        self._last_result = None
        if os.path.isfile('prefixes.json'):
            with open('prefixes.json') as file_in:
                self.prefixes = json.load(file_in)
        else:
            self.prefixes = {}

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
        self.prefixes.setdefault(str(ctx.guild.id), []).append(prefix)
        with open('prefixes.json', "w") as file_out:
            json.dump(self.prefixes, file_out)
        if not await helper.react_or_false(ctx):
            await ctx.send("Added the prefix")

    @commands.command()
    async def removeprefix(self, ctx, prefix: str):
        """Removes prefix for the bot from this server"""
        if not self.prefixes:
            await ctx.send("No prefixes to remove")
            return
        if not (ctx.author.guild_permissions.administrator or self.bot.is_owner(ctx.author)):
            raise commands.CheckFailure("You can't change the prefix")
        self.prefixes.setdefault(str(ctx.guild.id), []).remove(prefix)
        with open('prefixes.json', "w") as file_out:
            json.dump(self.prefixes, file_out)
        if not await helper.react_or_false(ctx):
            await ctx.send("Removed the prefix")


def setup(bot):
    import importlib
    for v in globals().values():
        try:
            importlib.reload(v)
        except TypeError:
            pass
    bot.add_cog(Core(bot))
