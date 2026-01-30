# core/api_views.py
"""
REST-like API views for job status, uploads, and file management.
All views are organization-scoped.
"""

import json
from django.http import JsonResponse, FileResponse, Http404
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from django.core.files.storage import default_storage
from django.urls import reverse
from core.models import Job, Upload, OutputFile
from core.decorators import org_required


@require_http_methods(["GET"])
@org_required
def job_status(request, job_id):
    """
    Get job status and progress.
    
    URL: /api/jobs/<job_id>/status/
    Returns: JSON with status, progress, current_step, output files, errors
    """
    try:
        job = Job.objects.get(
            id=job_id,
            organization=request.organization,
        )
    except Job.DoesNotExist:
        return JsonResponse({'error': 'Job not found'}, status=404)
    
    # Get output files for this job
    outputs = []
    for output_file in job.outputfile_set.all():
        outputs.append({
            'id': output_file.id,
            'filename': output_file.filename,
            'file_type': output_file.file_type,
            'file_size': output_file.file_size,
            'download_url': reverse('download_output_file', kwargs={'file_id': output_file.id}),
            'download_count': output_file.download_count,
        })
    
    return JsonResponse({
        'id': job.id,
        'status': job.status,
        'progress': job.progress,
        'current_step': job.current_step,
        'started_at': job.started_at.isoformat() if job.started_at else None,
        'completed_at': job.completed_at.isoformat() if job.completed_at else None,
        'error_message': job.error_message,
        'error_log': job.error_log,
        'result_summary': (
            json.dumps(job.result, indent=2) if job.result else None
        ),
        'outputs': outputs,
        'is_complete': job.is_complete(),
        'is_success': job.status == 'completed',
        'is_failed': job.status == 'failed',
    })


@require_http_methods(["GET"])
@org_required
def upload_status(request, upload_id):
    """
    Get upload status.
    
    URL: /api/uploads/<upload_id>/status/
    Returns: JSON with upload status and associated job
    """
    try:
        upload = Upload.objects.get(
            id=upload_id,
            organization=request.organization,
        )
    except Upload.DoesNotExist:
        return JsonResponse({'error': 'Upload not found'}, status=404)
    
    job_data = None
    job = upload.jobs.first()
    if job:
        job_data = {
            'id': job.id,
            'status': job.status,
            'progress': job.progress,
            'status_url': reverse('job_status', kwargs={'job_id': job.id}),
        }
    
    return JsonResponse({
        'id': upload.id,
        'filename': upload.filename,
        'status': upload.status,
        'file_size': upload.file_size,
        'created_at': upload.created_at.isoformat(),
        'job': job_data,
    })


@require_http_methods(["GET"])
@org_required
def download_output_file(request, file_id):
    """
    Download an output file with tracking.
    Uses signed URL for secure S3/DO Spaces access.
    
    URL: /api/outputs/<file_id>/download/
    """
    try:
        output_file = OutputFile.objects.get(
            id=file_id,
            job__organization=request.organization,
        )
    except OutputFile.DoesNotExist:
        return JsonResponse({'error': 'File not found'}, status=404)
    
    # Increment download counter atomically to prevent race conditions
    from django.db.models import F
    OutputFile.objects.filter(id=file_id).update(download_count=F('download_count') + 1)
    
    # For S3/DO Spaces, generate signed URL
    if hasattr(default_storage, 'url'):
        file_url = default_storage.url(output_file.file.name)
        
        # If using signed URLs (django-storages), redirect to it
        if 'Signature=' in file_url or 'X-Amz-Signature=' in file_url:
            return JsonResponse({'download_url': file_url})
    
    # Fallback: serve file directly (for local storage)
    try:
        file_content = output_file.file.read()
        response = FileResponse(
            file_content,
            as_attachment=True,
            filename=output_file.filename
        )
        response['Content-Type'] = 'application/octet-stream'
        return response
    except Exception:
        return JsonResponse(
            {'error': 'An unexpected error occurred while downloading the file.'},
            status=500
        )


@require_http_methods(["GET"])
@org_required
def list_outputs(request):
    """
    List all output files for the organization.
    
    URL: /api/outputs/
    Query params: ?job_id=<id> (optional filter by job)
    Returns: JSON list of output files
    """
    outputs = OutputFile.objects.filter(
        job__organization=request.organization
    ).select_related('job').order_by('-created_at')
    
    # Optional filter by job_id
    job_id = request.GET.get('job_id')
    if job_id:
        outputs = outputs.filter(job_id=job_id)
    
    output_list = []
    for output_file in outputs:
        output_list.append({
            'id': output_file.id,
            'filename': output_file.filename,
            'file_type': output_file.file_type,
            'file_size': output_file.file_size,
            'created_at': output_file.created_at.isoformat(),
            'download_count': output_file.download_count,
            'last_downloaded': (
                output_file.last_downloaded.isoformat()
                if output_file.last_downloaded else None
            ),
            'job_id': output_file.job.id,
            'job_status': output_file.job.status,
            'download_url': reverse('download_output_file', kwargs={'file_id': output_file.id}),
        })
    
    return JsonResponse({'outputs': output_list})


from django.views.decorators.csrf import csrf_protect

@require_http_methods(["POST"])
@org_required
@csrf_protect
def create_job(request):
    """
    Create a new job (typically after uploading a file).
    
    URL: /api/jobs/create/
    POST data: {
        "upload_id": <id>,
        "job_type": "excel_parse|generate_bill|generate_workslip",
        "metadata": {...}  # optional extra data
    }
    Returns: JSON with job_id and status_url
    """
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    upload_id = body.get('upload_id')
    job_type = body.get('job_type', 'excel_parse')
    metadata = body.get('metadata', {})
    
    # Verify upload exists and belongs to user's org
    try:
        upload = Upload.objects.get(
            id=upload_id,
            organization=request.organization,
        )
    except Upload.DoesNotExist:
        return JsonResponse({'error': 'Upload not found'}, status=404)
    
    # Create job
    job = Job.objects.create(
        organization=request.organization,
        user=request.user,
        upload=upload,
        job_type=job_type,
        status='queued',
        result={'metadata': metadata or {}},
    )
    
    # Job already linked to upload via upload FK
    upload.status = 'processing'
    upload.save()
    
    # Enqueue appropriate task
    from core.tasks import (
        process_excel_upload,
        generate_bill_pdf,
        generate_workslip_pdf,
    )
    
    if job_type == 'excel_parse':
        task = process_excel_upload.delay(upload.id)
        job.celery_task_id = task.id
        job.save()
    elif job_type == 'generate_bill':
        project_id = metadata.get('project_id')
        if not project_id:
            job.status = 'failed'
            job.error_message = "project_id required for bill generation"
            job.save()
            return JsonResponse({'error': 'project_id required'}, status=400)
        task = generate_bill_pdf.delay(job.id, project_id)
        job.celery_task_id = task.id
        job.save()
    elif job_type == 'generate_workslip':
        project_id = metadata.get('project_id')
        if not project_id:
            job.status = 'failed'
            job.error_message = "project_id required for workslip generation"
            job.save()
            return JsonResponse({'error': 'project_id required'}, status=400)
        task = generate_workslip_pdf.delay(job.id, project_id)
        job.celery_task_id = task.id
        job.save()
    
    return JsonResponse({
        'job_id': job.id,
        'status': job.status,
        'status_url': reverse('job_status', kwargs={'job_id': job.id}),
        'celery_task_id': job.celery_task_id,
    })
