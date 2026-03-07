#!/usr/bin/env python
"""Fix corrupted dash characters in views.py"""

# Read file
with open('core/views.py', 'rb') as f:
    content = f.read()

# The corrupted bytes for corrupted en-dash (mojibake)
corrupted = b'\xc3\xa2\xe2\x82\xac\xe2\x80\x9c'
simple_dash = b' - '

# Count occurrences
count = content.count(corrupted)
print(f'Found {count} corrupted dash characters')

# Replace
new_content = content.replace(corrupted, simple_dash)

# Write back
with open('core/views.py', 'wb') as f:
    f.write(new_content)

print('Fixed!')
