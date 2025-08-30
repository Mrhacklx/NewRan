import asyncio
import datetime
import time
from pyrogram.enums import ParseMode
from pyrogram import Client, filters
from pyrogram.errors import InputUserDeactivated, FloodWait, UserIsBlocked, PeerIdInvalid
from plugins.dbusers import db   # <-- your Database class
from config import ADMINS, IMAGE_PATH

# ---------------- Global flags & stats ----------------
auto_broadcast_running = False
auto_broadcast_task = None
auto_stats = {
    "total": 0,
    "done": 0,
    "success": 0,
    "removed": 0,
    "failed": 0,
    "start_time": None
}

# ---------------- Send file link to a single user ----------------
async def send_file_to_user(user_id: int, file_id: str, bot: Client):
    """Send a photo with a link to a user and log it."""
    while True:
        try:
            me = await bot.get_me()
            username = me.username
            link = f"https://t.me/{username}?start={file_id}"
            caption = f"<b>⭕ New File:\n\n🔗 Link: {link}</b>"

            await bot.send_photo(
                chat_id=user_id,
                photo=IMAGE_PATH,
                caption=caption,
                parse_mode=ParseMode.HTML   # ✅ Correct way in Pyrogram v2
            )


            # log the file in user's file list
            await db.safe_add_file_to_user(user_id, file_id)
            return True, "Success"

        except FloodWait as e:
            print(f"💤 FloodWait {e.value}s for user {user_id}")
            await asyncio.sleep(e.value)
        except (InputUserDeactivated, UserIsBlocked, PeerIdInvalid):
            await db.delete_user(user_id)
            await db.delete_user_link(user_id)
            return False, "Removed"
        except Exception as e:
            print(f"❌ Error sending file to {user_id}: {e}")
            return False, "Error"

# ---------------- Manual broadcast ----------------
async def broadcast_message(user_id: int, message, bot: Client):
    """Send a manual broadcast message to a user."""
    while True:
        try:
            await message.copy(chat_id=user_id)
            return True, "Success"
        except FloodWait as e:
            print(f"💤 FloodWait {e.value}s for user {user_id}")
            await asyncio.sleep(e.value)
        except (InputUserDeactivated, UserIsBlocked, PeerIdInvalid):
            await db.delete_user(user_id)
            return False, "Removed"
        except Exception as e:
            print(f"❌ Error broadcasting to {user_id}: {e}")
            return False, "Error"

async def start_manual_broadcast(bot: Client, b_msg, sts=None):
    """Broadcast a message to all users in users collection."""
    users_cursor = await db.get_all_users()
    total_users = await db.total_users_count()

    start_time = time.time()
    done = success = removed = failed = 0

    async for user in users_cursor:
        if "id" not in user:
            failed += 1
            done += 1
            continue

        ok, status = await broadcast_message(user["id"], b_msg, bot)
        done += 1

        if ok:
            success += 1
        elif status == "Removed":
            removed += 1
        else:
            failed += 1

        if sts and done % 20 == 0:
            try:
                await sts.edit(
                    f"📢 Broadcasting...\n"
                    f"👥 Total: {total_users}\n"
                    f"✅ Success: {success}\n"
                    f"🚫 Removed: {removed}\n"
                    f"⚠️ Failed: {failed}\n"
                    f"Progress: {done}/{total_users}"
                )
            except: 
                pass

    elapsed = datetime.timedelta(seconds=int(time.time() - start_time))
    if sts:
        await sts.edit(
            f"✅ Broadcast Completed in {elapsed}.\n\n"
            f"👥 Total: {total_users}\n"
            f"✅ Success: {success}\n"
            f"🚫 Removed: {removed}\n"
            f"⚠️ Failed: {failed}"
        )
    return {"total": total_users, "success": success, "removed": removed, "failed": failed, "time": str(elapsed)}

# ---------------- Auto-broadcast ----------------
async def auto_broadcast(bot: Client):
    global auto_broadcast_running, auto_stats
    while auto_broadcast_running:
        try:
            users_cursor = await db.get_all_users_link()
            file_ids = await db.get_all_file_ids()   # returns list of {"file_id": ...}
            file_ids = [doc["file_id"] for doc in file_ids]
            total_users = await db.total_users_link_count()

            if not file_ids:
                await asyncio.sleep(1800)
                continue

            auto_stats = {
                "total": total_users,
                "done": 0,
                "success": 0,
                "removed": 0,
                "failed": 0,
                "start_time": time.time()
            }

            async for user in users_cursor:
                if "user_id" not in user:
                    auto_stats["failed"] += 1
                    auto_stats["done"] += 1
                    continue

                user_id = user["user_id"]
                sent_files = await db.get_files_of_user(user_id)
                next_file = next((f for f in file_ids if f not in sent_files), None)
                if not next_file:
                    auto_stats["done"] += 1
                    continue

                ok, status = await send_file_to_user(user_id, next_file, bot)
                auto_stats["done"] += 1

                if ok:
                    auto_stats["success"] += 1
                elif status == "Removed":
                    auto_stats["removed"] += 1
                else:
                    auto_stats["failed"] += 1
                    print(f"⚠️ Failed to send file to {user_id}")

            elapsed = datetime.timedelta(seconds=int(time.time() - auto_stats["start_time"]))
            stats_msg = (
                f"📊 <b>Auto Broadcast Round Completed</b>\n\n"
                f"👥 Total Users: {auto_stats['total']}\n"
                f"✅ Success: {auto_stats['success']}\n"
                f"🚫 Removed: {auto_stats['removed']}\n"
                f"⚠️ Failed: {auto_stats['failed']}\n"
                f"⏱️ Time Taken: {elapsed}"
            )
            try:
                await bot.send_message(ADMINS[0], stats_msg)
            except: 
                print("⚠️ Could not send stats to admin.")

            await asyncio.sleep(1800)  # 30 minutes

        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"🔥 Auto broadcast error: {e}")
            await asyncio.sleep(60)

# ---------------- Commands ----------------
@Client.on_message(filters.command("broadcast") & filters.user(ADMINS) & filters.reply)
async def broadcast_cmd(bot, message):
    b_msg = message.reply_to_message
    sts = await message.reply_text("🚀 Broadcasting started...")
    await start_manual_broadcast(bot, b_msg, sts)

@Client.on_message(filters.command(["autobroadcast", "v"]) & filters.user(ADMINS))
async def start_auto_cmd(bot, message):
    global auto_broadcast_running, auto_broadcast_task
    if auto_broadcast_running:
        return await message.reply_text("⚠️ Auto broadcast already running!")

    auto_broadcast_running = True
    auto_broadcast_task = asyncio.create_task(auto_broadcast(bot))
    await message.reply_text("✅ Auto broadcast started! Sending every 30 minutes.")

@Client.on_message(filters.command("stopbroadcast") & filters.user(ADMINS))
async def stop_auto_cmd(bot, message):
    global auto_broadcast_running, auto_broadcast_task
    if not auto_broadcast_running:
        return await message.reply_text("⚠️ Auto broadcast is not running!")

    auto_broadcast_running = False
    if auto_broadcast_task:
        auto_broadcast_task.cancel()
        auto_broadcast_task = None

    await message.reply_text("🛑 Auto broadcast stopped successfully.")

@Client.on_message(filters.command("autostats") & filters.user(ADMINS))
async def show_auto_stats(bot, message):
    global auto_broadcast_running, auto_stats
    if not auto_broadcast_running or not auto_stats["start_time"]:
        return await message.reply_text("⚠️ Auto broadcast is not running!")

    elapsed = datetime.timedelta(seconds=int(time.time() - auto_stats["start_time"]))
    stats_msg = (
        f"📊 <b>Auto Broadcast Live Stats</b>\n\n"
        f"👥 Total Users: {auto_stats['total']}\n"
        f"✅ Success: {auto_stats['success']}\n"
        f"🚫 Removed: {auto_stats['removed']}\n"
        f"⚠️ Failed: {auto_stats['failed']}\n"
        f"📌 Progress: {auto_stats['done']}/{auto_stats['total']}\n"
        f"⏱️ Elapsed: {elapsed}"
    )
    await message.reply_text(stats_msg)
