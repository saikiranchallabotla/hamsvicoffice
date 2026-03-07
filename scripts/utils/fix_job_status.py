import re

# Fix tasks.py
with open('core/tasks.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = re.sub(r'Job\.JobStatus\.RUNNING', "'running'", content)
content = re.sub(r'Job\.JobStatus\.COMPLETED', "'completed'", content)
content = re.sub(r'Job\.JobStatus\.FAILED', "'failed'", content)
content = re.sub(r'Job\.JobStatus\.QUEUED', "'queued'", content)
content = re.sub(r'Job\.JobStatus\.PENDING', "'queued'", content)

with open('core/tasks.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed core/tasks.py")

# Fix api_views.py
with open('core/api_views.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = re.sub(r'Job\.JobStatus\.RUNNING', "'running'", content)
content = re.sub(r'Job\.JobStatus\.COMPLETED', "'completed'", content)
content = re.sub(r'Job\.JobStatus\.FAILED', "'failed'", content)
content = re.sub(r'Job\.JobStatus\.QUEUED', "'queued'", content)
content = re.sub(r'Job\.JobStatus\.PENDING', "'queued'", content)

with open('core/api_views.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed core/api_views.py")
print("Done!")
