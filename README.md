# OSRS Discord Tax Bot

A standalone Discord bot for managing **tax rewards** during NerdyKnights OSRS clan competitions.

Members post taxes directly into a designated Discord channel by tagging the bot and supplying a description, reward type, and amount. The bot converts the submission into a clean tax post with ✅ and ❌ reactions.

The person who posted the tax — or anyone with the **Staff** Discord role — can mark the tax as claimed or withdraw it.

Claimed taxes are tracked automatically so Staff can see the running giveaway total. All tax records persist across bot restarts and server reboots.

## Features

- Dedicated Discord **tax channel**
- Separate **Staff control channel**
- Post taxes by tagging the bot
- Supports rewards in:
  - Bonds
  - GP
- GP values support convenient formats such as:
  - `50000000`
  - `50,000,000`
  - `50m`
  - `51k`
  - `1.2m`
- Automatically adds:
  - ✅ Claim reaction
  - ❌ Withdraw reaction
- Only the original poster or someone with the **Staff** role can claim or withdraw a tax
- Unauthorized reactions are automatically removed
- Claimed taxes are struck through and marked **CLAIMED**
- Staff can list:
  - Open taxes
  - Claimed taxes
  - Total claimed bonds
  - Total claimed GP
- Persistent state in `/var/lib/taxbot/`
- Runs cleanly under systemd using `DynamicUser=yes`
- Automatically restarts after crashes or server reboots

---

## Tax Format

Members post taxes by tagging the bot in the configured tax channel:

```text
@taxbot <description>; <bonds or gp>; <amount>
```

Examples:

```text
@taxbot Olmlet from CoX; bonds; 10
```

```text
@taxbot Sanguine Ornament Kit from HMT; bonds; 5
```

```text
@taxbot Any HMT purple; gp; 50m
```

```text
@taxbot Shadow split; gp; 125m
```

The bot deletes the original submission and replaces it with a formatted tax post:

```text
💰 TAX — posted by @Player
Olmlet from CoX
Reward: 10 bonds
```

It then adds:

```text
✅ ❌
```

## Claiming and Withdrawing Taxes

The person who originally posted the tax can manage it using reactions.

Members with the Discord role:

```text
Staff
```

can manage any tax.

### ✅ Claim

React with:

```text
✅
```

The tax is marked claimed and changed to something similar to:

```text
💰 TAX — posted by @Player
Olmlet from CoX
✅ CLAIMED — Reward: 10 bonds
```

The description and header are struck through in Discord.

Claimed taxes remain in the bot's state and are included in the giveaway totals.

### ❌ Withdraw

React with:

```text
❌
```

The tax is removed from the bot's state and the Discord tax message is deleted.

---

## Discord Commands

Commands work by tagging the bot.

### Control Channel

First designate a Staff/control channel:

```text
@taxbot admin
```

The current channel becomes a control channel.

To remove it:

```text
@taxbot unadmin
```

Multiple control channels can be configured if needed.

### Configure the Tax Channel

From a control channel:

```text
@taxbot post tax #tax-channel
```

Example:

```text
@taxbot post tax #raids-taxes
```

The bot posts the tax instructions into that channel and records it as the active tax channel.

You can also run:

```text
@taxbot post tax
```

from inside the tax channel itself.

Only one active tax channel is configured at a time.

### Change the Event Title

From a control channel, change the event title without editing the Python file:

```text
@taxbot title NerdyKnights Fall Raid Rush
```

The new title is saved in `tax_bot_state.json` and the existing tax-channel header is updated immediately. The title persists across bot restarts.

To display the current title:

```text
@taxbot title
```

The bot also accepts:

```text
@taxbot tax title NerdyKnights Fall Raid Rush
```

### List Taxes

From a control channel:

```text
@taxbot tax list
```

The bot displays open and claimed taxes.

Example:

```text
Open taxes:

Olmlet from CoX — 10 bonds (by Even)
Any HMT purple — 50,000,000 gp (by Player2)


Claimed taxes (giveaway total: 15 bonds, 100,000,000 gp):

Shadow split — 5 bonds (by Player3)
Sanguine Ornament Kit — 10 bonds (by Player4)
Purple split — 100,000,000 gp (by Player5)
```

Only **claimed** taxes contribute to the giveaway total.

### Reset All Taxes

From a control channel:

```text
@taxbot tax reset
```

The bot asks for confirmation.

Respond by tagging the bot:

```text
@taxbot yes
```

This clears the bot's tax records.

Previously posted Discord tax messages are intentionally left in place.

### Unpin the Tax Channel

From a control channel:

```text
@taxbot tax unpin
```

This removes the configured tax channel from the bot.

Existing Discord messages are left untouched.

You can then configure another tax channel:

```text
@taxbot post tax #new-tax-channel
```

---

## Discord Application Setup

### 1. Create the Discord Application

Create an application at:

https://discord.com/developers/applications

Open the application and go to the **Bot** tab.

### 2. Enable Message Content Intent

Under **Privileged Gateway Intents**, enable:

**Message Content Intent**

This is required.

Without it, the bot can receive the mention but cannot reliably read the command following it.

Reset/copy the bot token for use in the systemd service.

### 3. Configure OAuth2

Go to:

**OAuth2 → URL Generator**

Select the scope:

```text
bot
```

Recommended bot permissions:

- View Channels
- Send Messages
- Read Message History
- Add Reactions
- Manage Messages

`Manage Messages` allows the bot to:

- Delete the original member tax submission
- Delete withdrawn tax posts
- Remove unauthorized reactions

Open the generated OAuth2 URL and authorize the bot in your Discord server.

If the tax or Staff channels use custom permission overwrites, make sure the bot's role has these permissions in those specific channels.

> **Tagging tip:** Discord may create a managed role with the same name as the bot. When tagging the bot, select the autocomplete result showing the bot's **avatar**. Role mentions are ignored.

---

# Server Installation

This README assumes the repository is located at:

```text
/repos/osrs-discord-taxbot
```

Adjust the paths if yours differs.

## 1. Clone / Enter the Repo

```bash
cd /repos/osrs-discord-taxbot
```

The main bot script is:

```text
tax_channel_bot.py
```

## 2. Create the Python Virtual Environment

```bash
sudo python3 -m venv venv
```

Install Discord.py:

```bash
sudo ./venv/bin/pip install discord.py
```

Root ownership of the virtual environment is fine. The systemd service only needs to read and execute it.

## 3. Create the systemd Service

Create:

```text
/etc/systemd/system/osrs-discord-taxbot.service
```

Example:

```ini
[Unit]
Description=NerdyKnights Tax Discord Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
DynamicUser=yes
WorkingDirectory=/repos/osrs-discord-taxbot
ExecStart=/repos/osrs-discord-taxbot/venv/bin/python3 /repos/osrs-discord-taxbot/tax_channel_bot.py
Restart=always
RestartSec=5
StateDirectory=taxbot
Environment=DISCORD_TOKEN=your_token_here

[Install]
WantedBy=multi-user.target
```

Replace:

```ini
Environment=DISCORD_TOKEN=your_token_here
```

with the real Discord bot token in the copy under `/etc/systemd/system/`.

> **Never commit the real Discord token to Git.**

A repo copy of the service file should always contain a dummy value.

## 4. Enable and Start the Bot

Reload systemd:

```bash
sudo systemctl daemon-reload
```

Enable and start the bot:

```bash
sudo systemctl enable --now osrs-discord-taxbot
```

Check its status:

```bash
sudo systemctl status osrs-discord-taxbot
```

Watch the logs:

```bash
journalctl -u osrs-discord-taxbot -f
```

You should see something similar to:

```text
Logged in as taxbot#1234
State file: /var/lib/taxbot/tax_bot_state.json
```

---

# Initial Discord Setup

Once the bot is running, go to your Staff/control channel and run:

```text
@taxbot admin
```

Then configure the tax channel:

```text
@taxbot post tax #raids-taxes
```

The bot will post the tax instructions into the tax channel.

Members can now submit taxes with:

```text
@taxbot Olmlet from CoX; bonds; 10
```

or:

```text
@taxbot Any HMT purple; gp; 50m
```

---

# How State Works

The systemd service uses:

```ini
DynamicUser=yes
StateDirectory=taxbot
```

systemd creates and manages:

```text
/var/lib/taxbot
```

The bot stores its state at:

```text
/var/lib/taxbot/tax_bot_state.json
```

This contains:

- Event title
- Configured tax channel
- Tax header message ID
- Configured control channels
- Open taxes
- Claimed taxes
- Original poster IDs
- Reward amounts and currencies

The state persists across:

- Bot restarts
- Application crashes
- Server reboots
- Dynamic systemd UID changes

systemd manages the ownership of the state directory automatically.

## Manual Testing vs systemd

When started through systemd, the environment variable:

```text
STATE_DIRECTORY
```

is automatically provided because of:

```ini
StateDirectory=taxbot
```

Therefore the live bot uses:

```text
/var/lib/taxbot/tax_bot_state.json
```

If you manually start the bot:

```bash
./venv/bin/python3 tax_channel_bot.py
```

`STATE_DIRECTORY` is not set.

The bot therefore falls back to:

```text
/repos/osrs-discord-taxbot/tax_bot_state.json
```

This is a **different state file**.

That means taxes or channel configuration created during manual testing will not appear in the live systemd bot, and vice versa.

---

# Tax State File

The JSON file is named:

```text
tax_bot_state.json
```

A simplified example looks like:

```json
{
  "event_title": "NerdyKnights Summer Raid Rush",
  "tax_channel_id": "123456789012345678",
  "header_message_id": 123456789012345679,
  "taxes": {
    "123456789012345680": {
      "poster_id": 111111111111111111,
      "poster_name": "Even",
      "description": "Olmlet from CoX",
      "currency": "bonds",
      "amount": 10,
      "claimed": false
    }
  },
  "admin_channels": [
    "222222222222222222"
  ]
}
```

Do not edit the live state file while the bot is running unless you know what you're changing.

---

# Staff Role

The bot looks for a Discord role named exactly:

```text
Staff
```

Role matching is case-insensitive.

The setting is near the top of `tax_channel_bot.py`:

```python
STAFF_ROLE_NAME = "Staff"
```

If your server uses a different Staff role name, change it there.

For example:

```python
STAFF_ROLE_NAME = "Raid Staff"
```

Restart the bot after changing it:

```bash
sudo systemctl restart osrs-discord-taxbot
```

---

# Changing the Event Title

The tax instructions are built into the bot. You do **not** need to retype the instructions for each event.

From a configured control channel, set the event title with:

```text
@taxbot title NerdyKnights Summer Raid Rush
```

For another event:

```text
@taxbot title NerdyKnights Fall Raid Rush
```

To show the current title:

```text
@taxbot title
```

The title is stored in `tax_bot_state.json`, survives service and server restarts, and the bot immediately updates the existing tax-channel header message.

The rest of the tax instructions remain unchanged.

---

# Troubleshooting

| Symptom | Cause / Fix |
|---|---|
| Bot ignores mentions | Enable **Message Content Intent** in the Discord Developer Portal and make sure you tagged the bot user rather than its role |
| `PrivilegedIntentsRequired` at startup | Message Content Intent is disabled |
| `ModuleNotFoundError: No module named 'discord'` | Make sure `ExecStart` uses `/repos/osrs-discord-taxbot/venv/bin/python3` and install `discord.py` into that venv |
| Bot says this isn't the configured tax channel | Configure it with `@taxbot post tax #channel` |
| `tax list` doesn't work in a channel | That channel must first be configured with `@taxbot admin` |
| Event title doesn't change | Run `@taxbot title <new title>` from a configured control channel |
| User cannot claim their tax | They must react to the tax post created by the bot, not their original message |
| Staff cannot claim another user's tax | Verify the Discord role is named `Staff`, or update `STAFF_ROLE_NAME` |
| Unauthorized reactions remain | Bot likely lacks **Manage Messages** permission |
| Original tax submission isn't deleted | Bot lacks **Manage Messages** |
| ❌ doesn't delete the tax | Bot lacks Manage Messages, or the reacting user is neither the original poster nor Staff |
| Tax disappeared after restarting | Verify `/var/lib/taxbot/tax_bot_state.json` exists and check the service logs |
| Manual testing has different taxes from the live bot | Manual runs use the repo-local `tax_bot_state.json`; systemd uses `/var/lib/taxbot/tax_bot_state.json` |
| Bot continuously restarts | Run `journalctl -u osrs-discord-taxbot -f` and inspect the Python error |

Logs:

```bash
journalctl -u osrs-discord-taxbot -f
```

Restart:

```bash
sudo systemctl restart osrs-discord-taxbot
```

Status:

```bash
sudo systemctl status osrs-discord-taxbot
```

---

# Repo Layout

```text
osrs-discord-taxbot/
├── tax_channel_bot.py       # Discord tax bot
├── taxbot.service           # Optional repo copy of the systemd unit
├── README.md
├── LICENSE
└── venv/                    # Local virtual environment - not committed
```

Recommended `.gitignore`:

```gitignore
venv/
tax_bot_state.json
__pycache__/
*.pyc
```

The live systemd state file is stored outside the repository at:

```text
/var/lib/taxbot/tax_bot_state.json
```

and should never be committed to Git.
