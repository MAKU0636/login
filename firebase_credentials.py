import firebase_admin
from firebase_admin import credentials, firestore
import asyncio
import logging
import os
import json

logger = logging.getLogger(__name__)

firebase_cred_json = os.environ.get('FIREBASE_CREDENTIALS')
if not firebase_cred_json:
    raise ValueError("FIREBASE_CREDENTIALS environment variable not set")

firebase_cred = json.loads(firebase_cred_json)

cred = credentials.Certificate(firebase_cred)
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

class FirestoreData:
    def __init__(self):
        self.db = firestore.client()
    async def read_collection(self, collection_name):
        try:
            docs = await asyncio.to_thread(lambda: list(self.db.collection(collection_name).stream()))
            return [item.to_dict() for item in docs]
        except Exception as e:
            logger.error(f"Error reading collection '{collection_name}': {e}")
            return []
    async def update_collection(self, collection_name, data_list, key_field):
        try:
            for data in data_list:
                doc_id = data.get(key_field)
                await asyncio.to_thread(self.db.collection(collection_name).document(doc_id).set, data)
            logger.info(f"Updated {len(data_list)} documents in '{collection_name}'")
        except Exception as e:
            logger.error(f"Error updating collection '{collection_name}': {e}")
