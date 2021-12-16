"""
Slurpotron - A Discord bot for Cape Town By Night.

Slurpotron crawls through non-excluded channels and tallies posts by individual
users over a given timeframe. It can then issue a detailed activity report or
present a calculated list of character XP.
"""

import math
import json
import os
import re
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

from discord.ext import commands
import discord

# Setup
intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!!", intents=intents)
bot.remove_command('help')


# Configuration and persistence
CONFIG_PATH = "configuration.json"
CONFIGURATION = {}


# HELPER FUNCTIONS
def user_is_staff():
    """Returns true if the user has the Staff role."""
    def predicate(ctx):
        roles = map(lambda role: role.name, ctx.author.roles)
        return "Staff" in roles
    return commands.check(predicate)


def get_threshold():
    """Return the daily post threshold to receive XP."""
    return CONFIGURATION["post_threshold"]


def set_threshold(new_value):
    """Set the posts-per-day threshold."""
    CONFIGURATION["post_threshold"] = new_value
    save_configuration()


def get_name(msg):
    """Get a character's name from a message body."""
    if msg.channel.category is not None and "correspondence" in msg.channel.category.name.lower():
        return "Correspondence"

    message = msg.content.strip()
    if len(message) == 0 or message[0] == "\"" or message in ["-start", "-end"] or re.match(r"\**\w+", message):
        return None

    fence_languages = ["css", "yaml", "http", "arm", "excel", "fix", "ini", "ml", "md"]
    for language in fence_languages:
        message = re.sub(r"```" + language, "", message, re.IGNORECASE)

    message = message.strip()
    match = re.search(r"([A-Za-z ]+)", message)#, re.MULTILINE)

    if match is not None:
        name = match.group(0).strip()
        if len(name) == 0 or len(name.split()) > 4:
            return None
        return name
    return "Unknown"


def get_excluded_channels():
    """Return the list of excluded channels."""
    return CONFIGURATION["excluded_channels"]


def exclude_channels(*channels):
    """Add th echannels to the exclusion list."""
    # Lowercase the categories first
    channels = list(map(lambda category: category.lower(), channels))

    current_exclusion_list = CONFIGURATION["excluded_channels"]
    current_exclusion_list.extend(channels)
    CONFIGURATION["excluded_channels"] = current_exclusion_list

    print(CONFIGURATION)


def get_max_xp():
    """Return the maximum RP XP."""
    return CONFIGURATION["max_xp"]


def set_max_xp(new_value):
    """Set the maximum RP XP."""
    CONFIGURATION["max_xp"] = new_value
    save_configuration()


def load_configuration():
    """Loads the configuration; if it doesn't exist, creates a default configuration."""
    config = None
    if os.path.isfile(CONFIG_PATH):
        with open(CONFIG_PATH) as file:
            config = json.load(file)
    else:
        json_str = """
        {
            "post_threshold": 1,
            "excluded_channels": [],
            "max_xp": 3
        }
        """
        config = json.loads(json_str)

    return config


def save_configuration():
    """Save the configuration."""
    print(CONFIGURATION)
    with open(CONFIG_PATH, "w") as file:
        json.dump(CONFIGURATION, file)


def in_allowed_category(channel):
    """Determines whether a channel is part of an allowed category."""
    if "coord" in channel.name or "rolls" in channel.name: # Kludge; exclude bad channels
        return False

    if channel.category is None:
        return False

    allowed_categories = CONFIGURATION["excluded_channels"]

    category = channel.category.name.lower()
    if "[" in category or "【" in category:
        return False

    for allowed in allowed_categories:
        if allowed in category:
            return True

    return False


async def crawl_channel(channel, start, end):
    """Return a dictionary of posts per user in a given channel."""
    stats = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: 0)))

    async for message in channel.history(limit=None, after=start, before=end):
        # Skip bots
        if message.author.bot:
            continue

        # Make sure the user is still in the server
        if message.guild.get_member(message.author.id) is None:
            print(f"\t\t\tSKIPPING user {message.author.display_name}")
            continue

        user = message.author.name
        char_name = get_name(message)
        if char_name is None:
            char_name = "Unknown"
        post_counts = stats[user][char_name]

        date = message.created_at.date()
        post_counts[date] += 1

        stats[user][char_name] = post_counts

    return stats


async def calculate_xp(statistics):
    """Calculate how much XP each user gets."""
    threshold = get_threshold()
    xp_allotment = {}

    for user, character in statistics.items():
        xp_allotment[user] = {}
        for character, post_counts in character.items():
            xp = sum(map(lambda n: n >= threshold, post_counts.values()))
            xp = math.ceil(xp / 2)
            max_rp_xp = get_max_xp()
            if xp > max_rp_xp:
                xp = max_rp_xp # Max allowable RP XP
            xp_allotment[user][character] = xp

    return xp_allotment


async def print_statistics(ctx, statistics, start_date, end_date):
    """Prints a nicely formatted statistics string."""
    xp = await calculate_xp(statistics)
    entries = []
    for user, chars in xp.items():
        entry = user + ": "
        characters = []
        for character, experience in chars.items():
            if character == "Unknown":
                continue
            characters.append(f"{character} ({experience})")
        entry += " | ".join(characters)
        entries.append(entry)

    entries.sort()

    formatted_statistics = "\n".join(entries)

    date_format = "%A, %b %d, %Y"
    start_date = start_date.strftime(date_format)
    end_date = end_date.strftime(date_format)

    output = f"**Calculated RP XP**\n**Start date:** {start_date}\n**End date:** {end_date}```"
    output += formatted_statistics + "\n```"

    await ctx.reply(output)


# COMMANDS

@bot.command()
@user_is_staff()
async def crawl(ctx, start_date, end_date = None):
    """
    Crawl through the non-excluded channels, pulling messages between the start
    and end dates. If no end date is specified, today's date is used.

    Dates must be given in YYYYMMDD format.
    """

    # Determine the date range
    date_format = r"%Y%m%d"

    try:
        start_date = datetime.strptime(start_date, date_format)

        if end_date is None:
            end_date = datetime.now()
        else:
            end_date = datetime.strptime(end_date, date_format)

        # Set the cutoff to 1800 UTC, which is when sunrise/sundown happens
        start_date += timedelta(hours=18)
        end_date += timedelta(hours=18)
    except ValueError:
        await help(ctx)
        return

    working = await ctx.reply("Working ...")

    all_stats = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: 0)))
    crawled = 0
    for channel in ctx.guild.channels:
        if isinstance(channel, discord.TextChannel) and in_allowed_category(channel):
            channel_stats = await crawl_channel(channel, start_date, end_date)
            crawled += 1
            print(f"Crawled {crawled} channels ({channel.name})")
            for user, character in channel_stats.items():
                for character, post_counts in character.items():
                    for day, count in post_counts.items():
                        all_stats[user][character][day] += count

            # Update the user on progress
            if crawled % 10 == 0:
                await working.edit(content=f"Working ... {crawled} done")

        else:
            print(f"Skipping {channel.name}")

    await print_statistics(ctx, all_stats, start_date, end_date)
    await working.delete()
    print("DONE")


# Configuration commands

@bot.command()
@user_is_staff()
async def include(ctx, *channels: str):
    """Exempt a list of channels from being crawled."""
    exclude_channels(*channels)

    await ctx.reply(f"Allowing {len(channels)} additional categories.\nView with `!!included`.")


@bot.command()
@user_is_staff()
async def included(ctx):
    """Print the list of excluded channels."""
    channels = "\n".join(get_excluded_channels())

    await ctx.reply(f"**Including these category patterns in the XP crawl:**\n\n{channels}")


@bot.command()
@user_is_staff()
async def max_xp(ctx, new_value: Optional[int]):
    """Set a new maximum XP or display the current maximum."""
    if new_value is not None:
        set_max_xp(new_value)
        await ctx.reply(f"Set the maximum RP XP to {new_value}.")
    else:
        max_rp_xp = get_max_xp()
        await ctx.reply(f"The maximum RP XP is {max_rp_xp}.")


@bot.command()
@user_is_staff()
async def daily_threshold(ctx, new_value: Optional[int]):
    """Set or retrieve the daily post threshold."""
    if new_value is not None:
        set_threshold(new_value)
        await ctx.reply(f"Set the daily post threshold to {new_value}.")
    else:
        threshold = get_threshold()
        await ctx.reply(f"The daily post threshold is {threshold}.")


@bot.command()
@user_is_staff()
async def help(ctx):
    """Print the bot invocation instructions."""
    instructions = """
    Instructions:
```
!!crawl <YYYYMMDD> [YYYYMMDD] | Calculate RP XP between two dates
!!include <categories>        | Include a list of categories in the crawl. Exactness not required
!!included                    | Show the categories included in the crawl
!!max_xp [new value]          | Set or view the maximum RP XP
!!daily_threshold [new value] | Set or view the posts required to receive XP
!!help                        | Print this message
```
    """
    await ctx.reply(instructions)


@bot.event
async def on_ready():
    """Set the presence."""
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="everything you do"
        )
    )


# Error handling
@bot.event
async def on_command_error(ctx, error):
    """Print the help message."""
    print(error)
    if not isinstance(error, commands.CommandNotFound):
        await help(ctx)


# Run the bot
if __name__ == "__main__":
    CONFIGURATION = load_configuration()
    bot.run(os.environ["SLURPOTRON_TOKEN"])
