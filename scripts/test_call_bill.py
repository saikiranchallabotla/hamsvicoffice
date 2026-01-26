import os
from django.test import RequestFactory
import os
import sys
# ensure project root is on sys.path
sys.path.insert(0, r"C:\Users\HP\Documents\Windows x 1")
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'estimate_site.settings')
import django
django.setup()
from core import views
req = RequestFactory().get('/bill/')
res = views.bill(req)
print('TYPE:', type(res))
print('VALUE:', repr(res))
if res is None:
    print('Returned None')
else:
    try:
        print('status_code:', getattr(res, 'status_code', None))
    except Exception as e:
        print('status access error:', e)
