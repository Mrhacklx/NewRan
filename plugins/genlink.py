import re
from pyrogram import filters, Client, enums
from pyrogram.errors.exceptions.bad_request_400 import ChannelInvalid, UsernameInvalid, UsernameNotModified
from config import ADMINS, LOG_CHANNEL, PUBLIC_FILE_STORE, WEBSITE_URL, WEBSITE_URL_MODE, IMAGE_PATH
from plugins.users_api import get_user, get_short_link
from plugins.dbusers import db
import re
import os
import json
import base64
import tempfile
import asyncio
import shutil
import logging



async def allowed(_, __, message):
    if PUBLIC_FILE_STORE:
        return True
    if message.from_user and message.from_user.id in ADMINS:
        return True
    return False


logger = logging.getLogger(__name__)


@Client.on_message((filters.document | filters.video | filters.audio | filters.photo) & filters.private)
async def incoming_gen_link(bot, message):
    """
    Copy media to LOG_CHANNEL, produce a share link, extract poster (thumbnail),
    store file_id + poster_id in DB, and reply to user with the thumbnail + link.
    """
    try:
        # 1) Copy media to log channel and build outstr
        me = await bot.get_me()
        username = me.username or (me.first_name or "bot")
        post = await message.copy(LOG_CHANNEL)

        file_id = str(post.id)
        outstr = base64.urlsafe_b64encode(f"file_{file_id}".encode("ascii")).decode().strip("=")

        # 2) user info
        user_id = message.from_user.id
        user = await get_user(user_id)

        # 3) share link
        if WEBSITE_URL_MODE:
            share_link = f"{WEBSITE_URL}?Tech_VJ={outstr}"
        else:
            share_link = f"https://t.me/{username}?start={outstr}"

        # 4) prepare caption (shortener optional)
        if user and user.get("base_site") and user.get("shortener_api") is not None:
            try:
                short_link = await get_short_link(user, share_link)
                caption = f"<b>⭕ ʜᴇʀᴇ ɪs ʏᴏᴜʀ ʟɪɴᴋ:\n\n🖇️ sʜᴏʀᴛ ʟɪɴᴋ :- {short_link}</b>"
            except Exception as e:
                logger.exception("Shortener failed: %s", e)
                caption = f"<b>⭕ New File:\n\n🔗 ʟɪɴᴋ :- {share_link}</b>"
        else:
            caption = f"<b>⭕ New File:\n\n🔗 ʟɪɴᴋ :- {share_link}</b>"

        # 5) extract poster / thumbnail
        poster_file_id = None

        # 5a) If message is photo -> we can use its file_id directly
        if message.photo:
            # message.photo is a PhotoSize object (pyrogram gives .file_id)
            try:
                poster_file_id = message.photo.file_id
                # Optionally re-upload to LOG_CHANNEL to guarantee persistence/consistency:
                # sent = await bot.send_photo(LOG_CHANNEL, photo=poster_file_id)
                # poster_file_id = sent.photo.file_id
            except Exception:
                logger.exception("Failed to use message.photo.file_id directly.")

        # 5b) If video and thumbnail exists in Telegram metadata, use it
        if poster_file_id is None and message.video:
            thumbs = getattr(message.video, "thumbs", None) or getattr(message.video, "thumb", None)
            if thumbs:
                # thumbs may be list of PhotoSize or single PhotoSize
                thumb_obj = thumbs[0] if isinstance(thumbs, (list, tuple)) else thumbs
                try:
                    # Download that thumb locally, then re-upload to LOG_CHANNEL to get a stable file_id
                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
                    tmp.close()
                    thumb_path = tmp.name
                    await bot.download_media(thumb_obj.file_id, file_name=thumb_path)
                    sent = await bot.send_photo(LOG_CHANNEL, photo=thumb_path)
                    poster_file_id = sent.photo.file_id
                    os.remove(thumb_path)
                except Exception as e:
                    logger.exception("Using Telegram thumb failed: %s", e)

        # 5c) If no Telegram thumb available -> download video & extract frame using ffmpeg
        if poster_file_id is None and message.video:
            tmp_video = None
            tmp_thumb = None
            try:
                tmp_video = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
                tmp_video.close()
                video_path = tmp_video.name

                # download full video (may be large)
                await bot.download_media(message, file_name=video_path)

                # check ffmpeg presence
                if shutil.which("ffmpeg") is None:
                    logger.error("ffmpeg binary not found. Install ffmpeg on the server.")
                else:
                    tmp_thumb = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
                    tmp_thumb.close()
                    thumb_path = tmp_thumb.name

                    # Extract a frame at 1 second (you can change ss value)
                    # Using subprocess (async) to avoid blocking
                    cmd = [
                        "ffmpeg", "-y",
                        "-ss", "00:00:01",
                        "-i", video_path,
                        "-vframes", "1",
                        "-q:v", "2",
                        thumb_path
                    ]
                    proc = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    out, err = await proc.communicate()
                    if proc.returncode == 0 and os.path.exists(thumb_path):
                        sent = await bot.send_photo(LOG_CHANNEL, photo=thumb_path)
                        poster_file_id = sent.photo.file_id
                        try:
                            os.remove(thumb_path)
                        except Exception:
                            pass
                    else:
                        logger.error("ffmpeg failed to extract frame. stderr: %s", err.decode() if err else None)
            except Exception as e:
                logger.exception("Failed to extract frame from video: %s", e)
            finally:
                # cleanup video
                try:
                    if tmp_video and os.path.exists(tmp_video.name):
                        os.remove(tmp_video.name)
                except Exception:
                    pass

        # 6) store in DB (poster_file_id may be None)
        try:
            await db.store_file_id(outstr, poster_file_id)
        except Exception:
            logger.exception("DB store failed for %s", outstr)

        # 7) Reply to user with extracted thumbnail if exists, else fallback image
        try:
            if poster_file_id:
                await message.reply_photo(photo=poster_file_id, caption=caption)
            else:
                await message.reply_photo(photo=IMAGE_PATH, caption=caption)
        except Exception as e:
            logger.exception("Failed to reply to user: %s", e)
            # fallback to plain text reply
            try:
                await message.reply_text(caption)
            except Exception:
                pass

    except Exception as exc:
        logger.exception("incoming_gen_link failed: %s", exc)
        # Inform the user with a neutral message
        try:
            await message.reply_text("⚠️ Something went wrong generating your link/thumbnail. Please try again later.")
        except Exception:
            pass



@Client.on_message(filters.command(['link']) & filters.create(allowed))
async def gen_link_s(bot, message):
    username = (await bot.get_me()).username
    replied = message.reply_to_message
    if not replied:
        return await message.reply('Reply to a message to get a shareable link.')

    
    post = await replied.copy(LOG_CHANNEL)
    file_id = str(post.id)
    string = f"file_"
    string += file_id
    outstr = base64.urlsafe_b64encode(string.encode("ascii")).decode().strip("=")
    user_id = message.from_user.id
    user = await get_user(user_id)
    if WEBSITE_URL_MODE == True:
        share_link = f"{WEBSITE_URL}?Tech_VJ={outstr}"
    else:
        share_link = f"https://t.me/{username}?start={outstr}"
    if user["base_site"] and user["shortener_api"] != None:
        short_link = await get_short_link(user, share_link)
        await message.reply(f"<b>⭕ ʜᴇʀᴇ ɪs ʏᴏᴜʀ ʟɪɴᴋ:\n\n🖇️ sʜᴏʀᴛ ʟɪɴᴋ :- {short_link}</b>")
    else:
        await message.reply(f"<b>⭕ ʜᴇʀᴇ ɪs ʏᴏᴜʀ ʟɪɴᴋ:\n\n🔗 ᴏʀɪɢɪɴᴀʟ ʟɪɴᴋ :- {share_link}</b>")
        



@Client.on_message(filters.command(['batch']) & filters.create(allowed))
async def gen_link_batch(bot, message):
    username = (await bot.get_me()).username
    if " " not in message.text:
        return await message.reply("Use correct format.\nExample /batch https://t.me/vj_botz/10 https://t.me/vj_botz/20.")
    links = message.text.strip().split(" ")
    if len(links) != 3:
        return await message.reply("Use correct format.\nExample /batch https://t.me/vj_botz/10 https://t.me/vj_botz/20.")
    cmd, first, last = links
    regex = re.compile("(https://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$")
    match = regex.match(first)
    if not match:
        return await message.reply('Invalid link')
    f_chat_id = match.group(4)
    f_msg_id = int(match.group(5))
    if f_chat_id.isnumeric():
        f_chat_id = int(("-100" + f_chat_id))

    
    match = regex.match(last)
    if not match:
        return await message.reply('Invalid link')
    l_chat_id = match.group(4)
    l_msg_id = int(match.group(5))
    if l_chat_id.isnumeric():
        l_chat_id = int(("-100" + l_chat_id))

    if f_chat_id != l_chat_id:
        return await message.reply("Chat ids not matched.")
    try:
        chat_id = (await bot.get_chat(f_chat_id)).id
    except ChannelInvalid:
        return await message.reply('This may be a private channel / group. Make me an admin over there to index the files.')
    except (UsernameInvalid, UsernameNotModified):
        return await message.reply('Invalid Link specified.')
    except Exception as e:
        return await message.reply(f'Errors - {e}')


    
    sts = await message.reply("**ɢᴇɴᴇʀᴀᴛɪɴɢ ʟɪɴᴋ ғᴏʀ ʏᴏᴜʀ ᴍᴇssᴀɢᴇ**.\n**ᴛʜɪs ᴍᴀʏ ᴛᴀᴋᴇ ᴛɪᴍᴇ ᴅᴇᴘᴇɴᴅɪɴɢ ᴜᴘᴏɴ ɴᴜᴍʙᴇʀ ᴏғ ᴍᴇssᴀɢᴇs**")

    FRMT = "**ɢᴇɴᴇʀᴀᴛɪɴɢ ʟɪɴᴋ...**\n**ᴛᴏᴛᴀʟ ᴍᴇssᴀɢᴇs:** {total}\n**ᴅᴏɴᴇ:** {current}\n**ʀᴇᴍᴀɪɴɪɴɢ:** {rem}\n**sᴛᴀᴛᴜs:** {sts}"

    outlist = []


    # file store without db channel
    og_msg = 0
    tot = 0
    async for msg in bot.iter_messages(f_chat_id, l_msg_id, f_msg_id):
        tot += 1
        if og_msg % 20 == 0:
            try:
                await sts.edit(FRMT.format(total=l_msg_id-f_msg_id, current=tot, rem=((l_msg_id-f_msg_id) - tot), sts="Saving Messages"))
            except:
                pass
        if msg.empty or msg.service:
            continue
        file = {
            "channel_id": f_chat_id,
            "msg_id": msg.id
        }
        og_msg +=1
        outlist.append(file)



    with open(f"batchmode_{message.from_user.id}.json", "w+") as out:
        json.dump(outlist, out)
    post = await bot.send_document(LOG_CHANNEL, f"batchmode_{message.from_user.id}.json", file_name="Batch.json", caption="⚠️ Batch Generated For Filestore.")
    os.remove(f"batchmode_{message.from_user.id}.json")
    string = str(post.id)
    file_id = base64.urlsafe_b64encode(string.encode("ascii")).decode().strip("=")
    user_id = message.from_user.id
    user = await get_user(user_id)
    if WEBSITE_URL_MODE == True:
        share_link = f"{WEBSITE_URL}?Tech_VJ=BATCH-{file_id}"
    else:
        share_link = f"https://t.me/{username}?start=BATCH-{file_id}"
    if user["base_site"] and user["shortener_api"] != None:
        short_link = await get_short_link(user, share_link)
        await sts.edit(f"<b>⭕ ʜᴇʀᴇ ɪs ʏᴏᴜʀ ʟɪɴᴋ:\n\nContains `{og_msg}` files.\n\n🖇️ sʜᴏʀᴛ ʟɪɴᴋ :- {short_link}</b>")
    else:
        await sts.edit(f"<b>⭕ ʜᴇʀᴇ ɪs ʏᴏᴜʀ ʟɪɴᴋ:\n\nContains `{og_msg}` files.\n\n🔗 ᴏʀɪɢɪɴᴀʟ ʟɪɴᴋ :- {share_link}</b>")
        












