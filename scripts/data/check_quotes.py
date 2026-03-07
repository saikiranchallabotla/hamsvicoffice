import re

with open('core/views.py', 'r', encoding='utf-8-sig') as f:
    content = f.read()
    lines = content.split('\n')

# Find all triple quote positions
triple_double_pattern = re.compile(r'"""')
matches = list(triple_double_pattern.finditer(content))

print(f"Found {len(matches)} triple-double-quote occurrences")

if len(matches) % 2 != 0:
    print("ODD NUMBER - there's an unclosed triple-quote!")
    
# Show last few matches
for m in matches[-10:]:
    pos = m.start()
    line_num = content[:pos].count('\n') + 1
    # Get context
    start = max(0, pos - 30)
    end = min(len(content), pos + 40)
    context = content[start:end].replace('\n', '\\n')
    print(f"Line {line_num}: ...{context}...")
