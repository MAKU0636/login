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
    async def update_collection(self, collection_name, data, unique_field):
        try:
            collection_ref = self.db.collection(collection_name)
            for row in data:
                symbol = row.get(unique_field)
                if symbol is None:
                    logger.warning(f"Row missing unique field '{unique_field}': {row}")
                    continue
                docs = await asyncio.to_thread(lambda: list(collection_ref.where(unique_field, "==", symbol).stream()))
                found = False
                for doc in docs:
                    found = True
                    await asyncio.to_thread(doc.reference.update, {k: v for k, v in row.items() if k != unique_field})
                    logger.info(f"Updated document with {unique_field}: {symbol}")
                if not found:
                    logger.info(f"No document found with {unique_field}: {symbol}")
        except Exception as e:
            logger.error(f"Error updating collection '{collection_name}': {e}")
