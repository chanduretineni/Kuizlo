from pymongo import MongoClient
from bson.objectid import ObjectId
from models.request_models import SaveEssayRequest

class EssayStorageService:
    def __init__(self, mongo_client, db):
        self.client = mongo_client
        self.db = db
        self.collection = self.db["essays"]

    async def save_essay(self, essay_data: SaveEssayRequest):
        try:
            # Convert Pydantic model to dictionary
            essay_dict = essay_data.model_dump()
            
            # Insert the essay document
            result = self.collection.insert_one(essay_dict)
            
            return {
                "success": True, 
                "message": "Essay saved successfully", 
                "document_id": str(result.inserted_id)
            }
        except Exception as e:
            return {
                "success": False, 
                "message": f"Error saving essay: {str(e)}"
            }

    async def get_essay(self, email: str):
        try:
            # Find the most recent essay for the given email
            essay = self.collection.find_one(
                {"email": email}, 
                sort=[("_id", -1)]  # Sort by most recent first
            )
            
            if not essay:
                return {
                    "success": False, 
                    "message": "No essay found for this email"
                }
            
            # Convert ObjectId to string
            essay['_id'] = str(essay['_id'])
            return {
                "success": True, 
                "essay": essay
            }
        except Exception as e:
            return {
                "success": False, 
                "message": f"Error retrieving essay: {str(e)}"
            }

# Create a singleton instance using the provided MongoDB connection
mongo_client = MongoClient("mongodb+srv://chandu:6264@chanduretineni.zfbcc.mongodb.net/?retryWrites=true&w=majority&appName=ChanduRetineni")
db = mongo_client["Kuizlo"]
essay_storage_service = EssayStorageService(mongo_client, db)
