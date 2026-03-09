"""Replace old inline replaceState script with static JS file include."""
import re
import glob
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
os.chdir('..')

old_pattern = re.compile(
    r'[ \t]*<script>\s*\n'
    r'\s*\(function\(\)\{\s*\n'
    r'\s*try\{\s*\n'
    r'\s*var key=\'_hamsvic_entered\';\s*\n'
    r'\s*if\(sessionStorage\.getItem\(key\)\)\{\s*\n'
    r'\s*history\.replaceState\(null,\'\',location\.href\);\s*\n'
    r'\s*\}else\{\s*\n'
    r'\s*sessionStorage\.setItem\(key,\'1\'\);\s*\n'
    r'\s*\}\s*\n'
    r'\s*\}catch\(e\)\{\}\s*\n'
    r'\s*\}\)\(\);\s*\n'
    r'\s*</script>'
)

new_text = "\n    <script src=\"{% static 'js/no-history.js' %}\"></script>"

files_changed = []
for pattern in [
    'core/templates/**/*.html',
    'admin_panel/templates/**/*.html',
    'accounts/templates/**/*.html',
    'subscriptions/templates/**/*.html',
    'support/templates/**/*.html',
    'templates/**/*.html',
]:
    for f in glob.glob(pattern, recursive=True):
        with open(f, 'r', encoding='utf-8') as fh:
            content = fh.read()
        if '_hamsvic_entered' not in content:
            continue
        new_content = old_pattern.sub(new_text, content)
        if new_content == content:
            print(f'  WARNING: regex did not match in {f}')
            continue
        # Add {% load static %} if not present
        if '{% load static %}' not in new_content:
            new_content = '{% load static %}\n' + new_content
        with open(f, 'w', encoding='utf-8') as fh:
            fh.write(new_content)
        files_changed.append(f)

print(f'Updated {len(files_changed)} files:')
for f in sorted(files_changed):
    print(f'  {f}')
