# Vida Vashara

A Discord bot that plays Vida Vashara, founder of House Vashara — the healer
who never wanted to be one, and the ghost who cared for Mordy Velmora at the
very end of his life. It speaks in character via the Claude API (dynamic, not
canned lines) when someone has spoken — her name, “I don’t feel well,” “can’t
sleep,” replies and mentions, and the occasional aside — remembers things
members say and brings them up later, and answers direct questions through
`/ask`. `/tend` asks her to look in on someone for a while, `/remedy` shares
an old memory from her healing days, and `/mood` is for admins.

The name is configurable via `GHOST_NAME` in `.env` if you ever want to
rename it — it's woven into the system prompt, the bot's Discord presence,
and `/mood`.

This is meant to run as a **separate bot/service** from the other Velmora
ghosts — its own Discord application, its own Railway service — so the
personalities don't collide in the same process. She only ever speaks in
response to someone, and she never talks to the other ghosts — not even
Cassy, whom she has never once addressed directly.

## Setup

1. Create a Discord application + bot at https://discord.com/developers/applications
   - Enable the **Message Content Intent** and **Server Members Intent** under Bot settings.
   - Invite it to your server with the `bot` and `applications.commands` scopes,
     and at least: View Channels, Send Messages, Read Message History, Embed Links.
2. `cp .env.example .env` and fill in `DISCORD_TOKEN` and `ANTHROPIC_API_KEY`.
3. `pip install -r requirements.txt`
4. `python bot.py`

Slash commands sync automatically on startup (guild-instant if you set
`DEV_GUILD_ID` / `ALLOWED_GUILD_IDS` in `.env`, otherwise global sync which
can take up to an hour the first time).

## Commands

- `/ask question:<text>` — ask Vida something; she answers warm and present.
- `/tend user:<@member>` — she takes a gentler interest in someone for a while.
- `/remedy` — an old memory or remedy from her healing days.
- `/mood` — (admin) peek at her current mood, for debugging.

## Structure

```
bot.py                 # entrypoint and client setup
cogs/
  personality.py       # Claude API wrapper + ghost voice/mood/memory
  haunting.py           # passive behaviors: name cues, care phrases, tend asides, memory
  commands.py           # /ask, /tend, /remedy, /mood
  diary.py              # long-term diary memory mixed into personality
data/
  memory_store.json     # persisted member quotes + mood + tend targets (runtime-created)
  lore.json              # healing-day fragments, revealed in order
  velmora_lore.json      # shared Velmora ghost lore
  shared_history.json    # shared stories (Vida keeps none of her own)
```

## Notes

- All dialogue is generated at request time by Claude (Haiku by default,
  configurable via `VASHARA_MODEL`) using a system prompt that defines its
  voice, current mood, and any relevant remembered snippets — nothing is
  hardcoded canned text, though there are graceful fallback lines if the API
  call fails.
- State (mood, memories, tend targets, lore progress) is persisted to a
  small JSON file under `STATE_DIR` (defaults to `data/`) so it survives
  restarts.
- Academy rumors (`/rumor` and the scheduled posts) live in Housecup.
