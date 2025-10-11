import os
from django.conf import settings
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.http import MediaIoBaseDownload
from google.auth.transport.requests import Request
import io
from datetime import datetime, timezone
import subprocess
from pathlib import Path
from dateutil import parser


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
def upload_to_drive():
    # --- Temp backup file (created same way as upload_to_local) ---
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"backup_{timestamp}.sql"

    # --- Build pg_dump command ---
    dump_cmd = [
        settings.PG_DUMP_PATH,  # same as in upload_to_local
        "-h", settings.DB_HOST,
        "-p", str(settings.DB_PORT),
        "-U", settings.DB_USER,
        "-F", "p",
        "-b",
        "-v",
        "-f", backup_file,
        settings.DB_NAME,
    ]

    # --- Run with PGPASSWORD in env ---
    env = os.environ.copy()
    env["PGPASSWORD"] = settings.DB_PASSWORD

    result = subprocess.run(dump_cmd, env=env, capture_output=True, text=True)

    if result.returncode != 0:
        print("Backup failed")
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
        return False

    # --- Upload to Google Drive ---
    service = get_drive_service()
    file_metadata = {
        "name": backup_file,
        "parents": [settings.GOOGLE_DRIVE_FOLDER_ID],
    }
    media = MediaFileUpload(backup_file, resumable=False)

    uploaded_file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id",
    ).execute()

    # --- Cleanup ---
    media._fd.close()
    os.remove(backup_file)

    print(f"Backup uploaded successfully to Google Drive: {uploaded_file.get('id')}")
    return True


# 🔹 Upload backup file
def upload_to_local():
    backup_dir = settings.LOCAL_BACKUP_DIR
    os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(backup_dir, f"backup_{timestamp}.sql")

    # Build command
    dump_cmd = [
        settings.PG_DUMP_PATH,
        "-h", settings.DB_HOST,
        "-p", str(settings.DB_PORT),
        "-U", settings.DB_USER,
        "-F", "p",
        "-b",
        "-v",
        "-f", backup_file,
        settings.DB_NAME
    ]

    # Run with PGPASSWORD in env
    env = os.environ.copy()
    env["PGPASSWORD"] = settings.DB_PASSWORD

    result = subprocess.run(dump_cmd, env=env, capture_output=True, text=True)

    if result.returncode == 0:
        print(f"Backup successful: {backup_file}")
        return True
    else:
        print("Backup failed")
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
        return False


# 🔹 Download file locally
'''def download_from_drive(file_id, destination_path):
    service = get_drive_service()
    request = service.files().get_media(fileId=file_id)

    with io.FileIO(destination_path, 'wb') as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            print(f"Download {int(status.progress() * 100)}%.")

    return destination_path'''

# 🔹 Restore directly into PostgreSQL
def restore_from_drive(file_name):
    service = get_drive_service()

    # --- Step 1: Search file by name ---
    results = service.files().list(
        q=f"name='{file_name}' and trashed=false",
        spaces='drive',
        fields="files(id, name)"
    ).execute()
    files = results.get('files', [])

    if not files:
        print(f"No file found with name '{file_name}'")
        return False

    # Use the first matching file
    file_id = files[0]['id']
    request = service.files().get_media(fileId=file_id)

    temp_file = "temp_restore.sql"
    fh = io.FileIO(temp_file, "wb")
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    fh.close()

    env = os.environ.copy()
    env["PGPASSWORD"] = settings.DB_PASSWORD

    TARGET_DB = settings.DB_NAME
    TEMP_DB = f"{TARGET_DB}_temp"

    # --- Step 1: Create temporary DB ---
    subprocess.run([
        settings.PSQL_PATH, "-h", settings.DB_HOST, "-p", str(settings.DB_PORT),
        "-U", settings.DB_USER, "-d", "postgres",
        "-c", f"CREATE DATABASE {TEMP_DB};"
    ], env=env, capture_output=True, text=True)

    # --- Step 2: Restore backup into TEMP_DB ---
    restore_cmd = [
        settings.PSQL_PATH, "-h", settings.DB_HOST, "-p", str(settings.DB_PORT),
        "-U", settings.DB_USER, "-d", TEMP_DB, "-f", temp_file
    ]
    result = subprocess.run(restore_cmd, env=env, capture_output=True, text=True)

    if result.returncode != 0:
        print("Restore to temp DB failed!")
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
        # Cleanup temp DB
        subprocess.run([
            settings.PSQL_PATH, "-h", settings.DB_HOST, "-p", str(settings.DB_PORT),
            "-U", settings.DB_USER, "-d", "postgres",
            "-c", f"DROP DATABASE IF EXISTS {TEMP_DB};"
        ], env=env)
        os.remove(temp_file)
        return False

    # --- Step 3: Terminate connections to original DB ---
    subprocess.run([
        settings.PSQL_PATH, "-h", settings.DB_HOST, "-p", str(settings.DB_PORT),
        "-U", settings.DB_USER, "-d", "postgres",
        "-c", f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='{TARGET_DB}';"
    ], env=env)

    # --- Step 4: Drop original DB ---
    subprocess.run([
        settings.PSQL_PATH, "-h", settings.DB_HOST, "-p", str(settings.DB_PORT),
        "-U", settings.DB_USER, "-d", "postgres",
        "-c", f"DROP DATABASE IF EXISTS {TARGET_DB};"
    ], env=env)

    # --- Step 5: Rename temp DB to target DB ---
    subprocess.run([
        settings.PSQL_PATH, "-h", settings.DB_HOST, "-p", str(settings.DB_PORT),
        "-U", settings.DB_USER, "-d", "postgres",
        "-c", f"ALTER DATABASE {TEMP_DB} RENAME TO {TARGET_DB};"
    ], env=env)

    os.remove(temp_file)
    print("Restore successful")
    return True

def restore_from_local(backup_file):
    """
    Restore a PostgreSQL database from a local .sql file.
    :param backup_file: Path to the SQL backup file
    :return: True if successful, False otherwise
    """

    if not os.path.exists(backup_file):
        print(f"Backup file not found: {backup_file}")
        return False

    # --- Environment with password ---
    env = os.environ.copy()
    env["PGPASSWORD"] = settings.DB_PASSWORD

    # --- psql command ---
    psql_exe = getattr(settings, "PSQL_PATH", "psql")
    restore_cmd = [
        psql_exe,
        "-h", settings.DB_HOST,
        "-p", str(settings.DB_PORT),
        "-U", settings.DB_USER,
        "-d", settings.DB_NAME,
        "-f", backup_file
    ]

    try:
        subprocess.run(restore_cmd, check=True, env=env)
        print(f"Database restored successfully from {backup_file}")
        return True
    except FileNotFoundError:
        print("Error: psql not found. Check PSQL_PATH or install PostgreSQL client.")
        return False
    except subprocess.CalledProcessError as e:
        print(f"Error during restore: exit code {e.returncode}")
        return False


def restore_backup(source="local", file_name=None, drive_file_name=None):
    # --- Step 1: Prepare backup file ---
    if source == "local":
        backup_dir = Path(settings.LOCAL_BACKUP_DIR)
        if not backup_dir.exists():
            print(f"❌ Backup directory not found: {backup_dir}")
            return False

        if file_name:
            backup_path = backup_dir / file_name
        else:
            # Auto-pick the latest file
            sql_files = sorted(
                backup_dir.glob("*.sql"),
                key=lambda f: f.stat().st_mtime,
                reverse=True
            )
            if not sql_files:
                print("❌ No .sql backup files found in local backup directory")
                return False
            backup_path = sql_files[0]
            print(f"ℹ️ Using latest local backup: {backup_path.name}")

        if not backup_path.exists():
            print(f"❌ Local backup not found: {backup_path}")
            return False

        temp_file = str(backup_path)

    elif source == "cloud":
        if not drive_file_name:
            print("❌ Drive restore requires drive_file_name")
            return False

        service = get_drive_service()
        results = service.files().list(
            q=f"name='{drive_file_name}' and trashed=false",
            spaces="drive",
            fields="files(id, name)"
        ).execute()
        files = results.get("files", [])

        if not files:
            print(f"❌ No file found with name '{drive_file_name}' on Drive")
            return False

        file_id = files[0]["id"]
        request = service.files().get_media(fileId=file_id)

        temp_file = "temp_restore.sql"
        fh = io.FileIO(temp_file, "wb")
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        fh.close()

    else:
        print("❌ Invalid source. Use 'local' or 'drive'.")
        return False
    
    env = os.environ.copy()
    env["PGPASSWORD"] = settings.DB_PASSWORD

    TARGET_DB = settings.DB_NAME
    TEMP_DB = f"{TARGET_DB}_temp"

    # --- Step 2: Create temporary DB ---
    subprocess.run([
        settings.PSQL_PATH, "-h", settings.DB_HOST, "-p", str(settings.DB_PORT),
        "-U", settings.DB_USER, "-d", "postgres",
        "-c", f"CREATE DATABASE {TEMP_DB};"
    ], env=env, capture_output=True, text=True)

    # --- Step 3: Restore into TEMP_DB ---
    restore_cmd = [
        settings.PSQL_PATH, "-h", settings.DB_HOST, "-p", str(settings.DB_PORT),
        "-U", settings.DB_USER, "-d", TEMP_DB, "-f", temp_file
    ]
    result = subprocess.run(restore_cmd, env=env, capture_output=True, text=True)

    if result.returncode != 0:
        print("Restore to temp DB failed!")
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
        subprocess.run([
            settings.PSQL_PATH, "-h", settings.DB_HOST, "-p", str(settings.DB_PORT),
            "-U", settings.DB_USER, "-d", "postgres",
            "-c", f"DROP DATABASE IF EXISTS {TEMP_DB};"
        ], env=env)
        if source == "cloud" and os.path.exists(temp_file):
            os.remove(temp_file)
        return False

    # --- Step 4: Terminate connections to original DB ---
    subprocess.run([
        settings.PSQL_PATH, "-h", settings.DB_HOST, "-p", str(settings.DB_PORT),
        "-U", settings.DB_USER, "-d", "postgres",
        "-c", f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='{TARGET_DB}';"
    ], env=env)

    # --- Step 5: Drop original DB ---
    subprocess.run([
        settings.PSQL_PATH, "-h", settings.DB_HOST, "-p", str(settings.DB_PORT),
        "-U", settings.DB_USER, "-d", "postgres",
        "-c", f"DROP DATABASE IF EXISTS {TARGET_DB};"
    ], env=env)

    # --- Step 6: Rename temp DB to target DB ---
    subprocess.run([
        settings.PSQL_PATH, "-h", settings.DB_HOST, "-p", str(settings.DB_PORT),
        "-U", settings.DB_USER, "-d", "postgres",
        "-c", f"ALTER DATABASE {TEMP_DB} RENAME TO {TARGET_DB};"
    ], env=env)

    if source == "cloud" and os.path.exists(temp_file):
        os.remove(temp_file)

    print("✅ Restore successful")
    return True

# 🔹 List files in Drive folder
def list_backups():
    service = get_drive_service()
    query = f"'{settings.GOOGLE_DRIVE_FOLDER_ID}' in parents and trashed=false"

    results = service.files().list(
        q=query,
        fields="files(id, name, modifiedTime, size)"
    ).execute()

    return results.get('files', [])


def get_local_backups():
    backup_dir = Path(settings.LOCAL_BACKUP_DIR)
    backups = []
    if backup_dir.exists():
        for file in backup_dir.glob("*.sql"):
            backups.append({
                "name": file.name,
                "location": "local",
                "size": format_size(round(file.stat().st_size / 1024, 2)),
                # Make UTC-aware
                "created_at": datetime.fromtimestamp(file.stat().st_ctime, tz=timezone.utc)
            })
    return backups

def get_cloud_backups():
    service = get_drive_service()
    query = f"'{settings.GOOGLE_DRIVE_FOLDER_ID}' in parents and trashed=false"
    results = service.files().list(
        q=query,
        fields="files(name, createdTime, size)"
    ).execute()
    items = results.get("files", [])
    
    backups = []
    for item in items:
        # Convert string to UTC-aware datetime
        created_at = parser.isoparse(item['createdTime'])
        backups.append({
            "name": item['name'],
            "location": "cloud",
            "size": format_size(round(int(item.get('size', 0)) / 1024, 2)),
            "created_at": created_at
        })
    return backups


def cleanup_old_backups():
    service = get_drive_service()
    results = service.files().list(
        q=f"'{settings.GOOGLE_DRIVE_TOKEN_FILE}' in parents",
        orderBy="createdTime desc",
        fields="files(id, name, createdTime)"
    ).execute()
    files = results.get('files', [])

    if len(files) > KEEP_BACKUPS:
        for old_file in files[KEEP_BACKUPS:]:
            service.files().delete(fileId=old_file['id']).execute()
            print(f"🗑️ Deleted old backup: {old_file['name']}")


def format_size(size_kb):
    """Convert KB to KB, MB, GB string."""
    if size_kb >= 1024*1024:
        return f"{size_kb / (1024*1024):.2f} GB"
    elif size_kb >= 1024:
        return f"{size_kb / 1024:.2f} MB"
    else:
        return f"{size_kb:.2f} KB"