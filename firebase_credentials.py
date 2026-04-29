import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.base_query import FieldFilter
import asyncio
import logging
import os
import json

logger = logging.getLogger(__name__)

firebase_cred_json = os.environ.get('FIREBASE_CREDENTIALS')
if not firebase_cred_json:
    # Load from local file for development
    json_path = os.path.join(os.path.dirname(__file__), 'firebase_credentials.json')
    with open(json_path, 'r') as f:
        firebase_cred = json.load(f)
else:
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
    async def read_document(self, collection_name, document_id):
        try:
            doc = await asyncio.to_thread(self.db.collection(collection_name).document(document_id).get)
            return doc.to_dict() if doc.exists else None
        except Exception as e:
            logger.error(f"Error reading document '{document_id}' from '{collection_name}': {e}")
            return None
    async def update_collection(self, collection_name, data, unique_field):
        try:
            collection_ref = self.db.collection(collection_name)
            for row in data:
                symbol = row.get(unique_field)
                if symbol is None:
                    logger.warning(f"Row missing unique field '{unique_field}': {row}")
                    continue
                docs = await asyncio.to_thread(lambda: list(collection_ref.where(filter=FieldFilter(unique_field, "==", symbol)).stream()))
                found = False
                for doc in docs:
                    found = True
                    await asyncio.to_thread(doc.reference.update, {k: v for k, v in row.items() if k != unique_field})
                    logger.info(f"Updated document with {unique_field}: {symbol}")
                if not found:
                    logger.info(f"No document found with {unique_field}: {symbol}")
        except Exception as e:
            logger.error(f"Error updating collection '{collection_name}': {e}")

fire = FirestoreData()

async def get_shoonya_huf_creds():
    """Get Shoonya HUF credentials + password"""
    creds, pwd = await asyncio.gather(
        fire.read_document('other_credentials', 'shoonya_huf'),
        fire.read_document('password', 'password_001')
    )
    if creds and pwd:
        creds['password'] = pwd.get('shoonya_huf')
    return creds

async def get_icici_creds():
    """Get ICICI PIN from Firestore"""
    pwd = await fire.read_document('password', 'password_003')
    return pwd.get('icici') if pwd else None
