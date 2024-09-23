import pymongo
import json

client = pymongo.MongoClient("mongodb://localhost:27017/")
db = client["AlMayadeen"]
collection = db["articles_clean"]

with open(r'C:\Users\Administrator\Desktop\Almayadeenproject\json_files\articles_09.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
    print(f"Data to insert: {data}") # Check the data being read
    collection.insert_many(data)
    print("Data inserted successfully.")