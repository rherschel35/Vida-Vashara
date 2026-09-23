"""
Slash commands for talking to Vida directly:

- /ask <question>   - ask Vida something
- /tend <member>     - she takes a particular, gentler interest in someone for a while
- /remedy            - an old memory or remedy from her healing days
- /mood              - (admin) peek at her current mood

There is no /interact. Vida doesn't talk to the other ghosts - not even Cassy.
"""

import json
import logging
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

log = logging.getLogger("vashara.commands")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LORE_PATH = DATA_DIR / "lore.json"

TEND_DURATION_SECONDS = 60 * 60 * 6  # 6 hours


def _load_lore():
    try:
        with open(LORE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        log.exception("Failed to load lore.json")
        return []


class GhostCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.lore = _load_lore()

    def _personality(self):
        return self.bot.get_cog("Personality")

    @app_commands.command(name="ask", description="Ask Vida Vashara a question.")
    @app_commands.describe(question="What do you want to ask her?")
    async def ask(self, interaction: discord.Interaction, question: str):
        personality = self._personality()
        if not personality:
            await interaction.response.send_message("No one's answering right now.", ephemeral=True)
            return

        await interaction.response.defer(thinking=True)

        asker = str(interaction.user.display_name)
        prior = personality.memories_about(asker, limit=1)
        memory_hint = prior[0] if prior else None

        cue = (
            f'{asker} asks you directly: "{question}". Answer as yourself - warm, present, and genuinely '
            "engaged with what they actually asked."
        )
        line = await personality.speak(cue, memory_hint=memory_hint, max_tokens=220)

        embed = discord.Embed(description=line, color=0x6FA37B)
        embed.set_author(name=f"{asker} asks Vida…")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="tend", description="Ask Vida to take a gentler, closer interest in someone for a while.")
    @app_commands.describe(member="Who should she look in on?")
    async def tend(self, interaction: discord.Interaction, member: discord.Member):
        personality = self._personality()
        if not personality:
            await interaction.response.send_message("No response right now.", ephemeral=True)
            return
        if member.bot:
            await interaction.response.send_message(
                "The other spirits don't need tending. Her attention belongs to the living.", ephemeral=True
            )
            return

        personality.set_haunt_target(member.id, TEND_DURATION_SECONDS)

        cue = (
            f"You've just been asked to look in on {member.display_name} for a while - to notice how "
            "they're actually doing. Announce it in character: warm, delighted to have a reason to check in, entirely without fuss. "
            "This is simply what you do."
        )
        line = await personality.speak(cue, max_tokens=150)

        embed = discord.Embed(description=line, color=0x6FA37B)
        embed.set_footer(text=f"Vida is quietly looking in on {member.display_name}.")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="remedy", description="Hear an old memory or remedy from Vida's healing days.")
    async def remedy(self, interaction: discord.Interaction):
        personality = self._personality()
        if not personality:
            await interaction.response.send_message("Nothing comes to mind tonight.", ephemeral=True)
            return

        await interaction.response.defer(thinking=True)

        fragment = personality.next_lore_fragment(self.lore)
        if fragment is None:
            line = await personality.speak(
                "Someone has asked for another old memory or remedy, but you've shared every one you're "
                "willing to share for now. Deflect, in character, gently - there will be more, another "
                "time - without saying you've run out.",
                max_tokens=120,
            )
            await interaction.followup.send(embed=discord.Embed(description=line, color=0x5A5A5A))
            return

        cue = (
            "Tell whoever's listening about this memory from your healing days, in your own voice - not "
            f'verbatim, but true to it: "{fragment}"'
        )
        line = await personality.speak(cue, max_tokens=220)

        embed = discord.Embed(title="A memory from Vida Vashara…",
                              description=line, color=0x6FA37B)
        remaining = len(self.lore) - personality.state.get("lore_index", 0)
        embed.set_footer(text=f"{remaining} more, for another time.")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="mood", description="(admin) Peek at Vida's current mood.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def mood(self, interaction: discord.Interaction):
        personality = self._personality()
        if not personality:
            await interaction.response.send_message("No mood to report.", ephemeral=True)
            return
        from cogs.personality import GHOST_NAME
        await interaction.response.send_message(
            f"{GHOST_NAME}'s current mood: `{personality.current_mood()}`", ephemeral=True
        )

    @mood.error
    async def mood_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("You need permission for this one.", ephemeral=True)
        else:
            log.exception("Unhandled error in /mood", exc_info=error)


async def setup(bot: commands.Bot):
    await bot.add_cog(GhostCommands(bot))
