# admin_panel/data_management_views.py
"""
Backend data management views - upload/replace Excel files without affecting users.
Supports multiple backends per module (state-wise SOR rates).
"""

import os
import shutil
from datetime import datetime
from pathlib import Path
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse, FileResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.conf import settings
import pandas as pd

from admin_panel.decorators import superadmin_required
from subscriptions.models import Module, ModuleBackend


# Data files location
DATA_DIR = Path(settings.BASE_DIR) / 'core' / 'data'
BACKUP_DIR = Path(settings.BASE_DIR) / 'core' / 'data' / 'backups'
MEDIA_BACKENDS_DIR = Path(settings.MEDIA_ROOT) / 'module_backends'


def get_file_info(filepath):
    """Get file metadata."""
    if not filepath.exists():
        return None
    
    stat = filepath.stat()
    return {
        'name': filepath.name,
        'path': str(filepath),
        'size': stat.st_size,
        'size_readable': format_size(stat.st_size),
        'modified': datetime.fromtimestamp(stat.st_mtime),
    }


def format_size(size_bytes):
    """Format bytes to human readable."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def get_excel_preview(filepath, max_rows=10):
    """
    Get preview of Excel file contents.
    Returns dict with sheet names and sample data.
    """
    try:
        xl = pd.ExcelFile(filepath)
        preview = {
            'sheets': [],
            'total_sheets': len(xl.sheet_names)
        }
        
        for sheet_name in xl.sheet_names[:5]:  # Max 5 sheets
            df = pd.read_excel(xl, sheet_name=sheet_name, nrows=max_rows)
            preview['sheets'].append({
                'name': sheet_name,
                'rows': len(df),
                'columns': list(df.columns)[:10],  # First 10 columns
                'total_columns': len(df.columns),
                'sample_data': df.head(5).fillna('').values.tolist()
            })
        
        return preview
    except Exception as e:
        return {'error': str(e)}


@superadmin_required
def data_management(request):
    """
    Main data management page showing current backend files.
    Now supports multiple backends per module for different states/regions.
    """
    # Ensure directories exist
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    MEDIA_BACKENDS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Get modules that can have their own backend data uploads
    # Note: workslip shares backends with new_estimate module
    # temp_works and amc have their own separate backends
    # estimate module doesn't require backend data
    backend_modules = Module.objects.filter(
        code__in=['new_estimate', 'temp_works', 'amc']
    ).order_by('display_order', 'name')
    
    # Get all module backends grouped by module and category
    module_backends_data = []
    for module in backend_modules:
        electrical_backends = ModuleBackend.objects.filter(
            module=module, category='electrical', is_active=True
        ).order_by('display_order', 'name')
        
        civil_backends = ModuleBackend.objects.filter(
            module=module, category='civil', is_active=True
        ).order_by('display_order', 'name')
        
        module_backends_data.append({
            'module': module,
            'electrical_backends': electrical_backends,
            'civil_backends': civil_backends,
        })
    
    # Define all legacy managed files (for backward compatibility)
    legacy_categories = [
        ('civil', DATA_DIR / 'civil.xlsx', 'Civil Data', 'bi-building', '#d97706', 'civil', 'btn-warning'),
        ('electrical', DATA_DIR / 'electrical.xlsx', 'Electrical Data', 'bi-lightning', '#2563eb', 'electrical', 'btn-primary'),
        ('temp_civil', DATA_DIR / 'temp_civil.xlsx', 'Temp Civil Data', 'bi-building', '#f59e42', 'civil', 'btn-warning'),
        ('temp_electrical', DATA_DIR / 'temp_electrical.xlsx', 'Temp Electrical Data', 'bi-lightning', '#3b82f6', 'electrical', 'btn-primary'),
        ('amc_electrical', DATA_DIR / 'amc_electrical.xlsx', 'AMC Electrical Data', 'bi-tools', '#8b5cf6', 'amc_electrical', 'btn-purple'),
        ('amc_civil', DATA_DIR / 'amc_civil.xlsx', 'AMC Civil Data', 'bi-tools', '#a855f7', 'amc_civil', 'btn-purple'),
    ]

    legacy_files = []
    for key, fpath, title, icon, color, icon_class, btn_class in legacy_categories:
        file_info = get_file_info(fpath)
        legacy_files.append({
            'key': key,
            'title': title,
            'icon': icon,
            'color': color,
            'icon_class': icon_class,
            'btn_class': btn_class,
            'file': file_info,
            'upload_label': f'Upload {title}',
        })

    # Bill templates (always legacy)
    bill_templates = [
        {
            'key': 'ls_form_final',
            'title': 'L.S Form Final',
            'icon': 'bi-file-earmark-spreadsheet',
            'color': '#059669',
            'icon_class': 'civil',
            'btn_class': 'btn-success',
            'file': get_file_info(Path(settings.BASE_DIR) / 'core' / 'templates' / 'core' / 'bill_templates' / 'LS_Form_Final.xlsx'),
            'upload_label': 'Upload L.S Form Final',
        },
        {
            'key': 'ls_form_part',
            'title': 'L.S Form Part',
            'icon': 'bi-file-earmark-spreadsheet',
            'color': '#0ea5e9',
            'icon_class': 'electrical',
            'btn_class': 'btn-info',
            'file': get_file_info(Path(settings.BASE_DIR) / 'core' / 'templates' / 'core' / 'bill_templates' / 'LS_Form_Part.xlsx'),
            'upload_label': 'Upload L.S Form Part',
        },
    ]

    # Get backups
    backups = []
    for f in sorted(BACKUP_DIR.glob('*.xlsx'), key=lambda x: x.stat().st_mtime, reverse=True)[:20]:
        info = get_file_info(f)
        if info:
            # Parse backup filename: civil_2026-01-04_153022.xlsx
            parts = f.stem.split('_')
            info['category'] = parts[0] if parts else 'unknown'
            backups.append(info)

    context = {
        'module_backends_data': module_backends_data,
        'legacy_files': legacy_files,
        'bill_templates': bill_templates,
        'backups': backups,
        'data_dir': str(DATA_DIR),
        'modules': backend_modules,
    }
    return render(request, 'admin_panel/data/management.html', context)


@superadmin_required
def preview_file(request, category):
    """
    Preview contents of a backend Excel file.
    """
    allowed = ['civil', 'electrical', 'temp_civil', 'temp_electrical', 'amc_electrical', 'amc_civil', 'ls_form_final', 'ls_form_part']
    if category not in allowed:
        messages.error(request, 'Invalid category.')
        return redirect('admin_data_management')

    if category == 'ls_form_final':
        filepath = Path(settings.BASE_DIR) / 'core' / 'templates' / 'core' / 'bill_templates' / 'LS_Form_Final.xlsx'
    elif category == 'ls_form_part':
        filepath = Path(settings.BASE_DIR) / 'core' / 'templates' / 'core' / 'bill_templates' / 'LS_Form_Part.xlsx'
    else:
        filepath = DATA_DIR / f'{category}.xlsx'

    if not filepath.exists():
        context = {
            'category': category,
            'file_info': None,
            'preview': {'error': f'{category.replace("_", " ").title()} file not found.'},
        }
        return render(request, 'admin_panel/data/preview.html', context)

    preview = get_excel_preview(filepath, max_rows=20)
    file_info = get_file_info(filepath)

    context = {
        'category': category,
        'file_info': file_info,
        'preview': preview,
    }

    return render(request, 'admin_panel/data/preview.html', context)


@superadmin_required
@require_http_methods(["GET", "POST"])
def upload_file(request, category):
    """
    Upload and replace a backend Excel file.
    Automatically backs up the existing file before replacing.
    """
    allowed = ['civil', 'electrical', 'temp_civil', 'temp_electrical', 'amc_electrical', 'amc_civil', 'ls_form_final', 'ls_form_part']
    if category not in allowed:
        messages.error(request, 'Invalid category.')
        return redirect('admin_data_management')

    if category == 'ls_form_final':
        current_file = Path(settings.BASE_DIR) / 'core' / 'templates' / 'core' / 'bill_templates' / 'LS_Form_Final.xlsx'
    elif category == 'ls_form_part':
        current_file = Path(settings.BASE_DIR) / 'core' / 'templates' / 'core' / 'bill_templates' / 'LS_Form_Part.xlsx'
    else:
        current_file = DATA_DIR / f'{category}.xlsx'
    current_info = get_file_info(current_file)

    if request.method == 'POST':
        uploaded_file = request.FILES.get('file')

        if not uploaded_file:
            messages.error(request, 'No file uploaded.')
            return redirect('admin_upload_file', category=category)

        # Validate file extension
        if not uploaded_file.name.endswith(('.xlsx', '.xls')):
            messages.error(request, 'Please upload an Excel file (.xlsx or .xls)')
            return redirect('admin_upload_file', category=category)

        # Validate file by trying to read it
        try:
            # Save temporarily to validate
            temp_path = DATA_DIR / f'temp_{category}.xlsx'
            with open(temp_path, 'wb') as f:
                for chunk in uploaded_file.chunks():
                    f.write(chunk)

            # Try to read with pandas - ensure file is closed after reading
            with pd.ExcelFile(temp_path) as xl:
                sheet_count = len(xl.sheet_names)

            # Backup current file if exists
            if current_file.exists():
                timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
                backup_name = f'{category}_{timestamp}.xlsx'
                backup_path = BACKUP_DIR / backup_name
                shutil.copy2(current_file, backup_path)

            # Replace with new file (use copy + delete for Windows compatibility)
            shutil.copy2(temp_path, current_file)
            try:
                temp_path.unlink()
            except PermissionError:
                pass  # File will be cleaned up later

            # --- AUDIT LOG ---
            from datasets.models import AuditLog
            AuditLog.log(
                user=request.user,
                action='upload',
                obj=f"BackendData:{category}",  # Use string identifier instead of file object
                changes=None,
                metadata={
                    'category': category,
                    'filename': uploaded_file.name,
                    'sheet_count': sheet_count,
                    'backup': str(backup_path) if current_file.exists() else None,
                },
                request=request
            )

            messages.success(
                request,
                f'{category.replace("_", " ").title()} data updated successfully! '
                f'File contains {sheet_count} sheets. Previous version backed up.'
            )
            return redirect('admin_data_management')

        except Exception as e:
            # Clean up temp file - handle Windows file locking
            try:
                if temp_path.exists():
                    temp_path.unlink()
            except PermissionError:
                pass  # File locked, will be cleaned up later
            messages.error(request, f'Error processing file: {str(e)}')
            return redirect('admin_upload_file', category=category)

    # GET - show upload form with preview of current file
    preview = None
    if current_file.exists():
        preview = get_excel_preview(current_file, max_rows=5)

    context = {
        'category': category,
        'current_file': current_info,
        'preview': preview,
    }

    return render(request, 'admin_panel/data/upload.html', context)


@superadmin_required
def download_file(request, category):
    """
    Download current backend Excel file.
    """
    allowed = ['civil', 'electrical', 'temp_civil', 'temp_electrical', 'amc_electrical', 'amc_civil', 'ls_form_final', 'ls_form_part']
    if category not in allowed:
        messages.error(request, 'Invalid category.')
        return redirect('admin_data_management')

    if category == 'ls_form_final':
        filepath = Path(settings.BASE_DIR) / 'core' / 'templates' / 'core' / 'bill_templates' / 'LS_Form_Final.xlsx'
    elif category == 'ls_form_part':
        filepath = Path(settings.BASE_DIR) / 'core' / 'templates' / 'core' / 'bill_templates' / 'LS_Form_Part.xlsx'
    else:
        filepath = DATA_DIR / f'{category}.xlsx'

    if not filepath.exists():
        messages.error(request, f'{category.replace("_", " ").title()} file not found.')
        return redirect('admin_data_management')

    return FileResponse(
        open(filepath, 'rb'),
        as_attachment=True,
        filename=f'{category}.xlsx'
    )


@superadmin_required
def download_backup(request, filename):
    """
    Download a backup file.
    """
    # Sanitize filename to prevent path traversal
    safe_filename = Path(filename).name
    filepath = BACKUP_DIR / safe_filename
    
    if not filepath.exists() or not str(filepath).startswith(str(BACKUP_DIR)):
        messages.error(request, 'Backup file not found.')
        return redirect('admin_data_management')
    
    return FileResponse(
        open(filepath, 'rb'),
        as_attachment=True,
        filename=safe_filename
    )


@superadmin_required
@require_POST
def restore_backup(request, filename):
    """
    Restore a backup file to replace current data.
    """
    safe_filename = Path(filename).name
    backup_path = BACKUP_DIR / safe_filename
    
    if not backup_path.exists() or not str(backup_path).startswith(str(BACKUP_DIR)):
        messages.error(request, 'Backup file not found.')
        return redirect('admin_data_management')
    
    # Determine category from filename
    allowed = ['civil', 'electrical', 'temp_civil', 'temp_electrical', 'amc_electrical', 'amc_civil', 'ls_form_final', 'ls_form_part']
    category = None
    for cat in allowed:
        if safe_filename.startswith(cat):
            category = cat
            break
    if not category:
        messages.error(request, 'Cannot determine file category.')
        return redirect('admin_data_management')

    current_file = DATA_DIR / f'{category}.xlsx'

    try:
        # Backup current file first
        if current_file.exists():
            timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
            pre_restore_backup = BACKUP_DIR / f'{category}_pre_restore_{timestamp}.xlsx'
            shutil.copy2(current_file, pre_restore_backup)

        # Restore from backup
        shutil.copy2(backup_path, current_file)

        # --- AUDIT LOG ---
        from datasets.models import AuditLog
        AuditLog.log(
            user=request.user,
            action='restore',
            obj=current_file,
            changes=None,
            metadata={
                'category': category,
                'restored_from': safe_filename,
                'pre_restore_backup': str(pre_restore_backup),
            },
            request=request
        )
        messages.success(request, f'{category.replace("_", " ").title()} data restored from backup: {safe_filename}')
    except Exception as e:
        messages.error(request, f'Error restoring backup: {str(e)}')

    return redirect('admin_data_management')


@superadmin_required
@require_POST
def delete_backup(request, filename):
    """
    Delete a backup file.
    """
    safe_filename = Path(filename).name
    filepath = BACKUP_DIR / safe_filename
    
    if not filepath.exists() or not str(filepath).startswith(str(BACKUP_DIR)):
        messages.error(request, 'Backup file not found.')
        return redirect('admin_data_management')
    
    try:
        filepath.unlink()
        # --- AUDIT LOG ---
        from datasets.models import AuditLog
        AuditLog.log(
            user=request.user,
            action='delete',
            obj=filepath,
            changes=None,
            metadata={
                'deleted_backup': safe_filename,
            },
            request=request
        )
        messages.success(request, f'Backup deleted: {safe_filename}')
    except Exception as e:
        messages.error(request, f'Error deleting backup: {str(e)}')
    
    return redirect('admin_data_management')


@superadmin_required
def preview_upload(request):
    """
    AJAX endpoint to preview an uploaded file before confirming.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)
    
    uploaded_file = request.FILES.get('file')
    if not uploaded_file:
        return JsonResponse({'error': 'No file provided'}, status=400)
    
    from datasets.models import AuditLog
    try:
        # Read file directly from memory
        xl = pd.ExcelFile(uploaded_file)

        preview = {
            'filename': uploaded_file.name,
            'size': format_size(uploaded_file.size),
            'sheets': []
        }

        for sheet_name in xl.sheet_names[:5]:
            df = pd.read_excel(xl, sheet_name=sheet_name, nrows=5)
            preview['sheets'].append({
                'name': sheet_name,
                'columns': list(df.columns)[:8],
                'row_count': len(pd.read_excel(xl, sheet_name=sheet_name)),
                'sample': df.head(3).fillna('').values.tolist()
            })

        # --- AUDIT LOG ---
        AuditLog.log(
            user=request.user,
            action='preview',
            obj=uploaded_file,
            changes=None,
            metadata={
                'filename': uploaded_file.name,
                'sheet_count': len(xl.sheet_names),
            },
            request=request
        )

        return JsonResponse(preview)

    except Exception as e:
        # --- AUDIT LOG (failure) ---
        AuditLog.log(
            user=request.user,
            action='preview',
            obj=uploaded_file,
            changes=None,
            metadata={
                'filename': uploaded_file.name if uploaded_file else None,
                'error': str(e),
            },
            request=request
        )
        return JsonResponse({'error': 'Failed to preview file.'}, status=400)


# ==============================================================================
# MODULE BACKEND VIEWS (Multi-State SOR Support)
# ==============================================================================

@superadmin_required
@require_http_methods(["GET", "POST"])
def add_module_backend(request, module_code):
    """
    Add a new backend (SOR rates file) for a module.
    Example: Add "AP Electrical SOR 2024" for New Estimate module.
    """
    module = get_object_or_404(Module, code=module_code)
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        code = request.POST.get('code', '').strip()
        category = request.POST.get('category', '')
        description = request.POST.get('description', '').strip()
        is_default = request.POST.get('is_default') == 'on'
        display_order = request.POST.get('display_order', 0)
        uploaded_file = request.FILES.get('file')
        
        # Validation
        errors = []
        if not name:
            errors.append('Name is required.')
        if category not in ['electrical', 'civil']:
            errors.append('Category must be electrical or civil.')
        if not uploaded_file:
            errors.append('Excel file is required.')
        elif not uploaded_file.name.endswith(('.xlsx', '.xls')):
            errors.append('File must be an Excel file (.xlsx or .xls).')
        
        if errors:
            for error in errors:
                messages.error(request, error)
            return redirect('admin_add_module_backend', module_code=module_code)
        
        try:
            # Validate Excel file
            MEDIA_BACKENDS_DIR.mkdir(parents=True, exist_ok=True)
            
            with pd.ExcelFile(uploaded_file) as xl:
                sheet_names = xl.sheet_names
                if 'Master Datas' not in sheet_names and 'Groups' not in sheet_names:
                    messages.warning(
                        request, 
                        'File uploaded but does not contain standard sheets (Master Datas, Groups). '
                        'Please verify the file format.'
                    )
            
            # Read file bytes for DB persistence
            uploaded_file.seek(0)
            file_bytes = uploaded_file.read()
            uploaded_file.seek(0)

            # Compute file hash for integrity tracking
            import hashlib
            file_hash = hashlib.sha256(file_bytes).hexdigest()

            # Create backend with full persistence metadata
            backend = ModuleBackend(
                module=module,
                name=name,
                code=code,
                category=category,
                description=description,
                is_default=is_default,
                display_order=int(display_order) if display_order else 0,
                file=uploaded_file,
                file_data=file_bytes,
                file_name=uploaded_file.name,
                file_hash=file_hash,
                version=1,
                source_type='admin',
                admin_locked=True,  # Admin uploads are protected by default
            )
            backend.save()
            
            # Audit log
            from datasets.models import AuditLog
            AuditLog.log(
                user=request.user,
                action='create',
                obj=f"ModuleBackend:{backend.pk}",
                changes=None,
                metadata={
                    'module': module.name,
                    'backend_name': name,
                    'category': category,
                    'filename': uploaded_file.name,
                },
                request=request
            )
            
            messages.success(
                request,
                f'Backend "{name}" added successfully for {module.name}!'
            )
            return redirect('admin_data_management')
            
        except Exception as e:
            messages.error(request, f'Error processing file: {str(e)}')
            return redirect('admin_add_module_backend', module_code=module_code)
    
    # GET - show form
    context = {
        'module': module,
        'categories': ModuleBackend.CATEGORY_CHOICES,
    }
    return render(request, 'admin_panel/data/add_backend.html', context)


@superadmin_required
@require_http_methods(["GET", "POST"])
def edit_module_backend(request, backend_id):
    """
    Edit an existing module backend.
    """
    backend = get_object_or_404(ModuleBackend, pk=backend_id)
    
    if request.method == 'POST':
        backend.name = request.POST.get('name', '').strip() or backend.name
        backend.code = request.POST.get('code', '').strip()
        backend.description = request.POST.get('description', '').strip()
        backend.is_default = request.POST.get('is_default') == 'on'
        backend.display_order = int(request.POST.get('display_order', 0) or 0)
        backend.is_active = request.POST.get('is_active') == 'on'
        
        # If new file uploaded, replace the old one WITH BACKUP
        uploaded_file = request.FILES.get('file')
        if uploaded_file:
            if not uploaded_file.name.endswith(('.xlsx', '.xls')):
                messages.error(request, 'File must be an Excel file.')
                return redirect('admin_edit_module_backend', backend_id=backend_id)

            try:
                # Validate Excel file
                with pd.ExcelFile(uploaded_file) as xl:
                    pass  # Just validate it's a valid Excel file

                # CREATE BACKUP of existing file before replacing
                from core.deployment_safety import create_backup
                backup_path = create_backup(backend, reason='admin_edit')
                if backup_path:
                    messages.info(
                        request,
                        f'Previous version backed up to: {Path(backup_path).name}'
                    )

                # Delete old disk file (backup already created)
                if backend.file:
                    try:
                        old_path = Path(backend.file.path)
                        if old_path.exists():
                            old_path.unlink()
                    except Exception:
                        pass

                # Save file bytes to DB for persistence
                uploaded_file.seek(0)
                file_bytes = uploaded_file.read()
                uploaded_file.seek(0)

                import hashlib
                backend.file_data = file_bytes
                backend.file_name = uploaded_file.name
                backend.file_hash = hashlib.sha256(file_bytes).hexdigest()
                backend.version = (backend.version or 0) + 1
                backend.source_type = 'admin'
                backend.admin_locked = True  # Admin edits are protected
                backend.file = uploaded_file
            except Exception as e:
                messages.error(request, f'Error processing file: {str(e)}')
                return redirect('admin_edit_module_backend', backend_id=backend_id)

        backend.save()
        
        # Audit log
        from datasets.models import AuditLog
        AuditLog.log(
            user=request.user,
            action='update',
            obj=f"ModuleBackend:{backend.pk}",
            changes=None,
            metadata={
                'backend_name': backend.name,
                'new_file': uploaded_file.name if uploaded_file else None,
            },
            request=request
        )
        
        messages.success(request, f'Backend "{backend.name}" updated successfully!')
        return redirect('admin_data_management')
    
    # GET - show form
    file_info = None
    if backend.file:
        try:
            file_info = get_file_info(Path(backend.file.path))
        except:
            pass
    
    context = {
        'backend': backend,
        'module': backend.module,
        'categories': ModuleBackend.CATEGORY_CHOICES,
        'file_info': file_info,
    }
    return render(request, 'admin_panel/data/edit_backend.html', context)


@superadmin_required
@require_POST
def delete_module_backend(request, backend_id):
    """
    Delete a module backend.
    """
    backend = get_object_or_404(ModuleBackend, pk=backend_id)
    
    # Store info for message
    name = backend.name
    module_name = backend.module.name

    # CREATE BACKUP before deletion (safety net)
    from core.deployment_safety import create_backup
    backup_path = create_backup(backend, reason='admin_delete')
    if backup_path:
        messages.info(
            request,
            f'Backup created before deletion: {Path(backup_path).name}'
        )

    # Delete disk file (backup already created)
    if backend.file:
        try:
            file_path = Path(backend.file.path)
            if file_path.exists():
                file_path.unlink()
        except Exception:
            pass

    # Audit log
    from datasets.models import AuditLog
    AuditLog.log(
        user=request.user,
        action='delete',
        obj=f"ModuleBackend:{backend_id}",
        changes=None,
        metadata={
            'backend_name': name,
            'module': module_name,
        },
        request=request
    )
    
    backend.delete()
    messages.success(request, f'Backend "{name}" deleted successfully!')
    return redirect('admin_data_management')


@superadmin_required
def preview_module_backend(request, backend_id):
    """
    Preview a module backend's Excel file contents.
    """
    backend = get_object_or_404(ModuleBackend, pk=backend_id)
    
    if not backend.file:
        messages.error(request, 'No file associated with this backend.')
        return redirect('admin_data_management')
    
    try:
        filepath = Path(backend.file.path)
        if not filepath.exists():
            messages.error(request, 'Backend file not found.')
            return redirect('admin_data_management')
        
        preview = get_excel_preview(filepath, max_rows=20)
        file_info = get_file_info(filepath)
        
        context = {
            'category': backend.name,
            'backend': backend,
            'file_info': file_info,
            'preview': preview,
        }
        return render(request, 'admin_panel/data/preview.html', context)
        
    except Exception as e:
        messages.error(request, f'Error previewing file: {str(e)}')
        return redirect('admin_data_management')


@superadmin_required
def download_module_backend(request, backend_id):
    """
    Download a module backend's Excel file.
    """
    backend = get_object_or_404(ModuleBackend, pk=backend_id)
    
    if not backend.file:
        messages.error(request, 'No file associated with this backend.')
        return redirect('admin_data_management')
    
    try:
        filepath = Path(backend.file.path)
        if not filepath.exists():
            messages.error(request, 'Backend file not found.')
            return redirect('admin_data_management')
        
        # Generate download filename
        safe_name = backend.name.replace(' ', '_').replace('/', '-')
        download_name = f'{safe_name}_{backend.category}.xlsx'
        
        return FileResponse(
            open(filepath, 'rb'),
            as_attachment=True,
            filename=download_name
        )
    except Exception as e:
        messages.error(request, f'Error downloading file: {str(e)}')
        return redirect('admin_data_management')


@superadmin_required
@require_POST
def toggle_backend_default(request, backend_id):
    """
    Toggle a backend as default for its module and category.
    """
    backend = get_object_or_404(ModuleBackend, pk=backend_id)
    
    # Toggle default status
    backend.is_default = not backend.is_default
    backend.save()
    
    if backend.is_default:
        messages.success(request, f'"{backend.name}" is now the default for {backend.get_category_display()} in {backend.module.name}.')
    else:
        messages.info(request, f'"{backend.name}" is no longer the default.')
    
    return redirect('admin_data_management')

