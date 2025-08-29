from pyrogram.errors import InputUserDeactivated, FloodWait, UserIsBlocked, PeerIdInvalid
from plugins.dbusers import db
import asyncio, datetime, time


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
    except Exception:
        return False, "Error"


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

        if sts and not done % 20:
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
