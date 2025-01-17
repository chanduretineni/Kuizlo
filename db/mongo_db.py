from pymongo import MongoClient

client = MongoClient("mongodb+srv://chandu:6264@chanduretineni.zfbcc.mongodb.net/?retryWrites=true&w=majority&appName=ChanduRetineni")

db = client["Kuizlo"]

# This line can be used to add collections and edit data
# collection = db["user_data"]
# doc = {"name":"chandu","id":"1234"}
# insert_doc_id = collection.insert_one(doc)
# print(insert_doc_id)