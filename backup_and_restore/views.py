from django.shortcuts import render, redirect
from .utils import upload_to_drive, restore_backup, list_backups
from django.contrib import messages
import os


def backup_and_restore_view(request):
    return render(request, 'backup_and_restore/backup_and_restore.html')


def backup_page(request):
    if request.method == "POST" and "backup" in request.POST:
        # Example: run pg_dump before uploading
        os.system('PGPASSWORD=yourpassword pg_dump -U youruser -h localhost -p 5432 yourdb > backup.sql')
        file_id = upload_to_drive("backup.sql", "Postgres_Backup.sql")
        messages.success(request, f"Backup uploaded to Google Drive (ID: {file_id})")
        return redirect("backup_page")

    backups = list_backups()
    return render(request, "admin/backup_page.html", {"backups": backups})


def restore_from_drive(request, file_id):
    success = restore_backup(
        file_id,
        db_name=os.getenv('POSTGRES_DB'),
        db_user=os.getenv('POSTGRES_USER'),
        db_password=os.getenv('POSTGRES_PASSWORD')
    )
    if success:
        messages.success(request, "✅ Database restored successfully from Google Drive!")
    else:
        messages.error(request, "❌ Restore failed.")
    return redirect("backup_page")