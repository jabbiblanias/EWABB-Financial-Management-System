from django.shortcuts import render
from django.http import JsonResponse
from .models import BusinessProgram


def program_view(request):
    programs = BusinessProgram.objects.all()
    context = {"programs": programs}
    return render(request, 'programs/bookkeeper_program.html', context)

def create_program(request):
    if request.method == "POST":
        name = request.POST.get("program")
        date_start = request.POST.get("date_start")
        date_end = request.POST.get("date_end")

        program = (
            BusinessProgram.objects.create(
            program_name=name,
            date_started=date_start,
            date_end=date_end
            )
        )

        return JsonResponse({"success": True, "message": f"{program.program_name} has been created."})
    
def check_exist(request):
    if request.method == "GET":
        name = request.GET.get("program")
        exists = BusinessProgram.objects.filter(program_name=name).exists()
        return JsonResponse({"exists": exists})
