from pymongo import MongoClient, ASCENDING
from bson.objectid import ObjectId
from datetime import datetime
import os

class Database:
    def __init__(self):
        mongo_uri = os.getenv('MONGO_URI', 'mongodb://localhost:27017/')
        self.client = MongoClient(mongo_uri)
        self.db = self.client['list_tracker']
        self._create_indexes()
    
    def _create_indexes(self):
        self.db.users.create_index([('email', ASCENDING)], unique=True)
        self.db.users.create_index([('username', ASCENDING)], unique=True)
        self.db.lists.create_index([('name', ASCENDING)])
        self.db.lists.create_index([('owner_id', ASCENDING)])
        self.db.lists.create_index([('is_public', ASCENDING)])
        self.db.lists.create_index([('is_ethereal', ASCENDING)])
        self.db.lists.create_index([('tags', ASCENDING)])
        self.db.favorites.create_index([('user_id', ASCENDING)])
        self.db.favorites.create_index([('list_id', ASCENDING)])
        self.db.favorites.create_index([('user_id', ASCENDING), ('list_id', ASCENDING)], unique=True)
        self.db.autocomplete_cache.create_index([('user_id', ASCENDING)])
        self.db.autocomplete_cache.create_index([('item_text', ASCENDING)])

    def get_user_by_email(self, email):
        return self.db.users.find_one({'email': email})
    
    def get_user_by_id(self, user_id):
        return self.db.users.find_one({'_id': ObjectId(user_id)})
    
    def create_user(self, email, username, password_hash):
        user = {
            'email': email,
            'username': username,
            'password_hash': password_hash,
            'created_at': datetime.utcnow(),
            'preferences': {
                'theme': 'dark'
            }
        }
        result = self.db.users.insert_one(user)
        return result.inserted_id
    
    def update_user_theme(self, user_id, theme):
        self.db.users.update_one(
            {'_id': ObjectId(user_id)},
            {'$set': {'preferences.theme': theme}}
        )
    
    def get_lists_by_owner(self, user_id):
        return list(self.db.lists.find({'owner_id': ObjectId(user_id)}).sort('created_at', -1))
    
    def get_public_lists(self, search_query=None, tags=None, limit=50):
        query = {'is_public': True}
        if search_query:
            query['name'] = {'$regex': search_query, '$options': 'i'}
        if tags:
            query['tags'] = {'$in': tags}
        return list(self.db.lists.find(query).sort('created_at', -1).limit(limit))
    
    def get_list_by_id(self, list_id):
        return self.db.lists.find_one({'_id': ObjectId(list_id)})
    
    def create_list(self, name, owner_id, thumbnail_url='', is_public=False, is_ethereal=False, tags=None, items=None):
        items = items or []
        sorted_items = sorted(items, key=lambda x: x['text'].lower())
        
        list_doc = {
            'name': name,
            'owner_id': ObjectId(owner_id),
            'thumbnail_url': thumbnail_url,
            'is_public': is_public,
            'is_ethereal': is_ethereal,
            'tags': tags or [],
            'items': sorted_items,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        
        if is_ethereal:
            list_doc['original_items'] = sorted_items.copy()
        
        result = self.db.lists.insert_one(list_doc)
        return result.inserted_id
    
    def update_list(self, list_id, **kwargs):
        kwargs['updated_at'] = datetime.utcnow()
        self.db.lists.update_one(
            {'_id': ObjectId(list_id)},
            {'$set': kwargs}
        )
    
    def delete_list(self, list_id):
        self.db.lists.delete_one({'_id': ObjectId(list_id)})
        self.db.favorites.delete_many({'list_id': ObjectId(list_id)})
    
    def add_item_to_list(self, list_id, item_text):
        list_doc = self.get_list_by_id(list_id)
        if not list_doc:
            return False, 'List not found'
        
        for item in list_doc['items']:
            if item['text'].lower() == item_text.lower():
                return False, 'Item already exists'
        
        new_item = {
            '_id': ObjectId(),
            'text': item_text,
            'added_at': datetime.utcnow()
        }
        
        items = list_doc['items'] + [new_item]
        sorted_items = sorted(items, key=lambda x: x['text'].lower())
        
        self.db.lists.update_one(
            {'_id': ObjectId(list_id)},
            {'$set': {'items': sorted_items, 'updated_at': datetime.utcnow()}}
        )
        
        return True, 'Item added successfully'
    
    def remove_item_from_list(self, list_id, item_id):
        self.db.lists.update_one(
            {'_id': ObjectId(list_id)},
            {
                '$pull': {'items': {'_id': ObjectId(item_id)}},
                '$set': {'updated_at': datetime.utcnow()}
            }
        )
    
    def restore_ethereal_list(self, list_id):
        list_doc = self.get_list_by_id(list_id)
        if not list_doc or not list_doc.get('is_ethereal'):
            return False
        
        original_items = list_doc.get('original_items', [])
        self.db.lists.update_one(
            {'_id': ObjectId(list_id)},
            {'$set': {'items': original_items, 'updated_at': datetime.utcnow()}}
        )
        return True
    
    def is_favorited(self, user_id, list_id):
        return self.db.favorites.find_one({
            'user_id': ObjectId(user_id),
            'list_id': ObjectId(list_id)
        }) is not None
    
    def add_favorite(self, user_id, list_id):
        try:
            self.db.favorites.insert_one({
                'user_id': ObjectId(user_id),
                'list_id': ObjectId(list_id),
                'created_at': datetime.utcnow()
            })
            return True
        except:
            return False
    
    def remove_favorite(self, user_id, list_id):
        self.db.favorites.delete_one({
            'user_id': ObjectId(user_id),
            'list_id': ObjectId(list_id)
        })
    
    def get_favorited_lists(self, user_id):
        favorites = self.db.favorites.find({'user_id': ObjectId(user_id)})
        list_ids = [fav['list_id'] for fav in favorites]
        return list(self.db.lists.find({'_id': {'$in': list_ids}}).sort('created_at', -1))
    
    def get_autocomplete_suggestions(self, user_id, query, limit=5):
        suggestions = self.db.autocomplete_cache.find({
            'user_id': ObjectId(user_id),
            'item_text': {'$regex': f'^{query}', '$options': 'i'}
        }).sort('frequency', -1).limit(limit)
        return [s['item_text'] for s in suggestions]
    
    def update_autocomplete_cache(self, user_id, item_text):
        existing = self.db.autocomplete_cache.find_one({
            'user_id': ObjectId(user_id),
            'item_text': item_text
        })
        
        if existing:
            self.db.autocomplete_cache.update_one(
                {'_id': existing['_id']},
                {
                    '$set': {'last_used': datetime.utcnow()},
                    '$inc': {'frequency': 1}
                }
            )
        else:
            self.db.autocomplete_cache.insert_one({
                'user_id': ObjectId(user_id),
                'item_text': item_text,
                'last_used': datetime.utcnow(),
                'frequency': 1
            })
