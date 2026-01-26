# ==============================================================================
# Gunicorn Configuration for HAMSVIC
# ==============================================================================
# Run with: gunicorn -c gunicorn.conf.py estimate_site.wsgi:application

import multiprocessing
import os

# Server socket - Use PORT from environment (Railway/Heroku) or default to 8000
port = os.environ.get("PORT", "8000")
bind = f"0.0.0.0:{port}"
backlog = 2048

# Worker processes
# Formula: (2 x CPU cores) + 1
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"  # Use "gevent" for async if needed
worker_connections = 1000
timeout = 300  # 5 minutes for Excel processing
keepalive = 5
max_requests = 1000
max_requests_jitter = 50

# Process naming
proc_name = "hamsvic"

# Logging - Use stdout/stderr for cloud platforms
accesslog = "-"  # stdout
errorlog = "-"   # stderr
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(L)s'

# Security
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# Server mechanics
daemon = False  # Let container manage the process
pidfile = None  # No pidfile in containers
user = None     # Run as current user
group = None
tmp_upload_dir = None

# Environment
raw_env = [
    f"DJANGO_SETTINGS_MODULE=estimate_site.settings",
]

# Hooks
def on_starting(server):
    """Called before the master process is initialized."""
    pass

def on_reload(server):
    """Called to recycle workers during a reload via SIGHUP."""
    pass

def worker_exit(server, worker):
    """Called just after a worker has been exited."""
    pass
