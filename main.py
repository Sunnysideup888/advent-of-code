##########################################
# Advent of Code Bot
# https://adventofcode.com/2025
# 29/11/2025
##########################################
import discord
from discord import app_commands
from discord.ext import commands
import logging
from dotenv import load_dotenv
import requests
import os
from discord.ext import tasks
import datetime
from zoneinfo import ZoneInfo

load_dotenv()
token = os.getenv('DISCORD_TOKEN')

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

AOC_ROLE = "aoc-2025"
AOC_2025 = "aoc-2025"
AOC_LEADERBOARD = "aoc-leaderboard"
AOC_DISCUSSION = "aoc-discussion"
AOC_CHANNELS = (AOC_2025, AOC_LEADERBOARD, AOC_DISCUSSION)
LEADERBOARD_ID = 5160767

# Purpose: Gets the bot ready, logs it so you can be sure, and starts the self timer tasks
@bot.event
async def on_ready():
    print(f"Bot is ready {bot.user.name}")
    if not daily_leaderboard.is_running():
        daily_leaderboard.start()
    if not daily_problem_release.is_running():
        daily_problem_release.start()

########################################## Functionality ##########################################
# Purpose: Returns hello to the user with a mention for debugging purposes
# To run: !hello
@bot.command()
async def hello(ctx):
    if ctx.channel.name not in AOC_CHANNELS:
        return
    await ctx.send(f"Hello {ctx.author.mention}!")

# Purpose: Clears the bot from your global account on Discord
# To run: !clearglobal
@bot.command()
async def clearglobal(ctx):
    bot.tree.clear_commands(guild=None)
    await bot.tree.sync()
    await ctx.send("Removed global one")

# Purpose: Syncs your local code with Discord server. Run everytime you make a change
# To run: !sync
@bot.command()
async def sync(ctx):
    ctx.bot.tree.copy_global_to(guild=ctx.guild)
    synced = await ctx.bot.tree.sync(guild=ctx.guild)
    await ctx.send(f"Synced {len(synced)} command(s) to this server yay")

# Purpose: This is the logic for the /aoc [COMMAND] part
# To run: /aoc [COMMAND]
@bot.tree.command(name="aoc", description="Join, leave or see stats for AOC")
@app_commands.describe(command="Commands: join, leave, stats [NAME], leaderboard")
async def aoc(interaction: discord.Interaction, command: str):
    # if interaction.channel.name not in AOC_CHANNELS:
    #     await interaction.response.send_message(
    #         f"You can only run /aoc commands from `#aoc-2025`, `#aoc-leaderboard` and `#aoc-discussion`",ephemeral=True)
    #     return

    action = command.lower().strip()

    if action == "join":
        role = discord.utils.get(interaction.guild.roles, name=AOC_ROLE)
        if role:
            if role in interaction.user.roles:
                await interaction.response.send_message("You already joined AOC", ephemeral=True)
            else:
                await interaction.user.add_roles(role)

                msg = f"""
                    Welcome to Advent of Code 2025 {interaction.user.mention}\nGet started by making a free account here: https://adventofcode.com/2025/auth/login\nJoin our leaderboard using code `5160767-90e44d7b` here: https://adventofcode.com/2025/leaderboard/private\nYou will be pinged with a daily reminder when new problems come out
                """

                await interaction.response.send_message(msg, ephemeral=True)
                await interaction.channel.send(f"{interaction.user.mention} joined Advent of Code!")
    elif action == "leave":
        role = discord.utils.get(interaction.guild.roles, name=AOC_ROLE)
        if role:
            await interaction.user.remove_roles(role)
            await interaction.response.send_message(f"See you {interaction.user.mention}. Rejoin AOC anytime", ephemeral=True)
    elif action == "leaderboard":
        try:
            leaderboard_text = get_leaderboard_text(5)
            await interaction.response.send_message(leaderboard_text, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Error fetching leaderboard: {e}", ephemeral=True)
    elif action.startswith("stats"):
        parts = command.split()

        if len(parts) < 2:
            await interaction.response.send_message("Please provide a username.\nExample: `stats Name`", ephemeral=True)

        target_name = " ".join(parts[1:]).lower()
        embed = get_stats_user(target_name)
        if embed:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message("That username is not valid. Feel free to manually look for it here: https://adventofcode.com/2025/leaderboard/private/view/5160767", ephemeral=True)

    else:
        await interaction.response.send_message(f"Your command `{action}` is not valid. Try `join`, `leave`, `stats [NAME]`, or `leaderboard`.", ephemeral=True)

# Purpose: Tests the daily leaderboard so you can check it will run
# To run: !test_daily_leaderboard
@bot.command()
async def test_daily_leaderboard(ctx):
    if ctx.channel.name not in AOC_CHANNELS:
        return

    print("Testing daily leaderboard")
    await daily_leaderboard_logic()

# Purpose: Runs the daily leaderboard at a prescheduled time of 10pm Sydney time
# To run: Runs automatically (assuming you have started the server)
SYDNEY = ZoneInfo("Australia/Sydney")
DAILY_LEADERBOARD_TIME = datetime.time(hour=22, minute=00, tzinfo=SYDNEY)
@tasks.loop(time=DAILY_LEADERBOARD_TIME)
async def daily_leaderboard():
    await daily_leaderboard_logic()

async def daily_leaderboard_logic():
    channel = discord.utils.get(bot.get_all_channels(), name=AOC_LEADERBOARD)

    if channel:
        print("Channel exists")
        role = discord.utils.get(channel.guild.roles, name=AOC_ROLE)
        leaderboard_msg = get_leaderboard_text(5)
        today = datetime.date.today().strftime("%A, %d %B %Y")

        final_message = f"""
            Hey {role.mention}!\n\nHere is the leaderboard for {today}\n\n{leaderboard_msg}\nView the full leaderboard here https://adventofcode.com/2025/leaderboard/private/view/5160767
        """

        print(f"Final message is {final_message}")
        await channel.send(final_message)

# Purpose: Runs the daily reminder for the problem
# To run: !test_daily_problem_release
@bot.command()
async def test_daily_problem_release(ctx):
    if ctx.channel.name not in AOC_CHANNELS:
        return

    print("Testing daily problem release")
    await daily_problem_release()

# Purpose: Mentions everyone who is in the @aoc-2025 role that a new problem is released. Typically problems are
#          released at 10am Sydney time
# To run: Runs automatically (assuming you have started the server)
DAILY_PROBLEM_RELEASE_TIME = datetime.time(hour=10, minute=5, tzinfo=SYDNEY)
@tasks.loop(time=DAILY_PROBLEM_RELEASE_TIME)
async def daily_problem_release():
    channel = discord.utils.get(bot.get_all_channels(), name=AOC_2025)

    if channel:
        role = discord.utils.get(channel.guild.roles, name=AOC_ROLE)

        final_message = f"""
            Hey {role.mention}!\n\nBe sure to check out today's newly released problem here: https://adventofcode.com/
        """

        await channel.send(final_message)


########################################## Helper functions ##########################################
# Purpose: Gets the stats of a specific user
# Side effects: Returns None if no user can be found (used for error checking)
def get_stats_user(target_name):
    sorted_members = get_sorted_members()

    for i, member in enumerate(sorted_members):
        m_name = member.get("name", "")
        if m_name and m_name.lower() == target_name:
            rank = i + 1

            embed = discord.Embed(
                title=f"Stats for {m_name}",
                color=discord.Color.blue()
            )
            embed.add_field(name="Rank", value=f"#{rank}", inline=True)
            embed.add_field(name="Stars", value=f"{member.get('stars', 0)}", inline=True)
            embed.add_field(name="Score", value=f"{member.get('local_score', 0)}", inline=True)

            return embed

    return None

# Purpose: Gets data in a JSON format from the public API and cookie (stored in .env)
def get_data():
    URL = f"https://adventofcode.com/2025/leaderboard/private/view/{LEADERBOARD_ID}.json"
    COOKIE = os.getenv('AOC_SESSION')
    if not COOKIE:
        return "There was an error reading the leaderboard"

    response = requests.get(URL, cookies={"session": COOKIE})
    response.raise_for_status()
    data = response.json()

    return data

# Purpose: Gets data then transforms it into a list for easier analysis. Then sorts it by score in descending order.
def get_sorted_members():
    data = get_data()
    members_dictionary = data.get("members", {})
    member_list = list(members_dictionary.values())

    sorted_members = sorted(
        member_list,
        key=lambda x: -x.get("local_score", 0)
    )

    return sorted_members

# Purpose: Gets the text for the leaderboard and formats it.
# Side effects: Will set a players score or stars to -1 if it cannot be found
def get_leaderboard_text(n):
    sorted_members = get_sorted_members()

    leaderboard_text = "**Advent of Code Leaderboard**\n"
    for i, member in enumerate(sorted_members[:n]):
        i += 1
        name = member.get("name")
        score = member.get("local_score", -1)
        stars = member.get("stars", -1)

        if i == 1: number = "🥇"
        elif i == 2: number = "🥈"
        elif i == 3: number = "🥉"
        else: number = f"{i}"

        print(f"Name {name}, Score {score}, Stars: {stars}\n")
        leaderboard_text += f"{number} - {name} - {score} score - {stars} stars\n"

    return leaderboard_text

# Purpose: This runs the actual bot
bot.run(token, log_handler=handler, log_level=logging.DEBUG)