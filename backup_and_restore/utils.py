from django.shortcuts import render
import os
from django.conf import settings
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.http import MediaIoBaseDownload
from google.auth.transport.requests import Request
import io


SCOPES = ['https://www.googleapis.com/auth/drive.file']


def get_drive_service():
    creds = None
    token_path = settings.GOOGLE_DRIVE_TOKEN_FILE

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                settings.GOOGLE_DRIVE_CREDENTIALS_FILE, SCOPES
            )
            creds = flow.run_local_server(port=0)

        # Save refreshed credentials
        with open(token_path, 'w') as token:
            token.write(creds.to_json())

    return build('drive', 'v3', credentials=creds)


# 🔹 Upload backup file
def upload_to_drive(new_filename=None):
    backup_file = "backup.sql"

    dump_cmd = (
        f'PGPASSWORD={settings.DB_PASSWORD} '
        f'pg_dump -h {settings.DB_HOST} -p {settings.DB_PORT} '
        f'-U {settings.DB_USER} {settings.DB_NAME} > {backup_file}'
    )
    os.system(dump_cmd)

    service = get_drive_service()

    file_metadata = {
        'name': new_filename,
        'parents': [settings.GOOGLE_DRIVE_FOLDER_ID]
    }
    media = MediaFileUpload(backup_file, resumable=True)

    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id'
    ).execute()

    return file.get('id')


def create_backup():
    backup_file = "backup.sql"

    dump_cmd = (
        f'PGPASSWORD={settings.DB_PASSWORD} '
        f'pg_dump -h {settings.DB_HOST} -p {settings.DB_PORT} '
        f'-U {settings.DB_USER} {settings.DB_NAME} > {backup_file}'
    )
    os.system(dump_cmd)

    service = get_drive_service()
    file_metadata = {
        'name': "Postgres_Backup.sql",
        'parents': [settings.GOOGLE_DRIVE_FOLDER_ID],
    }
    media = MediaFileUpload(backup_file, resumable=True)

    uploaded = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id'
    ).execute()

    os.remove(backup_file)
    return uploaded.get("id")



# 🔹 List files in Drive folder
def list_backups():
    service = get_drive_service()
    query = f"'{settings.GOOGLE_DRIVE_FOLDER_ID}' in parents and trashed=false"

    results = service.files().list(
        q=query,
        fields="files(id, name, mimeType, modifiedTime, size)"
    ).execute()

    return results.get('files', [])


# 🔹 Download file locally
def download_from_drive(file_id, destination_path):
    service = get_drive_service()
    request = service.files().get_media(fileId=file_id)

    with io.FileIO(destination_path, 'wb') as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            print(f"Download {int(status.progress() * 100)}%.")

    return destination_path


# 🔹 Restore directly into PostgreSQL
def restore_backup(file_id):
    service = get_drive_service()
    request = service.files().get_media(fileId=file_id)

    temp_file = "temp_restore.sql"
    with open(temp_file, "wb") as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()

    restore_cmd = (
        f'PGPASSWORD={settings.DB_PASSWORD} '
        f'psql -h {settings.DB_HOST} -p {settings.DB_PORT} '
        f'-U {settings.DB_USER} -d {settings.DB_NAME} -f {temp_file}'
    )

    result = os.system(restore_cmd)
    os.remove(temp_file)
    return result == 0