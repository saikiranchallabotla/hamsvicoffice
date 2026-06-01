from django.urls import path

from core.views import dwg_views

urlpatterns = [
    path("", dwg_views.upload_view, name="dwg_upload"),
    path("<int:pk>/review/", dwg_views.review_view, name="dwg_review"),
    path("<int:pk>/result/", dwg_views.result_view, name="dwg_result"),
    path("<int:pk>/download/", dwg_views.download_view, name="dwg_download"),
    path("<int:pk>/status/", dwg_views.status_view, name="dwg_status"),
    path("<int:pk>/delete/", dwg_views.delete_view, name="dwg_delete"),
]
