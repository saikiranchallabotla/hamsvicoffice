"""
Deployment Safety Module - Non-destructive backend file management.

This module provides:
1. Hash-based integrity verification before any file operation
2. Structured backup system with timestamped archives
3. Deployment change logging
4. Conflict detection between disk, DB, and static templates
5. Rollback capability via backup restoration

Design principles:
- Admin modifications are AUTHORITATIVE and never silently overwritten
- Every file operation is logged with before/after state
- Backups are always created before any destructive operation
- Hash comparison prevents unnecessary writes
- The deployment process is idempotent and deterministic
"""

import os
import hashlib
import shutil
import json
import logging
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger('deployment_safety')


# ==============================================================================
# BACKUP SYSTEM
# ==============================================================================

def get_backup_dir():
    """Get the structured backup directory, creating it if needed."""
    backup_base = Path(settings.MEDIA_ROOT) / 'backend_backups'
    backup_base.mkdir(parents=True, exist_ok=True)
    return backup_base


def create_backup(backend, reason='deployment'):
    """
    Create a timestamped backup of a backend file before any modification.

    Structure: backend_backups/<module_code>/<category>/<timestamp>_v<version>_<filename>

    Args:
        backend: ModuleBackend instance
        reason: Why the backup is being created (deployment, admin_edit, restore, etc.)

    Returns:
        Path to backup file, or None if no data to back up
    """
    backup_base = get_backup_dir()

    # Create module/category subdirectory
    module_dir = backup_base / backend.module.code / backend.category
    module_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    version = getattr(backend, 'version', 0) or 0
    original_name = backend.file_name or 'unknown.xlsx'
    safe_name = original_name.replace('/', '_').replace('\\', '_')

    backup_filename = f"{timestamp}_v{version}_{reason}_{safe_name}"
    backup_path = module_dir / backup_filename

    # Try to backup from DB first (authoritative), then from disk
    data = None
    if backend.file_data:
        data = bytes(backend.file_data)
    elif backend.file:
        try:
            file_path = backend.file.path
            if os.path.exists(file_path):
                with open(file_path, 'rb') as f:
                    data = f.read()
        except Exception:
            pass

    if data is None:
        return None

    try:
        with open(backup_path, 'wb') as f:
            f.write(data)

        # Write metadata sidecar
        meta = {
            'backend_id': backend.pk,
            'backend_name': backend.name,
            'module_code': backend.module.code,
            'category': backend.category,
            'version': version,
            'file_hash': backend.file_hash or compute_file_hash(data),
            'original_filename': original_name,
            'reason': reason,
            'timestamp': timestamp,
            'source_type': getattr(backend, 'source_type', ''),
            'admin_locked': getattr(backend, 'admin_locked', False),
        }
        meta_path = backup_path.with_suffix('.json')
        with open(meta_path, 'w') as f:
            json.dump(meta, f, indent=2, default=str)

        logger.info(
            f"[BACKUP] Created: {backup_path.name} for backend '{backend.name}' "
            f"(reason={reason}, version=v{version})"
        )
        return backup_path

    except Exception as e:
        logger.error(f"[BACKUP] Failed for backend '{backend.name}': {e}")
        return None


def list_backups(module_code=None, category=None, limit=50):
    """
    List available backups, optionally filtered by module and category.

    Returns list of dicts with backup metadata.
    """
    backup_base = get_backup_dir()
    backups = []

    if module_code and category:
        search_dir = backup_base / module_code / category
        if not search_dir.exists():
            return []
        dirs_to_search = [search_dir]
    elif module_code:
        search_dir = backup_base / module_code
        if not search_dir.exists():
            return []
        dirs_to_search = [d for d in search_dir.iterdir() if d.is_dir()]
    else:
        dirs_to_search = []
        for mod_dir in backup_base.iterdir():
            if mod_dir.is_dir():
                for cat_dir in mod_dir.iterdir():
                    if cat_dir.is_dir():
                        dirs_to_search.append(cat_dir)

    for d in dirs_to_search:
        for f in d.glob('*.xlsx'):
            meta_path = f.with_suffix('.json')
            meta = {}
            if meta_path.exists():
                try:
                    with open(meta_path) as mf:
                        meta = json.load(mf)
                except Exception:
                    pass

            backups.append({
                'path': str(f),
                'filename': f.name,
                'size': f.stat().st_size,
                'modified': datetime.fromtimestamp(f.stat().st_mtime),
                **meta,
            })

    # Sort by modification time descending
    backups.sort(key=lambda x: x.get('modified', datetime.min), reverse=True)
    return backups[:limit]


# ==============================================================================
# HASH & INTEGRITY
# ==============================================================================

def compute_file_hash(data):
    """Compute SHA-256 hash of binary data."""
    if data is None:
        return ''
    if isinstance(data, memoryview):
        data = bytes(data)
    return hashlib.sha256(data).hexdigest()


def compute_file_hash_from_path(filepath):
    """Compute SHA-256 hash of a file on disk."""
    if not os.path.exists(filepath):
        return ''
    with open(filepath, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def verify_backend_integrity(backend):
    """
    Full integrity check for a backend:
    - Compare DB file_data hash vs stored file_hash
    - Compare disk file hash vs DB file_data hash
    - Detect conflicts between disk and DB

    Returns a dict with status and details.
    """
    result = {
        'backend_id': backend.pk,
        'backend_name': backend.name,
        'status': 'unknown',
        'disk_exists': False,
        'db_has_data': bool(backend.file_data),
        'has_stored_hash': bool(backend.file_hash),
        'disk_hash': '',
        'db_hash': '',
        'stored_hash': backend.file_hash or '',
        'conflicts': [],
    }

    # Check disk file
    disk_path = None
    try:
        if backend.file:
            disk_path = backend.file.path
            result['disk_exists'] = os.path.exists(disk_path)
    except Exception:
        result['disk_exists'] = False

    # Compute DB hash
    if backend.file_data:
        result['db_hash'] = compute_file_hash(bytes(backend.file_data))

    # Compute disk hash
    if result['disk_exists'] and disk_path:
        result['disk_hash'] = compute_file_hash_from_path(disk_path)

    # Detect conflicts
    if result['disk_exists'] and result['db_has_data']:
        if result['disk_hash'] != result['db_hash']:
            result['conflicts'].append('disk_db_mismatch')

    if result['has_stored_hash'] and result['db_has_data']:
        if result['stored_hash'] != result['db_hash']:
            result['conflicts'].append('stored_hash_db_mismatch')

    if result['has_stored_hash'] and result['disk_exists']:
        if result['stored_hash'] != result['disk_hash']:
            result['conflicts'].append('stored_hash_disk_mismatch')

    # Overall status
    if not result['db_has_data'] and not result['disk_exists']:
        result['status'] = 'missing'
    elif result['conflicts']:
        result['status'] = 'conflict'
    elif result['db_has_data'] and result['disk_exists']:
        result['status'] = 'healthy'
    elif result['db_has_data']:
        result['status'] = 'disk_missing'
    else:
        result['status'] = 'db_missing'

    return result


# ==============================================================================
# DEPLOYMENT CHANGE LOG
# ==============================================================================

def log_deployment_event(event_type, details, backend=None):
    """
    Log a deployment event for audit trail.

    Events are logged both to Python logging and to a deployment log file.
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    backend_info = ''
    if backend:
        backend_info = f" [backend={backend.pk} '{backend.name}']"

    log_message = f"[DEPLOY:{event_type}]{backend_info} {details}"
    logger.info(log_message)
    print(f"[INIT] {log_message}")

    # Also write to deployment log file
    try:
        log_dir = Path(settings.MEDIA_ROOT) / 'deployment_logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"deploy_{datetime.now().strftime('%Y%m%d')}.log"
        with open(log_file, 'a') as f:
            f.write(f"{timestamp} {log_message}\n")
    except Exception:
        pass


# ==============================================================================
# SAFE FILE OPERATIONS
# ==============================================================================

def safe_write_backend_file(backend, data, dest_path, reason='restore'):
    """
    Safely write a backend file to disk with full safety checks.

    Steps:
    1. Check if admin_locked - refuse if locked
    2. If file exists on disk, compare hashes - skip if identical
    3. If file exists and differs, create backup first
    4. Write the new file
    5. Update file_hash

    Returns: (success, action_taken, details)
        action_taken: 'skipped_locked', 'skipped_identical', 'written_new', 'written_with_backup'
    """
    # 1. Respect admin lock
    if getattr(backend, 'admin_locked', False):
        log_deployment_event(
            'BLOCKED',
            f"Skipping admin-locked backend (version=v{backend.version})",
            backend=backend,
        )
        return True, 'skipped_locked', {'reason': 'admin_locked'}

    new_hash = compute_file_hash(data)

    # 2. Check if disk file exists and compare
    if os.path.exists(dest_path):
        existing_hash = compute_file_hash_from_path(dest_path)
        if existing_hash == new_hash:
            log_deployment_event(
                'SKIP',
                f"File identical on disk (hash={new_hash[:12]}...)",
                backend=backend,
            )
            return True, 'skipped_identical', {'hash': new_hash}

        # 3. File differs - create backup before overwriting
        backup_path = create_backup(backend, reason=f'pre_{reason}')
        log_deployment_event(
            'BACKUP',
            f"Backup created at {backup_path} before {reason}",
            backend=backend,
        )

    # 4. Write the file
    try:
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        with open(dest_path, 'wb') as f:
            f.write(data)

        action = 'written_with_backup' if os.path.exists(dest_path) else 'written_new'
        log_deployment_event(
            'WRITE',
            f"File written to {dest_path} (hash={new_hash[:12]}...)",
            backend=backend,
        )
        return True, action, {'hash': new_hash, 'path': dest_path}

    except Exception as e:
        log_deployment_event(
            'ERROR',
            f"Failed to write file: {e}",
            backend=backend,
        )
        return False, 'error', {'error': str(e)}


# ==============================================================================
# PRE-DEPLOYMENT VALIDATION
# ==============================================================================

def run_pre_deployment_checks():
    """
    Run comprehensive pre-deployment validation.

    Returns: (all_ok, report_dict)
    """
    from subscriptions.models import ModuleBackend

    report = {
        'timestamp': datetime.now().isoformat(),
        'total_backends': 0,
        'healthy': 0,
        'disk_missing': 0,
        'db_missing': 0,
        'conflicts': 0,
        'missing': 0,
        'admin_locked': 0,
        'details': [],
    }

    for backend in ModuleBackend.objects.filter(is_active=True):
        report['total_backends'] += 1
        integrity = verify_backend_integrity(backend)
        report['details'].append(integrity)

        status = integrity['status']
        if status == 'healthy':
            report['healthy'] += 1
        elif status == 'disk_missing':
            report['disk_missing'] += 1
        elif status == 'db_missing':
            report['db_missing'] += 1
        elif status == 'conflict':
            report['conflicts'] += 1
        elif status == 'missing':
            report['missing'] += 1

        if getattr(backend, 'admin_locked', False):
            report['admin_locked'] += 1

    all_ok = report['conflicts'] == 0 and report['missing'] == 0
    return all_ok, report
