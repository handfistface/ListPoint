from database import Database

db = Database()

result = db.db.lists.update_many(
    {},
    {'$set': {'is_public': True}}
)

print(f"Updated {result.modified_count} lists to be public")
