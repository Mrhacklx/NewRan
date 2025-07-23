import logging, asyncio, os, re, random, pytz, aiohttp, requests, string, json, http.client
from datetime import date, datetime
from config import SHORTLINK_API, SHORTLINK_URL
from shortzy import Shortzy
from motor.motor_asyncio import AsyncIOMotorClient
from config import DB_NAME, DB_URI

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# MongoDB setup
client = AsyncIOMotorClient(DB_URI)
db = client['DB_NAME']
tokens_col = db.tokens  # stores tokens
verified_col = db.verified  # stores verification dates

# Shortener handler
async def get_verify_shorted_link(link):
    if SHORTLINK_URL == "api.shareus.io":
        url = f'https://{SHORTLINK_URL}/easy_api'
        params = {
            "key": SHORTLINK_API,
            "link": link,
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, raise_for_status=True, ssl=False) as response:
                    data = await response.text()
                    return data
        except Exception as e:
            logger.error(e)
            return link
    else:
        shortzy = Shortzy(api_key=SHORTLINK_API, base_site=SHORTLINK_URL)
        link = await shortzy.convert(link)
        return link

# Check if token is valid and not used
async def check_token(bot, userid, token):
    user = await bot.get_users(userid)
    record = await tokens_col.find_one({"user_id": user.id})
    if record and token in record.get("tokens", {}):
        return not record["tokens"][token]
    return False

# Generate and store a token
async def get_token(bot, userid, link, data):
    user = await bot.get_users(userid)
    token = ''.join(random.choices(string.ascii_letters + string.digits, k=7))
    await tokens_col.update_one(
        {"user_id": user.id},
        {"$set": {f"tokens.{token}": False}},
        upsert=True
    )
    full_link = f"{link}verify-{user.id}-{token}-{data}"
    shortened = await get_verify_shorted_link(full_link)
    return str(shortened)

# Mark token as used and store verification date
async def verify_user(bot, userid, token):
    user = await bot.get_users(userid)
    await tokens_col.update_one(
        {"user_id": user.id},
        {"$set": {f"tokens.{token}": True}},
        upsert=True
    )
    tz = pytz.timezone('Asia/Kolkata')
    today = datetime.now(tz).date()
    await verified_col.update_one(
        {"user_id": user.id},
        {"$set": {"verified_date": str(today)}},
        upsert=True
    )

# Check if user is verified today
async def check_verification(bot, userid):
    user = await bot.get_users(userid)
    tz = pytz.timezone('Asia/Kolkata')
    today = datetime.now(tz).date()

    record = await verified_col.find_one({"user_id": user.id})
    if record:
        try:
            verified_date = datetime.strptime(record["verified_date"], "%Y-%m-%d").date()
            return verified_date >= today
        except:
            return False
    return False
