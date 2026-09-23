"""
Passive presence: Vida noticing when someone needs her, without being asked.

- No unprompted chatter: she only ever speaks in response to a real message
  from someone in the channel.
- Only three trigger phrases: her name, "i don't feel well" and "can't
  sleep" - kept short so the ghosts don't pile onto the channel, and picked
  because they're unmistakably hers: she's the one who drifts toward
  whoever is quietly hurting. None overlap the other ghosts' triggers.
- Whole-word/whole-phrase matching, so nothing fires inside an unrelated word.
- Remembering what members say, and condensing recent activity into running
  notes about what's going on in the server.
- Extra, gentler attention on anyone she's been asked to /tend.

Vida does not talk to the other ghosts - not even Cassy. She ignores every
bot entirely, so there's no way for her to get drawn into a ghost
conversation.
"""

import asyncio
import logging
import os
import random
import re

import discord
from discord.ext import commands

log = logging.getLogger("vashara.haunting")


def _parse_channel_ids(env_value: str | None):
    if not env_value:
        return None
    ids = set()
    for part in env_value.split(","):
        part = part.strip()
        if part.isdigit():
            ids.add(int(part))
    return ids or None


# keyword -> (chance of reacting, cue). Her name, and two phrases that are
# unmistakably a call for her specifically - someone unwell, someone who
# can't sleep. Nothing overlapping the other ghosts' words.
KEYWORD_TRIGGERS = {
    "vida": (1.0, "Someone said your name. Light up and turn your attention to them, warmly and fully - the way you always do."),
    "i don't feel well": (1.0, "Someone just said they don't feel well. This is exactly what draws you - go to them, in your own quiet way, and ask after them properly."),
    "can't sleep": (1.0, "Someone said they can't sleep. Offer the kind of company that makes a quiet room feel less empty - no fuss, no lecture, just presence."),
}

_KEYWORD_PATTERNS = {
    kw: re.compile(r"\b" + re.escape(kw) + r"\b", re.IGNORECASE) for kw in KEYWORD_TRIGGERS
}


def match_keyword(content: str, rng=random):
    """First keyword that appears as a whole word/phrase and wins its dice roll."""
    text = (content or "").replace("’", "'")
    for keyword, (chance, cue) in KEYWORD_TRIGGERS.items():
        if _KEYWORD_PATTERNS[keyword].search(text):
            if chance >= 1.0 or rng.random() < chance:
                return keyword, cue
            return keyword, None   # heard it, chose to stay quiet
    return None, None


class Haunting(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.allowed_channel_ids = _parse_channel_ids(os.getenv("HAUNT_CHANNEL_IDS"))

    async def _write_notes_safely(self, personality):
        try:
            await personality.update_notes()
        except Exception:
            log.exception("Failed to update server notes")

    async def _resolve_reply_chain(self, message: discord.Message, limit: int = 3):
        """Walk up a Discord reply chain from `message`, nearest first."""
        chain = []
        current = message
        for _ in range(limit):
            ref = getattr(current, "reference", None)
            if not ref:
                break
            original = ref.resolved if isinstance(ref.resolved, discord.Message) else None
            if original is None and ref.message_id:
                try:
                    original = await current.channel.fetch_message(ref.message_id)
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    break
            if original is None:
                break
            chain.append(original)
            current = original
        return chain

    async def _maybe_answer_direct_address(self, message: discord.Message, personality) -> bool:
        """A reply to something Vida said, or an @mention, always gets a
        real answer, with the exchange passed as genuine conversation turns
        so she never doubts her own earlier words."""
        me = self.bot.user
        if me is None:
            return False

        chain = await self._resolve_reply_chain(message)
        replying_to_me = bool(chain) and chain[0].author.id == me.id
        mentioned = any(u.id == me.id for u in message.mentions)
        if not (replying_to_me or mentioned):
            return False

        author_name = str(message.author.display_name)
        asked = re.sub(r"<@!?&?\d+>", "", message.content or "").strip()
        if not asked:
            return False

        history = []
        for msg in reversed(chain):
            text = (msg.content or "").strip()
            if not text:
                continue
            if msg.author.id == me.id:
                history.append({"role": "assistant", "content": text})
            else:
                history.append({"role": "user", "content": f"{msg.author.display_name}: {text}"})

        if replying_to_me:
            direction = (
                "Someone has just replied directly to something you said, and their reply is the last "
                "message above. Answer them, in character, carrying on naturally from your own last "
                "message. Everything above is a real exchange you were part of - never say you don't "
                "remember it, never question whether you said it, and never apologise or break character "
                "to explain yourself. Keep it to a couple of sentences."
            )
        else:
            direction = "Someone has just spoken to you directly, by name. Answer them in character, briefly."

        async with message.channel.typing():
            line = await personality.speak(
                f"{author_name}: {asked}", max_tokens=200, history=history, direction=direction,
            )
        try:
            await message.reply(line, mention_author=False)
        except discord.HTTPException:
            log.exception("Failed to answer direct address in %s", message.channel.id)
        return True

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Vida keeps to the students. Other ghosts, and every other bot,
        # simply don't register.
        if message.author.bot or not message.guild:
            return
        if self.allowed_channel_ids and message.channel.id not in self.allowed_channel_ids:
            return

        personality = self.bot.get_cog("Personality")
        if not personality:
            return
        personality.maybe_shift_mood()

        content = message.content or ""
        author_name = str(message.author.display_name)

        if len(content.strip()) >= 12:
            if personality.remember(author_name, content, message.channel.id):
                asyncio.create_task(self._write_notes_safely(personality))

        if await self._maybe_answer_direct_address(message, personality):
            return

        keyword, matched_cue = match_keyword(content)
        tended = personality.is_haunted(message.author.id)

        cue = None
        if matched_cue:
            cue = f'{matched_cue} They said: "{content}"'
        elif keyword:
            return   # a keyword she chose to let pass - don't fall through to a random aside
        elif tended and random.random() < 0.35:
            cue = (
                f"You've been quietly keeping an eye on {author_name} lately - someone you're tending to. "
                f'They just said: "{content}". Notice it the way you always do: warm and bright, never '
                "intrusive, never clinical."
            )
        elif random.random() < 0.01:
            cue = f'Someone said: "{content}". Notice it in passing, briefly, as an aside.'

        if not cue:
            return

        async with message.channel.typing():
            memory_hint = None
            if random.random() < 0.3:
                memory_hint = personality.random_memory(exclude_author=author_name)
            line = await personality.speak(cue, memory_hint=memory_hint)
        try:
            await message.channel.send(line)
        except discord.HTTPException:
            log.exception("Failed to send reaction in %s", message.channel.id)


async def setup(bot: commands.Bot):
    await bot.add_cog(Haunting(bot))
