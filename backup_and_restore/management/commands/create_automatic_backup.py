from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from backup_and_restore.models import BackupSetting
from backup_and_restore.utils import upload_to_drive, upload_to_local


class Command(BaseCommand):
    help = 'Create automatic backup based on frequency.'

    def handle(self, *args, **options):
        today = timezone.localdate()

        backup_setting = BackupSetting.objects.first()
        if not backup_setting:
            self.stdout.write(self.style.WARNING(
                'No backup settings found. Please configure automatic backup settings.'
            ))
            return
        
        # Frequency (Daily, Weekly, Monthly)
        frequency = backup_setting.frequency

        # When was the last backup done?
        last_backup_date = (
            backup_setting.updated_at.date()
            if backup_setting.updated_at else None
        )

        # Determine if backup should run today
        should_backup = False

        if frequency == "Daily":
            should_backup = (last_backup_date != today)

        elif frequency == "Weekly":
            if not last_backup_date:
                should_backup = True
            else:
                should_backup = (today - last_backup_date) >= timedelta(weeks=1)

        elif frequency == "Monthly":
            if not last_backup_date:
                should_backup = True
            else:
                # Check if a new month has started since last backup
                should_backup = (
                    today.month != last_backup_date.month
                    or today.year != last_backup_date.year
                )

        else:
            self.stdout.write(self.style.WARNING(
                f"Invalid frequency '{frequency}'. Must be Daily, Weekly, or Monthly."
            ))
            return

        if not should_backup:
            self.stdout.write(self.style.WARNING(
                f"Backup skipped. Next backup based on '{frequency}' schedule."
            ))
            return

        # -----------------------------
        # 🚀 Perform the backup
        # -----------------------------
        storage_location = backup_setting.storage_location

        if storage_location.lower() == "cloud":
            success = upload_to_drive()
            message_ok = "Backup to Google Drive has been successful."
            message_fail = "Backup to Google Drive has failed."
        else:
            success = upload_to_local()
            message_ok = "Backup to Local Drive has been successful."
            message_fail = "Backup to Local Drive has failed."

        # Output success/failure
        if success:
            self.stdout.write(self.style.SUCCESS(message_ok))
        else:
            self.stdout.write(self.style.ERROR(message_fail))

        # Update last backup timestamp
        backup_setting.save(update_fields=["updated_at"])
