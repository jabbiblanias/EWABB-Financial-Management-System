from django.shortcuts import render, redirect
from .utils import upload_to_drive, restore_backup, upload_to_local, get_local_backups, get_cloud_backups
from django.contrib import messages
import os
from django.http import JsonResponse
import json
from django.core.paginator import Paginator
from django.template.loader import render_to_string


def backup_and_restore_view(request):
    is_ajax = request.headers.get("x-requested-with", "").lower() == "xmlhttprequest" \
            or request.META.get("HTTP_X_REQUESTED_WITH", "").lower() == "xmlhttprequest"

    context = backup_data(request, ajax=is_ajax)

    if is_ajax:
        return context
    
    return render(request, 'backup_and_restore/backup_and_restore.html', context)


def manual_backup(request):
    try:
        if request.method == "POST":
            storage = request.POST.get("backup_location")

            if storage == "cloud":
                if upload_to_drive():
                    message = "Backup to Google Drive has been successful"
                    context = backup_data(request, ajax=True, message=message)
                    return context
                else:
                    return JsonResponse({"status": "failed", "message": "Backup to Google Drive has failed"})
            else:
                if upload_to_local():
                    message = "Backup to Local Drive has been successful"
                    context = backup_data(request, ajax=True, message=message)
                    return context
                else:
                    return JsonResponse({"status": "failed", "message": "Backup to Local Drive has failed"})
    except Exception as e:
        return JsonResponse({"status": "error", "message": "Something went wrong."})


def restore_from_drive(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        file_name = data.get("name")
        location = data.get("location")

        if location == "cloud":
            success = restore_backup(source="cloud", drive_file_name=file_name)
        else:
            success = restore_backup(source="local", file_name=file_name)
        if success:
            return JsonResponse({"status": "success", "message": "Database restored successfully!"})
        else:
            return JsonResponse({"status": "failed", "message": "Restore failed."})
        
def backup_data(request, ajax=False, message=None):
    local = get_local_backups()
    cloud = get_cloud_backups()
    all_backups = local + cloud
    # Optional: Sort by creation date descending
    all_backups.sort(key=lambda x: x['created_at'], reverse=True)
    backups = all_backups

    paginator = Paginator(backups, 10)

    page_num = request.GET.get('page')

    page = paginator.get_page(page_num)
    context = {'backups': backups, 'page': page}

    if ajax:
        html = render_to_string("backup_and_restore/partials/backup_table_body.html", {"page": page})
        pagination = render_to_string("partials/pagination.html", {"page": page})
        return JsonResponse({"status": "success", "message": message, "table_body_html": html, "pagination_html": pagination})
    
    return context