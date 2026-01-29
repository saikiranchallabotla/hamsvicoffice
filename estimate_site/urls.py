import os
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect
from django.http import JsonResponse
from core import views, auth_views, api_views, dashboard_views, template_views, saved_works_views

# Health check endpoint for load balancers and container orchestration
def health_check(request):
    return JsonResponse({'status': 'healthy', 'app': 'hamsvic'})

urlpatterns = [
    path('health/', health_check, name='health_check'),
    path('admin/', admin.site.urls),
    
    # -------------------------
    # Custom Admin Panel (SaaS Management)
    # -------------------------
    path('admin-panel/', include('admin_panel.urls')),
    
    # -------------------------
    # New OTP-based Auth (accounts app)
    # -------------------------
    path('accounts/', include('accounts.urls')),
    
    # -------------------------
    # Subscriptions & Pricing
    # -------------------------
    path('subscriptions/', include('subscriptions.urls')),
    
    # -------------------------
    # Support & Help Center
    # -------------------------
    path('help/', include('support.urls')),
    
    # -------------------------
    # Datasets & SOR Rate Management
    # -------------------------
    path('datasets/', include('datasets.urls')),

    # -------------------------
    # Saved Works (Save & Resume Feature)
    # -------------------------
    path('saved-works/', saved_works_views.saved_works_list, name='saved_works_list'),
    path('saved-works/save/', saved_works_views.save_work, name='save_work'),
    path('saved-works/modal-data/', saved_works_views.get_save_work_modal_data, name='get_save_work_modal_data'),
    path('saved-works/folder/create/', saved_works_views.create_folder, name='create_folder'),
    path('saved-works/folder/<int:folder_id>/rename/', saved_works_views.rename_folder, name='rename_folder'),
    path('saved-works/folder/<int:folder_id>/delete/', saved_works_views.delete_folder, name='delete_folder'),
    path('saved-works/<int:work_id>/', saved_works_views.saved_work_detail, name='saved_work_detail'),
    path('saved-works/<int:work_id>/resume/', saved_works_views.resume_saved_work, name='resume_saved_work'),
    path('saved-works/<int:work_id>/update/', saved_works_views.update_saved_work, name='update_saved_work'),
    path('saved-works/<int:work_id>/delete/', saved_works_views.delete_saved_work, name='delete_saved_work'),
    path('saved-works/<int:work_id>/move/', saved_works_views.move_to_folder, name='move_to_folder'),
    path('saved-works/<int:work_id>/duplicate/', saved_works_views.duplicate_saved_work, name='duplicate_saved_work'),

    # -------------------------
    # Legacy Authentication (will be deprecated)
    # -------------------------
    path('register/', auth_views.register, name='register_legacy'),
    path('login/', auth_views.login_view, name='login_legacy'),
    path('logout/', auth_views.logout_view, name='logout_legacy'),
    path('dashboard/', dashboard_views.dashboard, name='dashboard'),
    path('dashboard/module/<str:module_code>/', dashboard_views.module_detail, name='module_detail'),
    path('dashboard/module/<str:module_code>/trial/', dashboard_views.start_trial, name='start_trial'),
    path('letter-settings/', views.letter_settings, name='letter_settings'),
    path('announcements/', dashboard_views.all_announcements, name='all_announcements'),
    path('api/announcements/', dashboard_views.api_announcements, name='api_announcements'),
    path('api/announcements/<uuid:announcement_id>/dismiss/', dashboard_views.api_dismiss_announcement, name='api_dismiss_announcement'),
    path('profile/', auth_views.profile_view, name='profile_legacy'),
    path('my-estimates/', auth_views.my_estimates, name='my_estimates'),
    path('estimates/<int:estimate_id>/', auth_views.view_estimate, name='view_estimate'),
    path('estimates/<int:estimate_id>/delete/', auth_views.delete_estimate, name='delete_estimate'),
    path('estimates/<int:estimate_id>/specification-report/', views.download_specification_report, name='download_specification_report'),
    path('save-estimate/', auth_views.save_estimate, name='save_estimate'),

    # -------------------------
    # User Document Templates (Covering Letter, Movement Slip)
    # -------------------------
    path('templates/', template_views.template_list_view, name='template_list'),
    path('templates/upload/', template_views.template_upload_view, name='template_upload'),
    path('templates/<int:template_id>/delete/', template_views.template_delete_view, name='template_delete'),
    path('templates/<int:template_id>/activate/', template_views.template_activate_view, name='template_activate'),
    path('templates/<int:template_id>/download/', template_views.template_download_view, name='template_download'),

    # -------------------------
    # Saved Works (Save & Resume)
    # -------------------------
    path('saved-works/', saved_works_views.saved_works_list, name='saved_works_list'),
    path('saved-works/save/', saved_works_views.save_work, name='save_work'),
    path('saved-works/save-with-parent/', saved_works_views.save_with_parent, name='save_with_parent'),
    path('saved-works/modal-data/', saved_works_views.get_save_work_modal_data, name='get_save_work_modal_data'),
    path('saved-works/<int:work_id>/', saved_works_views.saved_work_detail, name='saved_work_detail'),
    path('saved-works/<int:work_id>/resume/', saved_works_views.resume_saved_work, name='resume_saved_work'),
    path('saved-works/<int:work_id>/update/', saved_works_views.update_saved_work, name='update_saved_work'),
    path('saved-works/<int:work_id>/delete/', saved_works_views.delete_saved_work, name='delete_saved_work'),
    path('saved-works/<int:work_id>/move/', saved_works_views.move_to_folder, name='move_to_folder'),
    path('saved-works/<int:work_id>/duplicate/', saved_works_views.duplicate_saved_work, name='duplicate_saved_work'),
    path('saved-works/<int:work_id>/generate-workslip/', saved_works_views.generate_workslip_from_saved, name='generate_workslip_from_saved'),
    path('saved-works/<int:work_id>/generate-next-workslip/', saved_works_views.generate_next_workslip_from_saved, name='generate_next_workslip_from_saved'),
    path('saved-works/<int:work_id>/generate-bill/', saved_works_views.generate_bill_from_saved, name='generate_bill_from_saved'),
    path('folders/create/', saved_works_views.create_folder, name='create_folder'),
    path('folders/<int:folder_id>/rename/', saved_works_views.rename_folder, name='rename_folder'),
    path('folders/<int:folder_id>/delete/', saved_works_views.delete_folder, name='delete_folder'),

    # -------------------------
    # Main pages - Redirect home to dashboard
    # -------------------------
    path('', lambda request: redirect('dashboard'), name='home'),
    path('estimate/', views.estimate, name='estimate'),
    path('estimate/specification-report/', views.generate_specification_report_from_file, name='generate_specification_report'),
    path('estimate/forwarding-letter/', views.generate_estimate_forwarding_letter, name='generate_forwarding_letter'),
    path('workslip/', views.workslip_home, name='workslip'),  # Landing page for work type selection
    path('workslip/main/', views.workslip, name='workslip_main'),  # Main workslip 3-panel interface
    path('workslip/ajax-toggle-supp/', views.workslip_ajax_toggle_supp, name='workslip_ajax_toggle_supp'),
    path('bill/', views.bill, name='bill'),

    # -------------------------
    # Subscription / Projects
    # -------------------------
    path('my-subscription/', views.my_subscription, name='my_subscription'),
    path('my-projects/', views.my_projects, name='my_projects'),
    path('create-project/', views.create_project, name='create_project'),

    path('projects/<int:project_id>/load/', views.load_project, name='load_project'),
    path('projects/<int:project_id>/delete/', views.delete_project, name='delete_project'),
    path('new-project/', views.new_project, name='new_project'),

    # -------------------------
    # Datas / New Estimate Navigation
    # -------------------------
    # IMPORTANT: Keep name="datas" so home.html & other pages work correctly
    path('datas/', views.datas, name='datas'),

    path('datas/<str:category>/groups/', views.datas_groups, name='datas_groups'),
    path('datas/<str:category>/group/<str:group>/', views.datas_items, name='datas_items'),

    path(
        'datas/<str:category>/group/<str:group>/<path:item>/fetch/',
        views.fetch_item,
        name='fetch_item',
    ),

    path('datas/<str:category>/save/', views.save_project, name='save_project'),
    path('datas/<str:category>/output/', views.output_panel, name='output_panel'),
    path('datas/<str:category>/download/', views.download_output, name='download_output'),
    path('datas/<str:category>/clear/', views.clear_output, name='clear_output'),
    path('datas/<str:category>/save_qty_map/', views.save_qty_map, name='save_qty_map'),
    path('datas/<str:category>/specification-report/', views.download_specification_report_live, name='download_specification_report_live'),
    path('datas/<str:category>/forwarding-letter/', views.download_forwarding_letter_live, name='download_forwarding_letter_live'),
    
    # AJAX endpoints for New Estimate module (queued item selection & drag-drop reorder)
    path('datas/<str:category>/ajax_toggle_item/', views.ajax_toggle_item, name='ajax_toggle_item'),
    path('datas/<str:category>/ajax_reorder_items/', views.ajax_reorder_items, name='ajax_reorder_items'),

    # -------------------------
    # Bill document routes
    # -------------------------
    path("bill/document/", views.bill_document, name="bill_document"),

    # -------------------------
    # Self-formatted forms
    # -------------------------
    path('self-formatted/', views.self_formatted_form_page, name='self_formatted_form_page'),
    path('self-formatted/generate/', views.self_formatted_generate, name='self_formatted_generate'),
    path('self-formatted/preview/', views.self_formatted_preview, name='self_formatted_preview'),
    path('self-formatted/save-format/', views.self_formatted_save_format, name='self_formatted_save_format'),
    path('self-formatted/use/<int:pk>/', views.self_formatted_use_format, name='self_formatted_use_format'),
    path('self-formatted/edit/<int:pk>/', views.self_formatted_edit_format, name='self_formatted_edit_format'),
    path("self-formatted/delete/<int:pk>/", views.self_formatted_delete_format, name="self_formatted_delete_format"),

    # =========================
    # TEMPORARY WORKS (separate module)
    # =========================
    path("tempworks/", views.tempworks_home, name="tempworks_home"),

    path("tempdatas/<str:category>/groups/", views.temp_groups, name="temp_groups"),

    path(
        "tempdatas/<str:category>/group/<str:group>/",
        views.temp_items,
        name="temp_items",
    ),

    path(
        "tempdatas/<str:category>/group/<str:group>/add/<path:item>/",
        views.temp_add_item,
        name="temp_add_item",
    ),

    path(
        "tempdatas/<str:category>/group/<str:group>/remove/<str:entry_id>/",
        views.temp_remove_item,
        name="temp_remove_item",
    ),

    path(
        "tempdatas/<str:category>/download/",
        views.temp_download_output,
        name="temp_download_output",
    ),
    path(
        "tempdatas/<str:category>/specification-report/",
        views.temp_download_specification_report,
        name="temp_download_specification_report",
    ),
    path(
        "tempdatas/<str:category>/forwarding-letter/",
        views.temp_download_forwarding_letter,
        name="temp_download_forwarding_letter",
    ),
    path(
        "tempdatas/<str:category>/day_rates/",
        views.temp_day_rates_debug,
        name="temp_day_rates_debug",
    ),
    path(
        "tempdatas/<str:category>/save_state/",
        views.temp_save_state,
        name="temp_save_state",
    ),
    
    # AJAX endpoints for Temporary Works module (queued item add & drag-drop reorder)
    path(
        "tempdatas/<str:category>/ajax_add_item/",
        views.temp_ajax_add_item,
        name="temp_ajax_add_item",
    ),
    path(
        "tempdatas/<str:category>/ajax_reorder_items/",
        views.temp_ajax_reorder_items,
        name="temp_ajax_reorder_items",
    ),
    path(
        "tempdatas/<str:category>/group/<str:group>/clear/",
        views.temp_clear_items,
        name="temp_clear_items",
    ),
    path(
        "tempdatas/<str:category>/ajax_remove_item/",
        views.temp_ajax_remove_item,
        name="temp_ajax_remove_item",
    ),

    # =========================
    # AMC MODULE (Annual Maintenance Contract)
    # =========================
    path("amc/", views.amc_home, name="amc_home"),
    
    path("amc/<str:category>/groups/", views.amc_groups, name="amc_groups"),
    
    path(
        "amc/<str:category>/group/<str:group>/",
        views.amc_items,
        name="amc_items",
    ),
    
    path(
        "amc/<str:category>/group/<str:group>/<path:item>/fetch/",
        views.amc_fetch_item,
        name="amc_fetch_item",
    ),
    
    path(
        "amc/<str:category>/clear/",
        views.amc_clear_output,
        name="amc_clear_output",
    ),
    
    path(
        "amc/<str:category>/save_qty_map/",
        views.amc_save_qty_map,
        name="amc_save_qty_map",
    ),
    
    path(
        "amc/<str:category>/download/",
        views.amc_download_output,
        name="amc_download_output",
    ),
    path(
        "amc/<str:category>/specification-report/",
        views.amc_download_specification_report,
        name="amc_download_specification_report",
    ),
    path(
        "amc/<str:category>/forwarding-letter/",
        views.amc_download_forwarding_letter,
        name="amc_download_forwarding_letter",
    ),
    
    # AJAX endpoints for AMC module (queued item selection & drag-drop reorder)
    path(
        "amc/<str:category>/ajax_toggle_item/",
        views.amc_ajax_toggle_item,
        name="amc_ajax_toggle_item",
    ),
    path(
        "amc/<str:category>/ajax_reorder_items/",
        views.amc_ajax_reorder_items,
        name="amc_ajax_reorder_items",
    ),

    # ========================
    # API Routes (Job & Upload Management)
    # ========================
    path('api/jobs/<int:job_id>/status/', api_views.job_status, name='job_status'),
    path('api/uploads/<int:upload_id>/status/', api_views.upload_status, name='upload_status'),
    path('api/outputs/<int:file_id>/download/', api_views.download_output_file, name='download_output_file'),
    path('api/outputs/', api_views.list_outputs, name='list_outputs'),
    path('api/jobs/create/', api_views.create_job, name='create_job'),
]

# -------------------------
# MEDIA (for uploaded backend excels, templates etc.)
# -------------------------
# Always serve media files for Railway deployment (local storage mode)
# In production with S3, files are served directly from S3
if settings.DEBUG or os.environ.get('STORAGE_TYPE', 'local') == 'local':
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
