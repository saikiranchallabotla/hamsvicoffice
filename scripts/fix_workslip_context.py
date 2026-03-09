"""
Script to add items_info to all context dictionaries in workslip_views.py
"""
import os

filepath = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'core', 'views', 'workslip_views.py')

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Check quoting style
print(f"Total 'items_in_group' occurrences: {content.count('items_in_group')}")
print(f'Double-quoted: {content.count(chr(34) + "items_in_group" + chr(34))}')
print(f'Single-quoted: {content.count(chr(39) + "items_in_group" + chr(39))}')

# Replace: add items_info after items_in_group in context dicts
# The pattern is: "items_in_group": items_in_group,
old_pattern = '"items_in_group": items_in_group,'
new_pattern = '"items_in_group": items_in_group, "items_info": items_info,'

count = content.count(old_pattern)
print(f"Found {count} occurrences of the pattern to replace")

if count > 0:
    content = content.replace(old_pattern, new_pattern)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Replaced {count} occurrences successfully!")
else:
    # Show context around items_in_group occurrences
    import re
    for m in re.finditer(r'items_in_group', content):
        pos = m.start()
        snippet = content[max(0, pos-20):pos+60]
        print(f"  Context: {repr(snippet)}")
