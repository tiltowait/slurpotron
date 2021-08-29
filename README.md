# Slurpotron

Slurpotron is a quick-and-dirty Discord bot originally made for *Cape Town by Night*, a Vampire: The Masquerade 5th Edition RP server. This bot calculates the amount of RP XP users should receive for a given time period, based on the following criteria:

* A minimum number of posts required for a day to count
* A list of channel categories eligible for RP XP
* The maximum amount of XP obtainable in the time period

These parameters can be set on a per-server basis. See `!!help` for details.

As configured, Slurpotron halves the amount of active days (rounded up) to calculate earned XP. Channel categories are case-insensitive and fuzzily matched. If there are three channels: `Foo`, `Bar`, and `Foobar`, then `!!include foo` will match `Foo` and `Foobar`.

## Requirements

* [discord.py](https://discordpy.readthedocs.io/en/stable/) 1.7.3 or higher

## Limitations

At this moment, there is no command to clear the list of included channel categories or remove individual channel categories. To do so, `configuration.json` must be deleted or manually edited.
