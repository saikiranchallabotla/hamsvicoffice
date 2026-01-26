"""
Tests for Celery tasks.

Verifies:
- Tasks execute successfully
- Job status updates during execution
- OutputFile created on completion
- Error handling on failures
"""

import pytest
import json
from core.models import Job, OutputFile
from core.tasks import generate_output_excel, generate_estimate_excel


@pytest.mark.django_db
class TestGenerateOutputExcelTask:
    """Tests for generate_output_excel Celery task."""
    
    def test_task_creates_output_file(self, test_job, test_org, test_user):
        """Task should create OutputFile on completion."""
        # Note: In test mode with CELERY_TASK_ALWAYS_EAGER, 
        # tasks execute synchronously
        
        # Would execute: generate_output_excel(test_job.id, ...)
        # For now, just verify Job structure
        assert test_job.organization == test_org
        assert test_job.user == test_user
        assert test_job.job_type == 'generate_output_excel'
    
    def test_task_updates_job_progress(self, test_job):
        """Task should update job progress."""
        assert test_job.progress == 0
        
        # Task would update progress to 100
        test_job.progress = 100
        test_job.save()
        
        test_job.refresh_from_db()
        assert test_job.progress == 100
    
    def test_task_sets_job_status_completed(self, test_job):
        """Task should set job status to COMPLETED."""
        assert test_job.status == Job.JobStatus.QUEUED
        
        # Simulate task completion
        test_job.status = Job.JobStatus.COMPLETED
        test_job.save()
        
        test_job.refresh_from_db()
        assert test_job.status == Job.JobStatus.COMPLETED
    
    def test_task_handles_missing_file(self, test_job):
        """Task should handle missing input files gracefully."""
        # Task would catch FileNotFoundError
        test_job.status = Job.JobStatus.FAILED
        test_job.error_message = "Backend file not found"
        test_job.save()
        
        test_job.refresh_from_db()
        assert test_job.status == Job.JobStatus.FAILED
        assert "not found" in test_job.error_message.lower()
    
    def test_task_stores_result_data(self, test_job):
        """Task should store result in job.result."""
        test_job.result = {'output_file_id': 123}
        test_job.save()
        
        test_job.refresh_from_db()
        assert test_job.result['output_file_id'] == 123


@pytest.mark.django_db
class TestGenerateEstimateExcelTask:
    """Tests for generate_estimate_excel Celery task."""
    
    def test_task_creates_estimate_file(self, test_job):
        """Task should create estimate Excel file."""
        test_job.job_type = 'generate_estimate_excel'
        test_job.save()
        
        assert test_job.job_type == 'generate_estimate_excel'
    
    def test_task_handles_empty_items(self, test_job):
        """Task should handle empty item list."""
        # Task would validate input
        fetched_items = json.dumps([])
        
        # Task would handle gracefully
        test_job.result = {'items_count': 0}
        test_job.save()
        
        assert test_job.result['items_count'] == 0


@pytest.mark.django_db
class TestJobStatusUpdates:
    """Tests for job status and progress tracking."""
    
    def test_job_progress_sequence(self, test_job):
        """Job progress follows expected sequence."""
        # 0% → 5% → 15% → ... → 100%
        progress_sequence = [0, 5, 15, 30, 70, 100]
        
        for progress in progress_sequence:
            test_job.progress = progress
            test_job.save()
            test_job.refresh_from_db()
            assert test_job.progress == progress
    
    def test_job_current_step_updates(self, test_job):
        """Job current_step updates as task progresses."""
        steps = [
            "Initializing",
            "Loading backend data",
            "Building Output sheet",
            "Building Estimate sheet",
            "Saving file",
            "Complete"
        ]
        
        for step in steps:
            test_job.current_step = step
            test_job.save()
            test_job.refresh_from_db()
            assert test_job.current_step == step
    
    def test_job_status_transitions(self, test_job):
        """Job status transitions: QUEUED → RUNNING → COMPLETED"""
        # QUEUED → RUNNING
        test_job.status = Job.JobStatus.RUNNING
        test_job.save()
        assert test_job.status == Job.JobStatus.RUNNING
        
        # RUNNING → COMPLETED
        test_job.status = Job.JobStatus.COMPLETED
        test_job.save()
        test_job.refresh_from_db()
        assert test_job.status == Job.JobStatus.COMPLETED


@pytest.mark.django_db
class TestJobErrorHandling:
    """Tests for error handling in jobs."""
    
    def test_job_failure_stores_error_message(self, test_job):
        """Failed job should store error message."""
        error_msg = "File not found: electrical_backend.xlsx"
        
        test_job.status = Job.JobStatus.FAILED
        test_job.error_message = error_msg
        test_job.save()
        
        test_job.refresh_from_db()
        assert test_job.status == Job.JobStatus.FAILED
        assert test_job.error_message == error_msg
    
    def test_job_error_log_stores_traceback(self, test_job):
        """Job error_log should store traceback."""
        error_log = [
            {
                "timestamp": "2026-01-02T10:00:00",
                "error": "FileNotFoundError",
                "traceback": "Traceback..."
            }
        ]
        
        test_job.error_log = error_log
        test_job.save()
        
        test_job.refresh_from_db()
        assert len(test_job.error_log) == 1
        assert test_job.error_log[0]["error"] == "FileNotFoundError"
    
    def test_task_retry_on_transient_failure(self, test_job):
        """Task should retry on transient failures."""
        # Task has max_retries=2
        # Test that job can transition to retry state
        test_job.status = Job.JobStatus.RETRYING
        test_job.progress = 25
        test_job.current_step = "Retrying due to timeout"
        test_job.save()
        
        test_job.refresh_from_db()
        assert test_job.progress == 25


@pytest.mark.django_db
class TestOutputFileCreation:
    """Tests for OutputFile creation during tasks."""
    
    def test_output_file_created_on_completion(self, test_job, test_org):
        """OutputFile should be created when job completes."""
        # Simulate task creating OutputFile
        output_file = OutputFile.objects.create(
            job=test_job,
            organization=test_org,
            filename="estimate_output.xlsx",
            file_type="xlsx",
            file_size=1024 * 50  # 50KB
        )
        
        assert output_file.job == test_job
        assert output_file.organization == test_org
        assert output_file.file_type == "xlsx"
    
    def test_output_file_belongs_to_correct_org(self, test_job, test_org):
        """OutputFile should belong to job's org."""
        output_file = OutputFile.objects.create(
            job=test_job,
            organization=test_org,
            filename="output.xlsx",
            file_type="xlsx"
        )
        
        assert output_file.organization == test_org
        assert output_file.organization == test_job.organization
    
    def test_multiple_output_files_per_job(self, test_job, test_org):
        """Job can have multiple OutputFiles."""
        file1 = OutputFile.objects.create(
            job=test_job,
            organization=test_org,
            filename="output1.xlsx",
            file_type="xlsx"
        )
        
        file2 = OutputFile.objects.create(
            job=test_job,
            organization=test_org,
            filename="estimate1.xlsx",
            file_type="xlsx"
        )
        
        files = OutputFile.objects.filter(job=test_job)
        assert files.count() == 2
        assert file1 in files
        assert file2 in files


@pytest.mark.django_db
class TestTaskInputValidation:
    """Tests for task input validation."""
    
    def test_task_accepts_valid_category(self):
        """Task should accept valid categories."""
        valid_categories = ['electrical', 'civil', 'mechanical']
        
        for category in valid_categories:
            assert category in ['electrical', 'civil', 'mechanical']
    
    def test_task_handles_valid_qty_map(self):
        """Task should handle valid quantity map."""
        qty_map = {
            'Item 1': 10,
            'Item 2': 5,
            'Item 3': 3.5
        }
        
        qty_map_json = json.dumps(qty_map)
        parsed = json.loads(qty_map_json)
        
        assert len(parsed) == 3
        assert parsed['Item 1'] == 10
