from pymongo import MongoClient
from bson.objectid import ObjectId
from models.request_models import SaveEssayRequest, UserEssays, RetrieveUserEssays

class EssayStorageService:
    def __init__(self, mongo_client, db):
        self.client = mongo_client
        self.db = db
        self.collection = self.db["essays"]

    async def save_essay(self, essay_data: SaveEssayRequest):
        try:
            essay_dict = essay_data.model_dump()

            # Check if the document exists
            existing_document = self.collection.find_one({
                "document_id": essay_data.document_id, 
                "user_id": essay_data.user_id
            })

            if existing_document:
                # Update the existing document
                self.collection.update_one(
                    {"_id": existing_document["_id"]}, 
                    {"$set": essay_dict}
                )
                message = "Essay updated successfully"
            else:
                # Insert as a new document
                result = self.collection.insert_one(essay_dict)
                message = "Essay saved successfully"
            
            return {"success": True, "message": message}
        except Exception as e:
            return {"success": False, "message": f"Error saving essay: {str(e)}"}

    async def get_essays_by_user_id(self, user_id: str):
        try:
            essays_cursor = self.collection.find({"user_id": user_id})
            essays = [
                UserEssays(Title=essay["title"], document_id=essay["document_id"])
                for essay in essays_cursor
            ]

            if not essays:
                return {"success": False, "message": "No essays found for this user"}

            return RetrieveUserEssays(essays=essays)
        except Exception as e:
            return {"success": False, "message": f"Error retrieving essays: {str(e)}"}

    async def get_specific_essay(self, user_id: str, document_id: str):
        try:
            essay = self.collection.find_one({"user_id": user_id, "document_id": document_id})
            
            if not essay:
                return {"success": False, "message": "No essay found for the given user_id and document_id"}
            
            essay["_id"] = str(essay["_id"])  # Convert ObjectId to string
            return {"success": True, "essay": essay}
        except Exception as e:
            return {"success": False, "message": f"Error retrieving specific essay: {str(e)}"}

# Create singleton instance
mongo_client = MongoClient("mongodb+srv://chandu:6264@chanduretineni.zfbcc.mongodb.net/?retryWrites=true&w=majority&appName=ChanduRetineni")
db = mongo_client["Kuizlo"]
essay_storage_service = EssayStorageService(mongo_client, db)
