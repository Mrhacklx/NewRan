import asyncio
import datetime
import time
from pyrogram import Client, filters
from pyrogram.errors import InputUserDeactivated, FloodWait, UserIsBlocked, PeerIdInvalid
from plugins.dbusers import db
from config import ADMINS, IMAGE_PATH


# Global flags & stats
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


# ✅ Send file link to a single user (auto mode)
async def send_file_to_user(user_id, file_id, bot):
    try:
        me = await bot.get_me()
        username = me.username
        link = f"https://t.me/{username}?start={file_id}"
        caption = f"<b>⭕ New File:\n\n🔗 ʟɪɴᴋ :- {link}</b>"

        await bot.send_photo(
            chat_id=user_id,
            photo=IMAGE_PATH,
            caption=caption,
            parse_mode="html"
        )
        await db.add_file(user_id, file_id)   # ✅ log sent file for user
        return True, "Success"

    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await send_file_to_user(user_id, file_id, bot)
    except (InputUserDeactivated, UserIsBlocked, PeerIdInvalid):
        await db.delete_user(int(user_id))
        return False, "Removed"
    except Exception as e:
        print(f"❌ Error sending to {user_id}: {e}")
        return False, "Error"


# ✅ Send message to user (manual broadcast)
async def broadcast_messages(user_id, message):
    try:
        await message.copy(chat_id=user_id)
        return True, "Success"
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await broadcast_messages(user_id, message)
    except (InputUserDeactivated, UserIsBlocked, PeerIdInvalid):
        await db.delete_user(int(user_id))
        return False, "Removed"
    except Exception as e:
        print(f"❌ Error sending broadcast to {user_id}: {e}")
        return False, "Error"


# ✅ Manual broadcast (send replied message to all users)
async def start_broadcast(bot, b_msg, sts=None):
    users = await db.get_all_users()
    total_users = await db.total_users_count()

    start_time = time.time()
    done = success = removed = failed = 0

    async for user in users:
        if "id" not in user:
            failed += 1
            done += 1
            continue

        pti, status = await broadcast_messages(int(user["id"]), b_msg)

        if pti:
            success += 1
        else:
            if status == "Removed":
                removed += 1
            else:
                failed += 1
        done += 1

        if sts and not done % 20:  # update every 20 users
            try:
                await sts.edit(
                    f"📢 Broadcast in progress:\n\n"
                    f"👥 Total: {total_users}\n"
                    f"✅ Success: {success}\n"
                    f"🚫 Removed: {removed}\n"
                    f"⚠️ Failed: {failed}\n"
                    f"Progress: {done}/{total_users}"
                )
            except:
                pass

    time_taken = datetime.timedelta(seconds=int(time.time() - start_time))
    if sts:
        await sts.edit(
            f"✅ Broadcast Completed in {time_taken}.\n\n"
            f"👥 Total: {total_users}\n"
            f"✅ Success: {success}\n"
            f"🚫 Removed: {removed}\n"
            f"⚠️ Failed: {failed}"
        )
    return {"total": total_users, "success": success, "removed": removed, "failed": failed, "time": str(time_taken)}


# 📌 Auto-broadcast (every 30 min, file-by-file with stats)
async def auto_broadcast(bot):
    global auto_broadcast_running, auto_stats
    while auto_broadcast_running:
        try:
            users = await db.get_all_users()
            file_ids = await db.get_all_file_ids()
            total_users = await db.total_users_count()

            if not file_ids:
                await asyncio.sleep(1800)
                continue

            # reset stats for new round
            auto_stats = {
                "total": total_users,
                "done": 0,
                "success": 0,
                "removed": 0,
                "failed": 0,
                "start_time": time.time()
            }

            async for user in users:
                if "id" not in user:
                    auto_stats["failed"] += 1
                    auto_stats["done"] += 1
                    continue

                user_id = int(user["id"])
                sent_files = await db.get_files(user_id)

                # find next file
                next_file = None
                for f in file_ids:
                    if f not in sent_files:
                        next_file = f
                        break

                if not next_file:
                    continue  # all files already sent to this user

                ok, status = await send_file_to_user(user_id, next_file, bot)

                if ok:
                    auto_stats["success"] += 1
                else:
                    if status == "Removed":
                        auto_stats["removed"] += 1
                    else:
                        auto_stats["failed"] += 1
                auto_stats["done"] += 1

            # ⏱️ round completed, prepare stats
            time_taken = datetime.timedelta(seconds=int(time.time() - auto_stats["start_time"]))
            stats_msg = (
                f"📊 <b>Auto Broadcast Round Completed</b>\n\n"
                f"👥 Total Users: {auto_stats['total']}\n"
                f"✅ Success: {auto_stats['success']}\n"
                f"🚫 Removed: {auto_stats['removed']}\n"
                f"⚠️ Failed: {auto_stats['failed']}\n"
                f"⏱️ Time Taken: {time_taken}"
            )

            # send stats to admin
            try:
                await bot.send_message(ADMINS[0], stats_msg)
            except:
                print("⚠️ Could not send stats to admin.")

            # wait 30 minutes before next round
            await asyncio.sleep(1800)

        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"🔥 Auto broadcast error: {e}")
            await asyncio.sleep(60)


# 📌 Manual broadcast command
@Client.on_message(filters.command("broadcast") & filters.user(ADMINS) & filters.reply)
async def broadcast_cmd(bot, message):
    b_msg = message.reply_to_message
    sts = await message.reply_text("🚀 Broadcasting started...")
    await start_broadcast(bot, b_msg, sts)


# 📌 Start auto broadcast
@Client.on_message(filters.command(["autobroadcast", "v"]) & filters.user(ADMINS))
async def start_auto_cmd(bot, message):
    global auto_broadcast_running, auto_broadcast_task
    if auto_broadcast_running:
        return await message.reply_text("⚠️ Auto broadcast already running!")

    auto_broadcast_running = True
    auto_broadcast_task = asyncio.create_task(auto_broadcast(bot))
    await message.reply_text("✅ Auto broadcast started! Sending every 30 minutes.")


# 📌 Stop auto broadcast
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


# 📌 Show live stats
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
