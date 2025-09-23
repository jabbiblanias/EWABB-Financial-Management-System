from django.shortcuts import render, redirect
from .utils import upload_to_drive, restore_backup, upload_to_local, get_local_backups, get_cloud_backups
from django.contrib import messages
import os
from django.http import JsonResponse
import json


def backup_and_restore_view(request):
    local = get_local_backups()
    cloud = get_cloud_backups()
    all_backups = local + cloud
    # Optional: Sort by creation date descending
    all_backups.sort(key=lambda x: x['created_at'], reverse=True)
    backups = all_backups
    return render(request, 'backup_and_restore/backup_and_restore.html', {"backups": backups})


def manual_backup(request):
    try:
        if request.method == "POST":
            storage = request.POST.get("backup_location")
            if storage == "cloud":
                if upload_to_drive():
                    return JsonResponse({"status": "success", "message": "Backup uploaded to Google Drive"})
                else:
                    return JsonResponse({"status": "failed", "message": "Backup to Google Drive has failed"})
            else:
                if upload_to_local():
                    return JsonResponse({"status": "success", "message": "Backup uploaded to Local Drive"})
                else:
                    return JsonResponse({"status": "failed", "message": "Backup to Local Drive has failed"})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)})


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