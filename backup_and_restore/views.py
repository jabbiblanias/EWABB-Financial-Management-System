from django.shortcuts import render, redirect


def backup_and_restore_view(request):
    return render(request, 'backup_and_restore/backup_and_restore.html')