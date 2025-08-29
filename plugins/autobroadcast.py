import asyncio
from db_file import db
from pyrogram import Client
from config import API_ID, API_HASH, BOT_TOKEN

app = Client("broadcast-bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)


async def send_files_to_user(user_id: int):
    """Send next file to a user every 30 minutes."""
    while True:
        try:
            # get all files
            file_ids = await db.get_all_file_ids()
            if not file_ids:
                await asyncio.sleep(1800)
                continue

            # get user files
            sent_files = await db.get_files(user_id)

            # find next file
            next_file = None
            for f in file_ids:
                if f not in sent_files:
                    next_file = f
                    break

            if not next_file:
                # sab files bhej diye, wait karo jab tak naya file na aaye
                await asyncio.sleep(1800)
                continue

            # send file
            try:
                await app.send_message(user_id, f"📂 Here is your file: {next_file}")

                # mark file as sent
                await db.add_file(user_id, next_file)

            except Exception as e:
                print(f"❌ Failed to send to {user_id}: {e}")

            # wait 30 min before sending next file
            await asyncio.sleep(1800)

        except Exception as e:
            print(f"🔥 Error in loop for user {user_id}: {e}")
            await asyncio.sleep(60)  # retry after 1 min


async def auto_broadcast():
    """Start broadcast tasks for all users."""
    users = await db.get_all_users()
    tasks = []
    for user in users:
        user_id = user["_id"]
        tasks.append(asyncio.create_task(send_files_to_user(user_id)))

    await asyncio.gather(*tasks)


await auto_broadcast()

