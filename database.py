from pymongo import MongoClient, ASCENDING
from bson.objectid import ObjectId
from datetime import datetime
from werkzeug.security import generate_password_hash
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
        self.db.lists.create_index([('collaborators', ASCENDING)])
        self.db.lists.create_index([('is_public', ASCENDING)])
        self.db.lists.create_index([('is_ethereal', ASCENDING)])
        self.db.lists.create_index([('tags', ASCENDING)])
        self.db.lists.create_index([('parent_id', ASCENDING)])
        self.db.favorites.create_index([('user_id', ASCENDING)])
        self.db.favorites.create_index([('list_id', ASCENDING)])
        self.db.favorites.create_index([('user_id', ASCENDING), ('list_id', ASCENDING)], unique=True)
        self.db.autocomplete_cache.create_index([('user_id', ASCENDING)])
        self.db.autocomplete_cache.create_index([('item_text', ASCENDING)])

    def get_user_by_email(self, email):
        return self.db.users.find_one({'email': email})
    
    def get_user_by_id(self, user_id):
        return self.db.users.find_one({'_id': ObjectId(user_id)})
    
    def get_user_by_username(self, username):
        return self.db.users.find_one({'username': username})
    
    def search_users_by_username(self, query, limit=5):
        users = self.db.users.find({
            'username': {'$regex': f'^{query}', '$options': 'i'}
        }).limit(limit)
        return [{'username': u['username'], '_id': str(u['_id'])} for u in users]
    
    def create_user(self, email, username, password_hash):
        user = {
            'email': email,
            'username': username,
            'password_hash': password_hash,
            'created_at': datetime.utcnow(),
            'is_admin': False,
            'roles': [],
            'groups': [],
            'preferences': {
                'theme': 'dark'
            },
            'subscription': {
                'is_ad_free': False,
                'stripe_customer_id': None,
                'stripe_subscription_id': None,
                'subscription_start': None,
                'subscription_end': None
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
    
    def get_public_lists_paginated(self, search_query=None, tags=None, skip=0, limit=10):
        query = {'is_public': True}
        if search_query:
            query['name'] = {'$regex': search_query, '$options': 'i'}
        if tags:
            query['tags'] = {'$in': tags}
        return list(self.db.lists.find(query).sort('updated_at', -1).skip(skip).limit(limit))
    
    def get_list_by_id(self, list_id):
        return self.db.lists.find_one({'_id': ObjectId(list_id)})
    
    def create_list(self, name, owner_id, thumbnail_url='', is_public=True, is_ethereal=False, tags=None, items=None, parent_id=None):
        items = items or []
        sorted_items = self._sort_items_with_sections(items)
        
        list_doc = {
            'name': name,
            'owner_id': ObjectId(owner_id),
            'thumbnail_url': thumbnail_url,
            'is_public': is_public,
            'is_ethereal': is_ethereal,
            'tags': tags or [],
            'items': sorted_items,
            'collaborators': [],
            'parent_id': ObjectId(parent_id) if parent_id else None,
            'clone_count': 0,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        
        if is_ethereal:
            list_doc['original_items'] = sorted_items.copy()
        
        result = self.db.lists.insert_one(list_doc)
        
        if parent_id:
            self.db.lists.update_one(
                {'_id': ObjectId(parent_id)},
                {'$inc': {'clone_count': 1}}
            )
        
        return result.inserted_id
    
    def update_list(self, list_id, **kwargs):
        kwargs['updated_at'] = datetime.utcnow()
        self.db.lists.update_one(
            {'_id': ObjectId(list_id)},
            {'$set': kwargs}
        )
    
    def delete_list(self, list_id):
        list_doc = self.get_list_by_id(list_id)
        if not list_doc:
            return
        
        parent_id = list_doc.get('parent_id')
        if parent_id:
            self.db.lists.update_one(
                {'_id': parent_id},
                {'$inc': {'clone_count': -1}}
            )
        
        children = list(self.db.lists.find({'parent_id': ObjectId(list_id)}))
        
        orphan_list_id = None
        for child in children:
            if parent_id:
                self.db.lists.update_one(
                    {'_id': child['_id']},
                    {'$set': {'parent_id': parent_id}}
                )
                if parent_id:
                    self.db.lists.update_one(
                        {'_id': parent_id},
                        {'$inc': {'clone_count': 1}}
                    )
            else:
                if orphan_list_id is None:
                    orphan_list_id = self._create_orphan_list(list_doc)
                self.db.lists.update_one(
                    {'_id': child['_id']},
                    {'$set': {'parent_id': orphan_list_id}}
                )
                if orphan_list_id:
                    self.db.lists.update_one(
                        {'_id': orphan_list_id},
                        {'$inc': {'clone_count': 1}}
                    )
        
        self.db.lists.delete_one({'_id': ObjectId(list_id)})
        self.db.favorites.delete_many({'list_id': ObjectId(list_id)})
    
    def _sort_items_with_sections(self, items):
        sectioned = [item for item in items if item.get('section')]
        loose = [item for item in items if not item.get('section')]
        
        sectioned_sorted = sorted(sectioned, key=lambda x: (x['section'].lower(), x['text'].lower()))
        loose_sorted = sorted(loose, key=lambda x: x['text'].lower())
        
        return sectioned_sorted + loose_sorted
    
    def add_item_to_list(self, list_id, item_text, section=None):
        list_doc = self.get_list_by_id(list_id)
        if not list_doc:
            return False, 'List not found', None
        
        for item in list_doc['items']:
            if item['text'].lower() == item_text.lower():
                return False, 'Item already exists', None
        
        new_item = {
            '_id': ObjectId(),
            'text': item_text,
            'quantity': 1,
            'added_at': datetime.utcnow()
        }
        
        if section:
            new_item['section'] = section
        
        items = list_doc['items'] + [new_item]
        sorted_items = self._sort_items_with_sections(items)
        
        self.db.lists.update_one(
            {'_id': ObjectId(list_id)},
            {'$set': {'items': sorted_items, 'updated_at': datetime.utcnow()}}
        )
        
        return True, 'Item added successfully', str(new_item['_id'])
    
    def remove_item_from_list(self, list_id, item_id):
        self.db.lists.update_one(
            {'_id': ObjectId(list_id)},
            {
                '$pull': {'items': {'_id': ObjectId(item_id)}},
                '$set': {'updated_at': datetime.utcnow()}
            }
        )
    
    def restore_ethereal_list(self, list_id, reset_checked_only=False):
        list_doc = self.get_list_by_id(list_id)
        if not list_doc or not list_doc.get('is_ethereal'):
            return False
        
        if reset_checked_only:
            items = list_doc.get('items', [])
            for item in items:
                item['checked'] = False
            self.db.lists.update_one(
                {'_id': ObjectId(list_id)},
                {'$set': {'items': items, 'updated_at': datetime.utcnow()}}
            )
        else:
            original_items = list_doc.get('original_items', [])
            unchecked_items = []
            for item in original_items:
                item_copy = item.copy()
                item_copy['checked'] = False
                unchecked_items.append(item_copy)
            self.db.lists.update_one(
                {'_id': ObjectId(list_id)},
                {'$set': {'items': unchecked_items, 'updated_at': datetime.utcnow()}}
            )
        return True
    
    def toggle_item_checked(self, list_id, item_id):
        list_doc = self.get_list_by_id(list_id)
        if not list_doc:
            return False, 'List not found'
        
        items = list_doc.get('items', [])
        for item in items:
            if str(item['_id']) == str(item_id):
                item['checked'] = not item.get('checked', False)
                break
        
        self.db.lists.update_one(
            {'_id': ObjectId(list_id)},
            {'$set': {'items': items, 'updated_at': datetime.utcnow()}}
        )
        return True, 'Item toggled'
    
    def add_item_to_original(self, list_id, item_text):
        list_doc = self.get_list_by_id(list_id)
        if not list_doc or not list_doc.get('is_ethereal'):
            return False, 'Not an ethereal list', None
        
        original_items = list_doc.get('original_items', [])
        for item in original_items:
            if item['text'].lower() == item_text.lower():
                return False, 'Item already exists', None
        
        new_item = {
            '_id': ObjectId(),
            'text': item_text,
            'quantity': 1,
            'checked': False,
            'added_at': datetime.utcnow()
        }
        
        original_items.append(new_item)
        sorted_original = self._sort_items_with_sections(original_items)
        
        items = list_doc.get('items', [])
        items.append(new_item.copy())
        sorted_items = self._sort_items_with_sections(items)
        
        self.db.lists.update_one(
            {'_id': ObjectId(list_id)},
            {'$set': {
                'original_items': sorted_original,
                'items': sorted_items,
                'updated_at': datetime.utcnow()
            }}
        )
        return True, 'Item added to original', str(new_item['_id'])
    
    def remove_item_from_original(self, list_id, item_id):
        list_doc = self.get_list_by_id(list_id)
        if not list_doc or not list_doc.get('is_ethereal'):
            return False
        
        self.db.lists.update_one(
            {'_id': ObjectId(list_id)},
            {
                '$pull': {
                    'original_items': {'_id': ObjectId(item_id)},
                    'items': {'_id': ObjectId(item_id)}
                },
                '$set': {'updated_at': datetime.utcnow()}
            }
        )
        return True
    
    def adjust_item_quantity(self, list_id, item_id, delta):
        list_doc = self.get_list_by_id(list_id)
        if not list_doc:
            return False, 'List not found'
        
        items = list_doc.get('items', [])
        for item in items:
            if str(item['_id']) == str(item_id):
                current_qty = item.get('quantity', 1)
                new_qty = max(1, current_qty + delta)
                item['quantity'] = new_qty
                break
        
        self.db.lists.update_one(
            {'_id': ObjectId(list_id)},
            {'$set': {'items': items, 'updated_at': datetime.utcnow()}}
        )
        return True, 'Quantity updated'
    
    def update_item_text(self, list_id, item_id, new_text):
        list_doc = self.get_list_by_id(list_id)
        if not list_doc:
            return False, 'List not found', None
        
        items = list_doc.get('items', [])
        old_text = None
        item_found = False
        
        for item in items:
            if str(item['_id']) == str(item_id):
                old_text = item['text']
                if old_text.lower() == new_text.lower():
                    return False, 'New text is the same as current text', old_text
                item_found = True
            elif item['text'].lower() == new_text.lower():
                return False, 'An item with this text already exists', old_text
        
        if not item_found:
            return False, 'Item not found', None
        
        for item in items:
            if str(item['_id']) == str(item_id):
                item['text'] = new_text
                break
        
        sorted_items = self._sort_items_with_sections(items)
        
        self.db.lists.update_one(
            {'_id': ObjectId(list_id)},
            {'$set': {'items': sorted_items, 'updated_at': datetime.utcnow()}}
        )
        
        return True, 'Item updated successfully', old_text
    
    def update_item_text_in_original(self, list_id, item_id, new_text):
        list_doc = self.get_list_by_id(list_id)
        if not list_doc or not list_doc.get('is_ethereal'):
            return False, 'Not an ethereal list', None
        
        items = list_doc.get('items', [])
        original_items = list_doc.get('original_items', [])
        old_text = None
        item_found = False
        
        for item in original_items:
            if str(item['_id']) == str(item_id):
                old_text = item['text']
                if old_text.lower() == new_text.lower():
                    return False, 'New text is the same as current text', old_text
                item_found = True
            elif item['text'].lower() == new_text.lower():
                return False, 'An item with this text already exists', old_text
        
        if not item_found:
            return False, 'Item not found', None
        
        for item in original_items:
            if str(item['_id']) == str(item_id):
                item['text'] = new_text
                break
        
        for item in items:
            if str(item['_id']) == str(item_id):
                item['text'] = new_text
                break
        
        sorted_items = self._sort_items_with_sections(items)
        sorted_original = self._sort_items_with_sections(original_items)
        
        self.db.lists.update_one(
            {'_id': ObjectId(list_id)},
            {'$set': {
                'items': sorted_items,
                'original_items': sorted_original,
                'updated_at': datetime.utcnow()
            }}
        )
        
        return True, 'Item updated successfully', old_text
    
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
    
    def replace_autocomplete_entry(self, user_id, old_text, new_text):
        old_entry = self.db.autocomplete_cache.find_one({
            'user_id': ObjectId(user_id),
            'item_text': old_text
        })
        
        new_entry = self.db.autocomplete_cache.find_one({
            'user_id': ObjectId(user_id),
            'item_text': new_text
        })
        
        if old_entry and new_entry:
            self.db.autocomplete_cache.delete_one({'_id': old_entry['_id']})
            self.db.autocomplete_cache.update_one(
                {'_id': new_entry['_id']},
                {
                    '$set': {'last_used': datetime.utcnow()},
                    '$inc': {'frequency': 1}
                }
            )
        elif old_entry:
            self.db.autocomplete_cache.update_one(
                {'_id': old_entry['_id']},
                {
                    '$set': {
                        'item_text': new_text,
                        'last_used': datetime.utcnow()
                    }
                }
            )
        else:
            self.update_autocomplete_cache(user_id, new_text)
    
    def create_section(self, list_id, item_id, section_name):
        list_doc = self.get_list_by_id(list_id)
        if not list_doc:
            return False, 'List not found'
        
        items = list_doc.get('items', [])
        item_found = False
        
        for item in items:
            if str(item['_id']) == str(item_id):
                item['section'] = section_name
                item_found = True
                break
        
        if not item_found:
            return False, 'Item not found'
        
        sorted_items = self._sort_items_with_sections(items)
        
        self.db.lists.update_one(
            {'_id': ObjectId(list_id)},
            {'$set': {'items': sorted_items, 'updated_at': datetime.utcnow()}}
        )
        
        return True, 'Section created successfully'
    
    def rename_section(self, list_id, old_section_name, new_section_name):
        list_doc = self.get_list_by_id(list_id)
        if not list_doc:
            return False, 'List not found'
        
        items = list_doc.get('items', [])
        updated = False
        
        for item in items:
            if item.get('section') == old_section_name:
                item['section'] = new_section_name
                updated = True
        
        if not updated:
            return False, 'Section not found'
        
        sorted_items = self._sort_items_with_sections(items)
        
        self.db.lists.update_one(
            {'_id': ObjectId(list_id)},
            {'$set': {'items': sorted_items, 'updated_at': datetime.utcnow()}}
        )
        
        return True, 'Section renamed successfully'
    
    def delete_section(self, list_id, section_name):
        list_doc = self.get_list_by_id(list_id)
        if not list_doc:
            return False, 'List not found'
        
        items = list_doc.get('items', [])
        filtered_items = [item for item in items if item.get('section') != section_name]
        
        if len(filtered_items) == len(items):
            return False, 'Section not found'
        
        self.db.lists.update_one(
            {'_id': ObjectId(list_id)},
            {'$set': {'items': filtered_items, 'updated_at': datetime.utcnow()}}
        )
        
        return True, 'Section deleted successfully'
    
    def get_sections(self, list_id):
        list_doc = self.get_list_by_id(list_id)
        if not list_doc:
            return []
        
        sections = set()
        for item in list_doc.get('items', []):
            if item.get('section'):
                sections.add(item['section'])
        
        return sorted(list(sections))
    
    def update_user_subscription(self, user_id, stripe_customer_id, stripe_subscription_id, is_ad_free, subscription_start=None, subscription_end=None):
        self.db.users.update_one(
            {'_id': ObjectId(user_id)},
            {'$set': {
                'subscription.stripe_customer_id': stripe_customer_id,
                'subscription.stripe_subscription_id': stripe_subscription_id,
                'subscription.is_ad_free': is_ad_free,
                'subscription.subscription_start': subscription_start or datetime.utcnow(),
                'subscription.subscription_end': subscription_end
            }}
        )
    
    def cancel_user_subscription(self, user_id):
        self.db.users.update_one(
            {'_id': ObjectId(user_id)},
            {'$set': {
                'subscription.is_ad_free': False,
                'subscription.stripe_subscription_id': None,
                'subscription.subscription_end': datetime.utcnow()
            }}
        )
    
    def get_user_by_stripe_customer_id(self, stripe_customer_id):
        return self.db.users.find_one({'subscription.stripe_customer_id': stripe_customer_id})
    
    def add_collaborator(self, list_id, user_id):
        try:
            list_doc = self.get_list_by_id(list_id)
            if not list_doc:
                return False, 'List not found'
            
            collaborators = list_doc.get('collaborators', [])
            user_id_obj = ObjectId(user_id)
            
            if user_id_obj in collaborators:
                return False, 'User is already a collaborator'
            
            if user_id_obj == list_doc['owner_id']:
                return False, 'Owner cannot be added as collaborator'
            
            self.db.lists.update_one(
                {'_id': ObjectId(list_id)},
                {'$push': {'collaborators': user_id_obj}}
            )
            return True, 'Collaborator added successfully'
        except Exception as e:
            return False, f'Database error: {str(e)}'
    
    def remove_collaborator(self, list_id, user_id):
        self.db.lists.update_one(
            {'_id': ObjectId(list_id)},
            {'$pull': {'collaborators': ObjectId(user_id)}}
        )
        return True, 'Collaborator removed successfully'
    
    def get_collaborated_lists(self, user_id):
        return list(self.db.lists.find({
            'collaborators': ObjectId(user_id)
        }).sort('created_at', -1))
    
    def is_collaborator(self, user_id, list_id):
        list_doc = self.get_list_by_id(list_id)
        if not list_doc:
            return False
        collaborators = list_doc.get('collaborators', [])
        return ObjectId(user_id) in collaborators
    
    # Admin methods
    def set_user_admin(self, username, is_admin=True):
        result = self.db.users.update_one(
            {'username': username},
            {'$set': {'is_admin': is_admin}}
        )
        return result.modified_count > 0
    
    def get_all_users(self):
        users = list(self.db.users.find({}).sort('created_at', -1))
        # Remove password_hash from the results
        for user in users:
            user.pop('password_hash', None)
        return users
    
    def update_user_field(self, user_id, field, value):
        # Prevent updating password_hash directly
        if field == 'password_hash':
            return False
        result = self.db.users.update_one(
            {'_id': ObjectId(user_id)},
            {'$set': {field: value}}
        )
        return result.modified_count > 0
    
    def add_user_role(self, user_id, role):
        result = self.db.users.update_one(
            {'_id': ObjectId(user_id)},
            {'$addToSet': {'roles': role}}
        )
        return result.modified_count > 0
    
    def remove_user_role(self, user_id, role):
        result = self.db.users.update_one(
            {'_id': ObjectId(user_id)},
            {'$pull': {'roles': role}}
        )
        return result.modified_count > 0
    
    def add_user_group(self, user_id, group):
        result = self.db.users.update_one(
            {'_id': ObjectId(user_id)},
            {'$addToSet': {'groups': group}}
        )
        return result.modified_count > 0
    
    def remove_user_group(self, user_id, group):
        result = self.db.users.update_one(
            {'_id': ObjectId(user_id)},
            {'$pull': {'groups': group}}
        )
        return result.modified_count > 0
    
    def clone_list(self, list_id, new_owner_id):
        original_list = self.get_list_by_id(list_id)
        if not original_list:
            return None
        
        items_copy = []
        for item in original_list.get('items', []):
            item_copy = {
                '_id': ObjectId(),
                'text': item['text'],
                'quantity': item.get('quantity', 1),
                'added_at': datetime.utcnow()
            }
            if original_list.get('is_ethereal'):
                item_copy['checked'] = False
            items_copy.append(item_copy)
        
        original_items_copy = []
        if original_list.get('is_ethereal'):
            for item in original_list.get('original_items', []):
                original_items_copy.append({
                    '_id': ObjectId(),
                    'text': item['text'],
                    'quantity': item.get('quantity', 1),
                    'checked': False,
                    'added_at': datetime.utcnow()
                })
        
        cloned_list_id = self.create_list(
            name=original_list['name'],
            owner_id=new_owner_id,
            thumbnail_url=original_list.get('thumbnail_url', ''),
            is_public=True,
            is_ethereal=original_list.get('is_ethereal', False),
            tags=original_list.get('tags', []) if original_list.get('tags') else [],
            items=items_copy,
            parent_id=str(list_id)
        )
        
        if original_list.get('is_ethereal') and original_items_copy:
            self.db.lists.update_one(
                {'_id': cloned_list_id},
                {'$set': {'original_items': original_items_copy}}
            )
        
        return cloned_list_id
    
    def get_children_lists(self, list_id):
        return list(self.db.lists.find({'parent_id': ObjectId(list_id)}))
    
    def _create_orphan_list(self, deleted_list):
        items_copy = []
        for item in deleted_list.get('items', []):
            item_copy = {
                '_id': ObjectId(),
                'text': item['text'],
                'quantity': item.get('quantity', 1),
                'added_at': datetime.utcnow()
            }
            if deleted_list.get('is_ethereal'):
                item_copy['checked'] = item.get('checked', False)
            items_copy.append(item_copy)
        
        original_items_copy = []
        if deleted_list.get('is_ethereal'):
            for item in deleted_list.get('original_items', []):
                original_items_copy.append({
                    '_id': ObjectId(),
                    'text': item['text'],
                    'quantity': item.get('quantity', 1),
                    'checked': False,
                    'added_at': datetime.utcnow()
                })
        
        none_user = self.db.users.find_one({'username': 'None'})
        if not none_user:
            password_hash = generate_password_hash('none_user_no_login')
            none_user_id = self.create_user('none@system.internal', 'None', password_hash)
        else:
            none_user_id = none_user['_id']
        
        orphan_list_doc = {
            'name': deleted_list['name'],
            'owner_id': none_user_id,
            'thumbnail_url': deleted_list.get('thumbnail_url', ''),
            'is_public': deleted_list.get('is_public', True),
            'is_ethereal': deleted_list.get('is_ethereal', False),
            'tags': deleted_list.get('tags', []),
            'items': items_copy,
            'collaborators': [],
            'parent_id': None,
            'clone_count': 0,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        
        if deleted_list.get('is_ethereal') and original_items_copy:
            orphan_list_doc['original_items'] = original_items_copy
        
        result = self.db.lists.insert_one(orphan_list_doc)
        return result.inserted_id
