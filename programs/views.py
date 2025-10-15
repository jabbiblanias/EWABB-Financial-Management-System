from django.shortcuts import render
from django.http import JsonResponse
from .models import BusinessProgram
from django.core.paginator import Paginator
from django.template.loader import render_to_string


def program_view(request):
    programs = BusinessProgram.objects.all()

    paginator = Paginator(programs, 10)

    page_num = request.GET.get('page')

    page = paginator.get_page(page_num)
    context = {'programs': programs, 'page': page}

    is_ajax = request.headers.get("x-requested-with", "").lower() == "xmlhttprequest" \
            or request.META.get("HTTP_X_REQUESTED_WITH", "").lower() == "xmlhttprequest"

    if is_ajax:
        html = render_to_string("programs/partials/programs_table_body.html", {"page": page})
        pagination = render_to_string("partials/pagination.html", {"page": page})
        return JsonResponse({"table_body_html": html, "pagination_html": pagination})
    
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
