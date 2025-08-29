import motor.motor_asyncio
from config import DB_NAME, DB_URI

class Database:
    
    def __init__(self, uri, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.col = self.db.users         # users collection
        self.col_link = self.db.link_users  # link_users collection

    # ---------------- USERS ----------------

    def new_user(self, id, name):
        return dict(
            id=id,
            name=name,
        )
    
    async def add_user(self, id, name):
        user = self.new_user(id, name)
        await self.col.update_one(
            {"id": id},
            {"$setOnInsert": user},
            upsert=True
        )
    
    async def is_user_exist(self, id):
        user = await self.col.find_one({'id': int(id)})
        return bool(user)

    async def total_users_count(self):
        return await self.col.count_documents({})
    
    async def get_all_users(self):
        return self.col.find({})

    async def delete_user(self, user_id):
        await self.col.delete_many({'id': int(user_id)})

    # ---------------- LINK USERS (user_id + file_ids list) ----------------

    async def add_file(self, user_id, file_id):
        """Add file_id to user's file list (avoid duplicates)."""
        await self.col_link.update_one(
            {"user_id": user_id},
            {"$addToSet": {"file_ids": file_id}},
            upsert=True
        )

    async def file_exists(self, user_id, file_id) -> bool:
        """Check if file_id exists for this user."""
        doc = await self.col_link.find_one(
            {"user_id": user_id, "file_ids": file_id},
            {"_id": 1}
        )
        return doc is not None

    async def safe_add_file(self, user_id, file_id) -> bool:
        """Only add file_id if not already present."""
        if await self.file_exists(user_id, file_id):
            return False
        await self.add_file(user_id, file_id)
        return True

    async def get_files(self, user_id):
        """Get all file_ids of a user."""
        user = await self.col_link.find_one({"user_id": user_id})
        if user:
            return user.get("file_ids", [])
        return []

    async def remove_file(self, user_id, file_id):
        """Remove a file_id from user's list."""
        await self.col_link.update_one(
            {"user_id": user_id},
            {"$pull": {"file_ids": file_id}}
        )


# init db instance
db = Database(DB_URI, DB_NAME)
