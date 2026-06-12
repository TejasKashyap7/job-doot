"""One-time script to bulk-leave Telegram spam channels.

Leaves channels where:
  - You have never sent a single message, OR
  - The dialog is pinned in your chat list

Shows recently-joined channels first (priority). Always confirms before leaving.

Usage:
    python tools/telegram_cleanup.py           # 2s delay between leaves
    python tools/telegram_cleanup.py --slow    # batches of 20, 60s pause between

Requires in .env:
    TELEGRAM_API_ID=<number from my.telegram.org>
    TELEGRAM_API_HASH=<hex string from my.telegram.org>
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.tl.types import (
    Channel, Chat,
    InputPeerChannel, InputPeerChat,
)

# Load .env from repo root (two levels up from tools/)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

API_ID = os.getenv("TELEGRAM_API_ID", "")
API_HASH = os.getenv("TELEGRAM_API_HASH", "")
SESSION_PATH = str(Path(__file__).resolve().parent / "session_cleanup")


def _check_env():
    if not API_ID or not API_HASH:
        print("ERROR: TELEGRAM_API_ID and TELEGRAM_API_HASH must be set in .env")
        print("Get them from: https://my.telegram.org → API development tools")
        sys.exit(1)


async def _get_join_date(client: TelegramClient, entity) -> datetime | None:
    """Best-effort: works for supergroups. Returns None for broadcast channels."""
    try:
        from telethon.tl.functions.channels import GetParticipantRequest
        result = await client(GetParticipantRequest(entity, "me"))
        return getattr(result.participant, "date", None)
    except Exception:
        return None


async def _never_sent(client: TelegramClient, dialog) -> bool:
    """True if no message from 'me' exists in this dialog."""
    async for _ in client.iter_messages(dialog, from_user="me", limit=1):
        return False
    return True


async def collect_candidates(client: TelegramClient) -> list[dict]:
    """Return dialogs that are pinned OR never-chatted-in, newest joined first."""
    print("\nFetching your dialogs... (this may take a minute)")
    candidates = []

    async for dialog in client.iter_dialogs():
        entity = dialog.entity
        # Only channels and groups, skip private DMs and bots
        if not isinstance(entity, (Channel, Chat)):
            continue

        pinned = dialog.pinned
        never_chatted = await _never_sent(client, dialog)

        if not pinned and not never_chatted:
            continue  # you've chatted here and it's not pinned — keep it

        join_date = await _get_join_date(client, entity)
        member_count = getattr(entity, "participants_count", None)

        candidates.append({
            "id":           entity.id,
            "name":         dialog.name,
            "pinned":       pinned,
            "never_chatted": never_chatted,
            "join_date":    join_date,
            "members":      member_count,
            "input_entity": await client.get_input_entity(entity),
        })

    # Sort: recently joined first (None dates go last), pinned ties broken by name
    candidates.sort(
        key=lambda c: (
            c["join_date"] is None,           # None = sort to end
            -(c["join_date"].timestamp() if c["join_date"] else 0),
        )
    )
    return candidates


def _print_table(candidates: list[dict]):
    print(f"\n{'#':<5} {'Name':<40} {'Members':>9}  {'Pinned':>6}  {'Joined':<20}  Reason")
    print("-" * 100)
    for i, c in enumerate(candidates, 1):
        joined = c["join_date"].strftime("%Y-%m-%d") if c["join_date"] else "unknown"
        members = f"{c['members']:,}" if c["members"] else "?"
        pinned = "yes" if c["pinned"] else ""
        reasons = []
        if c["pinned"]:
            reasons.append("pinned")
        if c["never_chatted"]:
            reasons.append("never chatted")
        print(f"{i:<5} {c['name'][:39]:<40} {members:>9}  {pinned:>6}  {joined:<20}  {', '.join(reasons)}")


async def leave_one(client: TelegramClient, candidate: dict, slow: bool, batch_idx: int):
    """Leave a single channel. Handles FloodWaitError automatically."""
    if slow and batch_idx > 0 and batch_idx % 20 == 0:
        print(f"\n  [--slow] Pausing 60s after {batch_idx} leaves to avoid rate-limit...")
        await asyncio.sleep(60)

    while True:
        try:
            await client.delete_dialog(candidate["input_entity"])
            delay = 60 if slow else 2
            await asyncio.sleep(delay)
            return
        except FloodWaitError as e:
            print(f"\n  Telegram flood-wait: sleeping {e.seconds}s...")
            await asyncio.sleep(e.seconds + 2)
        except Exception as ex:
            print(f"\n  Could not leave '{candidate['name']}': {ex}")
            return


async def main(slow: bool):
    _check_env()

    client = TelegramClient(SESSION_PATH, int(API_ID), API_HASH)
    await client.start()  # prompts phone + OTP on first run

    candidates = await collect_candidates(client)

    if not candidates:
        print("\nNo candidates found — nothing to leave.")
        await client.disconnect()
        return

    _print_table(candidates)
    print(f"\nTotal candidates: {len(candidates)}")
    print("\nOptions:")
    print("  A — Leave ALL of the above")
    print("  B — Leave specific numbers (e.g. 1,3,5-10)")
    print("  D — Exit without leaving anything")

    choice = input("\nYour choice: ").strip().upper()

    if choice == "D" or not choice:
        print("Exiting. Nothing was left.")
        await client.disconnect()
        return

    to_leave: list[dict] = []

    if choice == "A":
        to_leave = candidates
    elif choice == "B":
        raw = input("Enter numbers (e.g. 1,3,5-10): ").strip()
        selected_indices: set[int] = set()
        for part in raw.split(","):
            part = part.strip()
            if "-" in part:
                a, b = part.split("-", 1)
                selected_indices.update(range(int(a), int(b) + 1))
            else:
                selected_indices.add(int(part))
        to_leave = [candidates[i - 1] for i in sorted(selected_indices) if 1 <= i <= len(candidates)]
    else:
        print("Unrecognised choice — exiting.")
        await client.disconnect()
        return

    print(f"\nAbout to leave {len(to_leave)} channel(s). Type 'yes' to confirm: ", end="")
    if input().strip().lower() != "yes":
        print("Cancelled.")
        await client.disconnect()
        return

    for idx, c in enumerate(to_leave):
        print(f"  Leaving [{idx + 1}/{len(to_leave)}] {c['name']}...", end=" ", flush=True)
        await leave_one(client, c, slow=slow, batch_idx=idx)
        print("done")

    await client.disconnect()
    print(f"\nDone. Left {len(to_leave)} channel(s).")
    print("\n" + "=" * 60)
    print("ACTION REQUIRED: Delete the session file now:")
    print(f"  rm {SESSION_PATH}.session")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Telegram channel bulk-leave tool")
    parser.add_argument("--slow", action="store_true",
                        help="Leave in batches of 20 with 60s pause (extra conservative)")
    args = parser.parse_args()
    asyncio.run(main(slow=args.slow))
