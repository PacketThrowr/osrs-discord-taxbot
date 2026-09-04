"""
NerdyKnights Summer Raid Rush - Tax Channel Bot

Features:
- Designate a control channel:
    @TaxBot admin
    @TaxBot unadmin

- From a control channel:
    @TaxBot post tax #tax-channel
    @TaxBot title <event title>
    @TaxBot tax list
    @TaxBot tax reset
    @TaxBot tax unpin

- In the tax channel:
    @TaxBot <description>; <bonds or gp>; <amount>

  Examples:
    @TaxBot Olmlet from CoX; bonds; 10
    @TaxBot Any HMT purple; gp; 50m

- The poster or a member with the Staff role can:
    ✅ mark a tax claimed
    ❌ withdraw/delete a tax

State persists in:
- $STATE_DIRECTORY/tax_bot_state.json when STATE_DIRECTORY is set
- otherwise next to this script

Discord token:
- Set DISCORD_TOKEN in the environment.
"""

import json
import os
import re

import discord


TOKEN = os.environ.get("DISCORD_TOKEN", "PASTE-TOKEN-HERE")

STATE_DIR = os.environ.get(
    "STATE_DIRECTORY",
    os.path.dirname(os.path.abspath(__file__)),
)
STATE_FILE = os.path.join(STATE_DIR, "tax_bot_state.json")

STAFF_ROLE_NAME = "Staff"
CLAIM_EMOJI = "✅"
CANCEL_EMOJI = "❌"

DEFAULT_EVENT_TITLE = ":sunny: NerdyKnights Summer Raid Rush :sunny:"


def build_tax_header(state):
    """
    Build the standard tax instructions using the event title saved in state.
    Only the first line/title is customizable from Discord.
    """
    event_title = state.get("event_title", DEFAULT_EVENT_TITLE).strip()
    if not event_title:
        event_title = DEFAULT_EVENT_TITLE

    return (
        f"# {event_title}\n"
        "💰 **TAXES** 💰\n"
        "To post a tax: **type** an @ mention of the bot (pick it from the popup — "
        "don't copy/paste this message, pasted mentions don't work!), then:\n"
        "`<description>; <bonds or gp>; <amount>`\n"
        "For example, after tagging the bot, type: "
        "`Olmlet from CoX or Sanguine Ornament Kit from HMT; bonds; 10`\n"
        "\n"
        "The poster (or Staff) reacts ✅ on a tax to mark it claimed, "
        "or ❌ to withdraw it.\n"
        "🎉 **All claimed taxes will be added to a giveaway at the end of the event!**"
    )


# ---------------------------------------------------------------------------
# State format:
#
# {
#   "event_title": ":sunny: NerdyKnights Summer Raid Rush :sunny:",
#   "tax_channel_id": "1234567890",
#   "header_message_id": 1234567890,
#   "taxes": {
#       "<message_id>": {
#           "poster_id": 123,
#           "poster_name": "Even",
#           "description": "...",
#           "currency": "bonds" | "gp",
#           "amount": 10,
#           "claimed": false
#       }
#   },
#   "admin_channels": ["1234567890"]
# }
# ---------------------------------------------------------------------------

def default_state():
    return {
        "event_title": DEFAULT_EVENT_TITLE,
        "tax_channel_id": None,
        "header_message_id": None,
        "taxes": {},
        "admin_channels": [],
    }


def load_state():
    if not os.path.exists(STATE_FILE):
        return default_state()

    with open(STATE_FILE, "r", encoding="utf-8") as f:
        state = json.load(f)

    state.setdefault("event_title", DEFAULT_EVENT_TITLE)
    state.setdefault("tax_channel_id", None)
    state.setdefault("header_message_id", None)
    state.setdefault("taxes", {})
    state.setdefault("admin_channels", [])
    return state


def save_state(state):
    os.makedirs(STATE_DIR, exist_ok=True)
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except OSError as exc:
        print(f"[FATAL] Could not write state to {STATE_FILE}: {exc}")
        raise


def is_staff(member):
    return any(
        role.name.lower() == STAFF_ROLE_NAME.lower()
        for role in getattr(member, "roles", [])
    )


def fmt_gp(value):
    return f"{value:,}"


def parse_gp(text):
    """Parse 51234 / 51,234 / 51k / 1.2m -> integer GP."""
    text = (
        text.lower()
        .strip()
        .replace(",", "")
        .replace("gp", "")
        .strip()
    )

    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([km]?)", text)
    if not match:
        return None

    number = float(match.group(1))
    suffix = match.group(2)

    if suffix == "k":
        number *= 1_000
    elif suffix == "m":
        number *= 1_000_000

    return int(number)


def parse_tax(content):
    """
    Parse:
        <description>; <bonds|gp>; <amount>

    Returns:
        (description, currency, amount)
    or:
        None
    """
    parts = [part.strip() for part in content.split(";")]
    if len(parts) != 3:
        return None

    description, currency, amount_text = parts
    currency = currency.lower().rstrip(".")

    if currency in ("bond", "bonds"):
        currency = "bonds"
        amount_clean = amount_text.replace(",", "").strip()
        if not re.fullmatch(r"\d+", amount_clean):
            return None
        amount = int(amount_clean)

    elif currency == "gp":
        amount = parse_gp(amount_text)

    else:
        return None

    if not description or amount is None or amount <= 0:
        return None

    return description, currency, amount


def build_tax_post(tax):
    if tax["currency"] == "bonds":
        reward = (
            f"{tax['amount']} bond"
            f"{'s' if tax['amount'] != 1 else ''}"
        )
    else:
        reward = f"{fmt_gp(tax['amount'])} gp"

    if tax.get("claimed"):
        return (
            f"~~💰 **TAX** — posted by <@{tax['poster_id']}>~~\n"
            f"~~{tax['description']}~~\n"
            f"{CLAIM_EMOJI} **CLAIMED** — Reward: {reward}"
        )

    return (
        f"💰 **TAX** — posted by <@{tax['poster_id']}>\n"
        f"{tax['description']}\n"
        f"**Reward: {reward}**"
    )


intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

# user_id -> True while waiting for reset confirmation
pending_reset = set()


async def try_delete(message):
    try:
        await message.delete()
    except (discord.Forbidden, discord.NotFound):
        pass


async def resolve_member(guild, user_id, payload_member=None):
    """Return a Member when possible, including for uncached raw reactions."""
    if payload_member is not None:
        return payload_member

    if guild is None:
        return None

    member = guild.get_member(user_id)
    if member is not None:
        return member

    try:
        return await guild.fetch_member(user_id)
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        return None


async def post_or_repost_header(channel, state):
    """
    Delete the previous tax header if we know about it, then post a fresh one.
    Existing individual tax messages are left alone.
    """
    old_id = state.get("header_message_id")
    if old_id:
        try:
            old_message = await channel.fetch_message(old_id)
            await old_message.delete()
        except (discord.NotFound, discord.Forbidden):
            pass

    new_message = await channel.send(build_tax_header(state))
    state["header_message_id"] = new_message.id
    save_state(state)


async def update_existing_header(state):
    """Edit the existing tax-channel header in place. Returns True if updated."""
    tax_channel_id = state.get("tax_channel_id")
    header_message_id = state.get("header_message_id")

    if not tax_channel_id or not header_message_id:
        return False

    channel = client.get_channel(int(tax_channel_id))
    if channel is None:
        try:
            channel = await client.fetch_channel(int(tax_channel_id))
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return False

    try:
        header_message = await channel.fetch_message(int(header_message_id))
        await header_message.edit(content=build_tax_header(state))
        return True
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        return False


async def send_tax_list(channel, state):
    taxes = state.get("taxes", {})

    open_taxes = []
    claimed_taxes = []
    bond_total = 0
    gp_total = 0

    for tax in taxes.values():
        if tax["currency"] == "bonds":
            reward = (
                f"{tax['amount']} bond"
                f"{'s' if tax['amount'] != 1 else ''}"
            )
        else:
            reward = f"{fmt_gp(tax['amount'])} gp"

        line = (
            f"{tax['description']} — {reward} "
            f"(by {tax['poster_name']})"
        )

        if tax.get("claimed"):
            claimed_taxes.append(line)
            if tax["currency"] == "bonds":
                bond_total += tax["amount"]
            else:
                gp_total += tax["amount"]
        else:
            open_taxes.append(line)

    sections = []

    if open_taxes:
        sections.append(
            "**Open taxes:**\n" + "\n".join(open_taxes)
        )

    if claimed_taxes:
        totals = []
        if bond_total:
            totals.append(
                f"{bond_total} bond{'s' if bond_total != 1 else ''}"
            )
        if gp_total:
            totals.append(f"{fmt_gp(gp_total)} gp")

        total_text = ", ".join(totals) if totals else "0"
        sections.append(
            f"**Claimed taxes** (giveaway total: {total_text}):\n"
            + "\n".join(claimed_taxes)
        )

    await channel.send(
        "\n\n".join(sections) if sections else "No taxes yet."
    )


@client.event
async def on_ready():
    print(f"Logged in as {client.user}")
    print(f"State file: {STATE_FILE}")


@client.event
async def on_message(message):
    if message.author.bot:
        return

    if client.user not in message.mentions:
        return

    content = message.content
    for mention in (
        f"<@{client.user.id}>",
        f"<@!{client.user.id}>",
    ):
        content = content.replace(mention, "")

    content = content.strip()
    lower = content.lower()

    state = load_state()
    channel_id = str(message.channel.id)
    is_admin_channel = channel_id in state["admin_channels"]

    # -----------------------------------------------------------------------
    # Reset confirmation
    # -----------------------------------------------------------------------
    if message.author.id in pending_reset:
        pending_reset.discard(message.author.id)

        if lower in ("yes", "confirm", "y"):
            state["taxes"] = {}
            save_state(state)
            await message.channel.send(
                "All tax records have been reset. "
                "Previously posted tax messages were left in place.",
                delete_after=15,
            )
        else:
            await message.channel.send(
                "Reset cancelled.",
                delete_after=10,
            )
        return

    # -----------------------------------------------------------------------
    # Control channel management
    # -----------------------------------------------------------------------
    if lower == "admin":
        if channel_id not in state["admin_channels"]:
            state["admin_channels"].append(channel_id)
            save_state(state)

        await message.channel.send(
            "This is now a tax control channel.\n"
            "Commands:\n"
            "`post tax #channel`\n"
            "`title <event title>`\n"
            "`tax list`\n"
            "`tax reset`\n"
            "`tax unpin`"
        )
        return

    if lower == "unadmin":
        if channel_id in state["admin_channels"]:
            state["admin_channels"].remove(channel_id)
            save_state(state)
            await message.channel.send(
                "This channel is no longer a control channel.",
                delete_after=10,
            )
        else:
            await message.channel.send(
                "This wasn't a control channel.",
                delete_after=10,
            )
        return

    # -----------------------------------------------------------------------
    # Post/pin the tax channel
    # -----------------------------------------------------------------------
    if lower.startswith("post"):
        words = lower.split()

        if len(words) < 2 or words[1] != "tax":
            await message.channel.send(
                "Use `post tax #channel`.",
                delete_after=15,
            )
            return

        if message.channel_mentions:
            target_channel = message.channel_mentions[0]
        elif is_admin_channel:
            await message.channel.send(
                "Which channel? Mention it: `post tax #tax-channel`.",
                delete_after=15,
            )
            return
        else:
            target_channel = message.channel

        target_id = str(target_channel.id)

        if target_id in state["admin_channels"]:
            await message.channel.send(
                "That's a control channel — pick a different channel.",
                delete_after=15,
            )
            return

        previous_id = state.get("tax_channel_id")
        if previous_id and previous_id != target_id:
            await message.channel.send(
                "A tax channel is already configured. "
                "Use `tax unpin` from a control channel first.",
                delete_after=15,
            )
            return

        state["tax_channel_id"] = target_id
        save_state(state)

        await post_or_repost_header(target_channel, state)

        if is_admin_channel:
            await message.channel.send(
                f"Posted the tax tracker in {target_channel.mention}.",
                delete_after=10,
            )
        else:
            await try_delete(message)

        return

    # -----------------------------------------------------------------------
    # Commands from control channels
    # -----------------------------------------------------------------------
    if is_admin_channel:
        # Show current event title.
        if lower == "title":
            await message.channel.send(
                f"Current event title:\n# {state.get('event_title', DEFAULT_EVENT_TITLE)}"
            )
            return

        # Set event title. Preserve original case and Discord emoji markup.
        if lower.startswith("title "):
            new_title = content[len("title "):].strip()

            if not new_title:
                await message.channel.send(
                    "Give me a title after `title`.",
                    delete_after=15,
                )
                return

            # Discord messages are limited to 2,000 characters. Validate the
            # complete rendered header rather than only the title.
            test_state = dict(state)
            test_state["event_title"] = new_title
            if len(build_tax_header(test_state)) > 2000:
                await message.channel.send(
                    "That title makes the tax header too long for Discord.",
                    delete_after=15,
                )
                return

            state["event_title"] = new_title
            save_state(state)

            updated = await update_existing_header(state)

            if state.get("tax_channel_id"):
                if updated:
                    reply = "Event title saved and the tax-channel header was updated."
                else:
                    reply = (
                        "Event title saved, but I couldn't edit the existing tax header. "
                        "Run `post tax` again in the tax channel if needed."
                    )
            else:
                reply = "Event title saved. It will be used when the tax channel is posted."

            await message.channel.send(reply, delete_after=20)
            return

        if lower == "tax list":
            await send_tax_list(message.channel, state)
            return

        if lower == "tax reset":
            pending_reset.add(message.author.id)
            await message.channel.send(
                f"{message.author.mention} This will clear **all tax records**. "
                "Previously posted tax messages will stay in place.\n"
                "Mention me with `yes` to confirm."
            )
            return

        if lower == "tax unpin":
            tax_channel_id = state.get("tax_channel_id")

            if not tax_channel_id:
                await message.channel.send(
                    "No tax channel is currently configured.",
                    delete_after=10,
                )
                return

            target_channel = client.get_channel(int(tax_channel_id))

            state["tax_channel_id"] = None
            state["header_message_id"] = None
            save_state(state)

            if target_channel:
                await message.channel.send(
                    f"Removed the tax tracker from {target_channel.mention}. "
                    "Existing messages were left in place.",
                    delete_after=15,
                )
            else:
                await message.channel.send(
                    "Removed the configured tax channel. "
                    "Existing messages were left in place.",
                    delete_after=15,
                )
            return

        await message.channel.send(
            "Tax control commands:\n"
            "`post tax #channel`\n"
            "`title <event title>`\n"
            "`tax list`\n"
            "`tax reset`\n"
            "`tax unpin`",
            delete_after=20,
        )
        return

    # -----------------------------------------------------------------------
    # Tax channel submissions
    # -----------------------------------------------------------------------
    if state.get("tax_channel_id") != channel_id:
        await message.channel.send(
            "This isn't the configured tax channel.",
            delete_after=15,
        )
        return

    parsed = parse_tax(content)
    if not parsed:
        await message.channel.send(
            "Tax format: `<description>; <bonds or gp>; <amount>` — e.g. "
            "`Olmlet from CoX; bonds; 10` or "
            "`Any HMT purple; gp; 50m`.",
            delete_after=20,
        )
        return

    description, currency, amount = parsed

    tax = {
        "poster_id": message.author.id,
        "poster_name": message.author.display_name,
        "description": description,
        "currency": currency,
        "amount": amount,
        "claimed": False,
    }

    tax_message = await message.channel.send(build_tax_post(tax))
    await tax_message.add_reaction(CLAIM_EMOJI)
    await tax_message.add_reaction(CANCEL_EMOJI)

    state.setdefault("taxes", {})[str(tax_message.id)] = tax
    save_state(state)

    await try_delete(message)


@client.event
async def on_raw_reaction_add(payload):
    if client.user is None or payload.user_id == client.user.id:
        return

    emoji = str(payload.emoji)
    if emoji not in (CLAIM_EMOJI, CANCEL_EMOJI):
        return

    state = load_state()

    if state.get("tax_channel_id") != str(payload.channel_id):
        return

    tax = state.get("taxes", {}).get(str(payload.message_id))
    if not tax:
        return

    channel = client.get_channel(payload.channel_id)
    if channel is None:
        return

    try:
        message = await channel.fetch_message(payload.message_id)
    except (discord.NotFound, discord.Forbidden):
        return

    guild = client.get_guild(payload.guild_id) if payload.guild_id else None
    member = await resolve_member(guild, payload.user_id, payload.member)

    authorized = (
        member is not None
        and (
            member.id == tax["poster_id"]
            or is_staff(member)
        )
    )

    if not authorized:
        if member is not None:
            try:
                await message.remove_reaction(payload.emoji, member)
            except discord.Forbidden:
                pass
        return

    # -----------------------------------------------------------------------
    # Claim
    # -----------------------------------------------------------------------
    if emoji == CLAIM_EMOJI:
        if tax.get("claimed"):
            return

        tax["claimed"] = True
        save_state(state)

        try:
            await message.edit(content=build_tax_post(tax))
        except discord.Forbidden:
            pass

        return

    # -----------------------------------------------------------------------
    # Withdraw/delete
    # -----------------------------------------------------------------------
    if emoji == CANCEL_EMOJI:
        state["taxes"].pop(str(payload.message_id), None)
        save_state(state)
        await try_delete(message)


if __name__ == "__main__":
    if not TOKEN or TOKEN == "PASTE-TOKEN-HERE":
        raise RuntimeError(
            "DISCORD_TOKEN is not set. "
            "Set it in the environment before starting the bot."
        )

    client.run(TOKEN)
