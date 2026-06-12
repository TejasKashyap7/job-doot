"""One-time script to bulk-delete empty/ghost private DM chats.

Targets:
  - Deleted accounts (ghost icon in Telegram)
  - Contacts where the ONLY exchange is the "X joined Telegram" notification
    and you have never sent a single message

Does NOT touch groups, channels, or any chat where you've sent a message.
Always shows a confirmation list before deleting anything.

Usage:
    python tools/telegram_dms_cleanup.py
    python tools/telegram_dms_cleanup.py --slow   # 60s pause every 20 deletes
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.tl.types import User, MessageService, MessageActionContactSignUp

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

API_ID = os.getenv("TELEGRAM_API_ID", "")
API_HASH = os.getenv("TELEGRAM_API_HASH", "")
SESSION_PATH = str(Path(__file__).resolve().parent / "session_dms_cleanup")


def _check_env():
    if not API_ID or not API_HASH:
        print("ERROR: TELEGRAM_API_ID and TELEGRAM_API_HASH must be set in .env")
        sys.exit(1)


async def _never_sent(client: TelegramClient, dialog) -> bool:
    async for _ in client.iter_messages(dialog, from_user="me", limit=1):
        return False
    return True


def _is_join_notification(dialog) -> bool:
    """True if the last (and likely only) message is 'X joined Telegram'."""
    msg = dialog.message
    return isinstance(msg, MessageService) and isinstance(msg.action, MessageActionContactSignUp)


async def collect_candidates(client: TelegramClient) -> list[dict]:
    print("\nFetching your DM dialogs... (this may take a minute)")
    candidates = []

    async for dialog in client.iter_dialogs():
        entity = dialog.entity
        if not isinstance(entity, User):
            continue  # skip groups and channels
        if entity.is_self or entity.bot:
            continue  # skip Saved Messages and bots

        reason = None
        if entity.deleted:
            reason = "deleted account"
        elif _is_join_notification(dialog) and await _never_sent(client, dialog):
            reason = "joined Telegram, never chatted"

        if not reason:
            continue

        name = " ".join(filter(None, [entity.first_name, entity.last_name])) or "?"
        username = f"@{entity.username}" if entity.username else ""
        candidates.append({
            "name":         name,
            "username":     username,
            "reason":       reason,
            "input_entity": await client.get_input_entity(entity),
        })

    return candidates


def _print_table(candidates: list[dict]):
    print(f"\n{'#':<5} {'Name':<30} {'Username':<20} Reason")
    print("-" * 85)
    for i, c in enumerate(candidates, 1):
        print(f"{i:<5} {c['name'][:29]:<30} {c['username'][:19]:<20} {c['reason']}")


async def delete_one(client: TelegramClient, candidate: dict, slow: bool, batch_idx: int):
    if slow and batch_idx > 0 and batch_idx % 20 == 0:
        print(f"\n  [--slow] Pausing 60s after {batch_idx} deletes...")
        await asyncio.sleep(60)

    while True:
        try:
            await client.delete_dialog(candidate["input_entity"])
            await asyncio.sleep(60 if slow else 2)
            return
        except FloodWaitError as e:
            print(f"\n  Flood-wait: sleeping {e.seconds}s...")
            await asyncio.sleep(e.seconds + 2)
        except Exception as ex:
            print(f"\n  Could not delete '{candidate['name']}': {ex}")
            return


async def main(slow: bool):
    _check_env()

    client = TelegramClient(SESSION_PATH, int(API_ID), API_HASH)
    await client.start()

    candidates = await collect_candidates(client)

    if not candidates:
        print("\nNo ghost DMs found — nothing to delete.")
        await client.disconnect()
        return

    _print_table(candidates)
    print(f"\nTotal: {len(candidates)} ghost DMs")
    print("\nOptions:")
    print("  A — Delete ALL of the above")
    print("  B — Delete specific numbers (e.g. 1,3,5-10)")
    print("  D — Exit without deleting anything")

    choice = input("\nYour choice: ").strip().upper()

    if choice == "D" or not choice:
        print("Exiting. Nothing was deleted.")
        await client.disconnect()
        return

    to_delete: list[dict] = []

    if choice == "A":
        to_delete = candidates
    elif choice == "B":
        raw = input("Enter numbers (e.g. 1,3,5-10): ").strip()
        selected: set[int] = set()
        for part in raw.split(","):
            part = part.strip()
            if "-" in part:
                a, b = part.split("-", 1)
                selected.update(range(int(a), int(b) + 1))
            else:
                selected.add(int(part))
        to_delete = [candidates[i - 1] for i in sorted(selected) if 1 <= i <= len(candidates)]
    else:
        print("Unrecognised choice — exiting.")
        await client.disconnect()
        return

    print(f"\nAbout to delete {len(to_delete)} DM(s). Type 'yes' to confirm: ", end="")
    if input().strip().lower() != "yes":
        print("Cancelled.")
        await client.disconnect()
        return

    for idx, c in enumerate(to_delete):
        print(f"  Deleting [{idx + 1}/{len(to_delete)}] {c['name']}...", end=" ", flush=True)
        await delete_one(client, c, slow=slow, batch_idx=idx)
        print("done")

    await client.disconnect()
    print(f"\nDone. Deleted {len(to_delete)} ghost DM(s).")
    print("\n" + "=" * 60)
    print("ACTION REQUIRED: Delete the session file now:")
    print(f"  rm {SESSION_PATH}.session")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Telegram ghost DM cleanup")
    parser.add_argument("--slow", action="store_true",
                        help="Batches of 20 with 60s pause between")
    args = parser.parse_args()
    asyncio.run(main(slow=args.slow))
