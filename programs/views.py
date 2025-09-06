from django.shortcuts import render


def program_view(request):
    return render(request, 'programs/bookkeeper_program.html')
