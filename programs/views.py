from django.shortcuts import render
from django.http import JsonResponse
from .models import BusinessProgram
from django.core.paginator import Paginator
from django.template.loader import render_to_string


from django.shortcuts import render
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.db.models import Q
from urllib.parse import urlencode

# Assuming BusinessProgram model is imported or defined elsewhere

def program_view(request):
    # --- 1. Get request parameters ---
    search_term = request.GET.get('account', '').strip()
    sort_by = request.GET.get('sort_by', '').strip()
    order = request.GET.get('order', '').strip()
    page_num = request.GET.get('page')
    
    # NEW: Get the status filter value
    status_filter = request.GET.get('status', '').strip()
    
    # --- 2. Build Queryset (Filtering) ---
    programs_qs = BusinessProgram.objects.all()
    
    # Apply combined search/filter logic
    q_filters = Q()
    
    # Apply search term filter (Program Name or Status)
    if search_term:
        q_filters &= (
            Q(program_name__icontains=search_term) |
            Q(status__icontains=search_term)
        )
        
    # Apply status dropdown filter (Exact match)
    if status_filter:
        q_filters &= Q(status=status_filter)
        
    if q_filters:
        programs_qs = programs_qs.filter(q_filters)


    # --- 3. Apply Sorting (Unchanged) ---
    sort_fields = {
        'id': 'program_id',
        'program_name': 'program_name',
        'date_started': 'date_started',
        'date_end': 'date_end',
        'status': 'status',
        'total_profits': 'total_profits',
    }
    
    ordering = []
    
    if sort_by in sort_fields:
        db_field = sort_fields[sort_by]
        prefix = '-' if order == 'desc' else ''
        ordering.append(prefix + db_field)
    
    if not ordering:
        ordering.append('-program_id')

    programs_qs = programs_qs.order_by(*ordering)


    # --- 4. Pagination (Unchanged) ---
    paginator = Paginator(programs_qs, 10)
    page = paginator.get_page(page_num)

    get_params = request.GET.copy()
    if 'page' in get_params:
        del get_params['page']
        
    current_query_params = '&' + urlencode(get_params) if get_params else ''

    context = {
        'programs': programs_qs,
        'page': page,
        'current_query_params': current_query_params,
        'current_search': search_term, 
        'current_sort_by': sort_by,
        'current_order': order,
        # NEW: Pass current status filter value back to the template
        'current_status_filter': status_filter, 
    }

    # --- 5. AJAX / Standard Response (Unchanged) ---
    is_ajax = request.headers.get("x-requested-with", "").lower() == "xmlhttprequest" \
              or request.META.get("HTTP_X_REQUESTED_WITH", "").lower() == "xmlhttprequest"

    if is_ajax:
        html = render_to_string("programs/partials/programs_table_body.html", context, request=request)
        pagination = render_to_string("partials/pagination.html", context, request=request)
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
