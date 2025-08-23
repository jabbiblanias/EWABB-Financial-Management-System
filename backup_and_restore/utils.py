from django.shortcuts import render
import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.http import MediaIoBaseDownload
import io

# OAuth scope for Google Drive access (file-level)
SCOPES = ['https://www.googleapis.com/auth/drive.file']


#Uploading file to the folder
def upload_to_drive(file_path, folder_id=None, new_filename=None):
    creds = None

    # Use existing token or authenticate
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    else:
        flow = InstalledAppFlow.from_client_secrets_file('client_secret_940826947132-4la3308io2fe3nv3p7v6u9ok4hg66bdk.apps.googleusercontent.com.json', SCOPES)
        creds = flow.run_local_server(port=0)
        # Save the credentials for future use
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    # Build Drive API service
    service = build('drive', 'v3', credentials=creds)

    # Rename file if a new name is provided
    file_metadata = {'name': new_filename or os.path.basename(file_path)}
    if folder_id:
        file_metadata['parents'] = [folder_id]

    media = MediaFileUpload(file_path, resumable=True)

    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id'
    ).execute()

    print(f"File uploaded successfully. File ID: {file.get('id')}")

# Replace with your file path
upload_to_drive("C:\\Users\\John April\\Documents\\tp.drawio", 
                folder_id='1vN8AeR7faQh2DY8iH7mVEme2vOwVPn8R', new_filename='tp.drawio')

#Listing file in the folder
def list_files_in_folder(folder_id):
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    else:
        flow = InstalledAppFlow.from_client_secrets_file('client_secret_940826947132-4la3308io2fe3nv3p7v6u9ok4hg66bdk.apps.googleusercontent.com.json', SCOPES)
        creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    service = build('drive', 'v3', credentials=creds)

    # Query files in the given folder
    query = f"'{folder_id}' in parents and trashed = false"
    results = service.files().list(
        q=query,
        fields="files(id, name, mimeType, modifiedTime, size)"
    ).execute()

    files = results.get('files', [])
    if not files:
        print("No files found in folder.")
    else:
        print(f"Files in folder {folder_id}:")
        for file in files:
            print(f"- {file['name']} (ID: {file['id']})")

# Example usage
list_files_in_folder("1vN8AeR7faQh2DY8iH7mVEme2vOwVPn8R")  # Replace with your real folder ID


#Dowloading file
def download_file(file_id, destination_path):
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    else:
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    service = build('drive', 'v3', credentials=creds)

    # Request file from Drive
    request = service.files().get_media(fileId=file_id)
    fh = io.FileIO(destination_path, 'wb')  # Write bytes to file

    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()
        print(f"Download progress: {int(status.progress() * 100)}%")

    print(f"File downloaded to: {destination_path}")

# 🔧 Example usage
download_file(
    file_id="17AWYGjKMz6YyggfF5AzelLKiPVlROPNl",  # Replace with your file's real ID
    destination_path="C:\\Users\\John April\\Downloads\\downloaded_file.pdf"
)