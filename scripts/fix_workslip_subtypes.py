"""
Script to add subtype grouping logic to workslip_views.py
"""
import os

filepath = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'core', 'views', 'workslip_views.py')

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

old_text = '    items_in_group = [name for name in group_items if name in detected_names]\n\n'

new_text = '''    items_in_group = [name for name in group_items if name in detected_names]

    # Build item subtypes map: items with ":" are subtypes
    # Group subtypes by their parent name (part before ":")
    import re as _re
    _colon_re = _re.compile(r'\\s*:\\s*')

    def _has_colon(name):
        return bool(_colon_re.search(name))

    def _split_parent(name):
        return _colon_re.split(name, 1)[0].strip()

    item_subtypes = {}
    parent_items_set = set()

    for name in items_in_group:
        if _has_colon(name):
            parent_name = _split_parent(name)
            if parent_name not in item_subtypes:
                item_subtypes[parent_name] = []
            item_subtypes[parent_name].append(name)
            parent_items_set.add(parent_name)

    items_info = []
    seen_parents = set()
    for name in items_in_group:
        if _has_colon(name):
            parent_name = _split_parent(name)
            if parent_name not in seen_parents:
                subtypes_list = item_subtypes.get(parent_name, [])
                items_info.append({
                    "name": parent_name,
                    "has_subtypes": True,
                    "subtypes": json.dumps(subtypes_list),
                    "subtypes_count": len(subtypes_list),
                })
                seen_parents.add(parent_name)
        else:
            items_info.append({
                "name": name,
                "has_subtypes": False,
                "subtypes": "[]",
                "subtypes_count": 0,
            })

'''

if old_text in content:
    content = content.replace(old_text, new_text, 1)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print('Step 1: Subtype grouping logic added successfully!')
else:
    print('ERROR: Could not find old text to replace')
    # Debug: show nearby text
    idx = content.find('items_in_group = [name for name')
    if idx >= 0:
        print(f'Found at index {idx}')
        print(repr(content[idx:idx+100]))
    else:
        print('items_in_group line not found at all')
