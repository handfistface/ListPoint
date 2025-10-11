from database import Database

db = Database()

all_lists = list(db.db.lists.find({}))
total_lists = len(all_lists)
public_lists = len([l for l in all_lists if l.get('is_public', False)])
private_lists = len([l for l in all_lists if not l.get('is_public', False)])

print(f"Total lists: {total_lists}")
print(f"Public lists: {public_lists}")
print(f"Private lists: {private_lists}")

if private_lists > 0:
    print("\nPrivate lists found:")
    for l in all_lists:
        if not l.get('is_public', False):
            print(f"  - {l['name']} (ID: {l['_id']})")
else:
    print("\n✓ All lists are public!")
