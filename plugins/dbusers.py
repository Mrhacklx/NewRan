import motor.motor_asyncio
from config import DB_NAME, DB_URI


class Database:
    """MongoDB handler for users, user links, and file IDs."""

    def __init__(self, uri: str, database_name: str):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        
        # Collections
        self.col_users = self.db.users          # users collection
        self.col_files = self._client["NewRan"].file_ids       # file_ids collectio
        self.col_links = self.db.link_users     # link_users collection (user + file_ids)n

    # ---------------- USERS ----------------

    def new_user(self, user_id: int, name: str) -> dict:
        """Prepare a user document for insertion."""
        return {"id": user_id, "name": name}

    async def add_user(self, user_id: int, name: str):
        """Add a user if they do not exist."""
        user = self.new_user(user_id, name)
        await self.col_users.update_one(
            {"id": user_id},
            {"$setOnInsert": user},
            upsert=True
        )

    async def is_user_exist(self, user_id: int) -> bool:
        """Check if a user exists."""
        user = await self.col_users.find_one({"id": user_id})
        return bool(user)

    async def total_users_count(self) -> int:
        """Return total number of users."""
        return await self.col_users.count_documents({})

    async def get_all_users(self):
        """Return all users as a cursor."""
        return self.col_users.find({})

    async def delete_user(self, user_id: int):
        """Delete a user by ID."""
        await self.col_users.delete_many({"id": user_id})

    # ---------------- USER LINKS (user + file_ids) ----------------

    def new_user_link(self, user_id: int, file_ids=None) -> dict:
        """Prepare a user link document for insertion."""
        if file_ids is None:
            file_ids = []
        return {"user_id": user_id, "file_ids": file_ids}

    async def add_user_link(self, user_id: int, file_ids=None):
        """Add a user link document if it does not exist."""
        user_link = self.new_user_link(user_id, file_ids)
        await self.col_links.update_one(
            {"user_id": user_id},
            {"$setOnInsert": user_link},
            upsert=True
        )

    async def is_user_link_exist(self, user_id: int) -> bool:
        """Check if a user link exists."""
        user = await self.col_links.find_one({"user_id": user_id})
        return bool(user)

    async def total_users_link_count(self) -> int:
        """Return total number of user links."""
        return await self.col_links.count_documents({})

    async def get_all_users_link(self):
        """Return all user links as a cursor."""
        return self.col_links.find({})

    async def delete_user_link(self, user_id: int):
        """Delete a user link by user_id."""
        await self.col_links.delete_many({"user_id": user_id})

    # ---------------- USER FILES ----------------

    async def add_file_to_user(self, user_id: int, file_id: str):
        """Add a file_id to a user's file list (avoid duplicates)."""
        await self.col_links.update_one(
            {"user_id": user_id},
            {"$addToSet": {"file_ids": file_id}},
            upsert=True
        )

    async def file_exists_for_user(self, user_id: int, file_id: str) -> bool:
        """Check if a file_id exists for a specific user."""
        doc = await self.col_links.find_one(
            {"user_id": user_id, "file_ids": file_id},
            {"_id": 1}
        )
        return doc is not None

    async def safe_add_file_to_user(self, user_id: int, file_id: str) -> bool:
        """Add file_id to user only if it doesn't already exist."""
        if await self.file_exists_for_user(user_id, file_id):
            return False
        await self.add_file_to_user(user_id, file_id)
        return True

    async def get_files_of_user(self, user_id: int) -> list:
        """Get all file_ids of a user."""
        user = await self.col_links.find_one({"user_id": user_id})
        return user.get("file_ids", []) if user else []

    async def remove_file_from_user(self, user_id: int, file_id: str):
        """Remove a file_id from a user's file list."""
        await self.col_links.update_one(
            {"user_id": user_id},
            {"$pull": {"file_ids": file_id}}
        )

    # ---------------- FILE IDS COLLECTION ----------------


    async def store_file_id(self, file_id: str, poster_id: str = None):
        """Store a unique file_id (and optional poster_id) in the file_ids collection."""
        data = {"file_id": file_id}
        if poster_id:
            data["poster_id"] = poster_id
        await self.col_files.update_one(
            {"file_id": file_id},
            {"$setOnInsert": data},
            upsert=True
        )




    async def file_id_exists(self, file_id: str) -> bool:
        """Check if a file_id exists in the file_ids collection."""
        doc = await self.col_files.find_one({"file_id": file_id})
        return doc is not None

    async def get_all_file_ids(self) -> list:
        """Return all file_ids in the collection."""
        cursor = self.col_files.find({})
        return [doc async for doc in cursor]

    async def delete_file_id(self, file_id: str):
        """Delete a file_id from the collection."""
        await self.col_files.delete_one({"file_id": file_id})


# ---------------- INIT DB ----------------

db = Database(DB_URI, DB_NAME)
