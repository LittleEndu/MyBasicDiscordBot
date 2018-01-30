import traceback

import math
from discord.ext import commands
import discord.errors


async def handle_error(ctx, err):
    can_send = ctx.channel.permissions_for(ctx.me).send_messages
    if not can_send:
        await react_or_false(ctx, ("\U0001f507",))
    if isinstance(err, commands.errors.CommandOnCooldown):
        if not await react_or_false(ctx, ("\u23f0",)) and can_send:
            await ctx.send("\u23f0 " + str(err))
        return
    if isinstance(err, commands.UserInputError) and can_send:
        await ctx.send("\u274c Bad argument: {}".format(' '.join(err.args)))
    elif isinstance(err, commands.errors.CheckFailure) and can_send:
        await ctx.send("\u274c Check failure. " + str(err))
    elif isinstance(err, commands.errors.CommandNotFound):
        await react_or_false(ctx, ("\u2753",))
    else:
        content = "\u274c Error occurred while handling the command."
        if isinstance(err, commands.errors.CommandInvokeError):
            if isinstance(err.original, discord.errors.HTTPException):
                content = None
        if content:
            await ctx.send(content)
        if ctx.command.name == 'debug':
            return
        ctx.bot.logger.error("{}.{}".format(err.__class__.__module__, err.__class__.__name__))
        ctx.bot.logger.trace("".join(traceback.format_exception(type(err), err, err.__traceback__)))
        ctx.bot.logger.trace("".join(traceback.format_exception(type(err), err.__cause__, err.__cause__.__traceback__)))


async def react_or_false(ctx, reactions=("\u2705",)):
    if ctx.channel.permissions_for(ctx.me).add_reactions:
        for r in reactions:
            try:
                await ctx.message.add_reaction(r)
            except:
                continue
        return True
    return False


def ci_score(ratings: list):
    pos = sum([ratings[i] * i / (len(ratings) - 1) for i in range(1, len(ratings))])
    n = sum([i for i in ratings])
    return ci(pos, n) * 10


def ci(pos, n):
    z = 1.96
    phat = 1.0 * pos / n

    return (phat + z * z / (2 * n) - z * math.sqrt((phat * (1 - phat) + z * z / (4 * n)) / n)) / (1 + z * z / n)
