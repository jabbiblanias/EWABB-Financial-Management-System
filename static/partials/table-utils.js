let currentPage = 1;
const currentUrlPath = window.location.pathname; // Base URL path

// --- Utility function for padding rows ---
function fillTableRows(tableId, requiredRows) {
    const table = document.getElementById(tableId);
    if (!table) return;

    const tbody = table.querySelector('tbody');
    if (!tbody) return;
    
    // Remove existing padding rows if necessary (optional, but clean)
    // To keep it simple, we just clear and refill every time.
    
    // Count current rows *after* the content has been updated by AJAX
    const currentRows = tbody.querySelectorAll('tr').length; 

    // Detect column count
    let columnsCount = 0;
    const firstDataRow = tbody.querySelector('tr');
    if (firstDataRow) {
        columnsCount = firstDataRow.children.length;
    } else {
        const firstHeaderRow = table.querySelector('thead tr');
        if (firstHeaderRow) {
            columnsCount = Array.from(firstHeaderRow.children)
                .reduce((count, th) => count + (parseInt(th.colSpan) || 1), 0);
        }
    }
    
    // Add empty rows until required number is met
    for (let i = currentRows; i < requiredRows; i++) {
        const row = document.createElement('tr');
        row.className = "border-b border-gray-200";

        for (let j = 0; j < columnsCount; j++) {
            const cell = document.createElement('td');
            cell.className = "px-6 py-3";
            cell.innerHTML = '&nbsp;';
            row.appendChild(cell);
        }

        tbody.appendChild(row);
    }
}
// --- End Utility function ---


document.addEventListener("DOMContentLoaded", function () {
    // 1. Define ALL DOM element variables HERE for guaranteed access
    const tableBody = document.getElementById("table-body");
    const paginationControls = document.getElementById("pagination-controls");
    const startDateInput = document.getElementById("start_date");
    const endDateInput = document.getElementById("end_date");
    const filterButton = document.getElementById("filter-button");
    const clearFilterButton = document.getElementById("clear-filter-button");
    
    // Initial fill, run once when the page loads
    fillTableRows('myTable', 10); 


    // --- Core AJAX Logic ---

    /**
     * Constructs the full query string with current filter values.
     */
    function constructQuery(pageNum = 1) {
        // Read the *current* state of the inputs here
        const startDate = startDateInput ? startDateInput.value : '';
        const endDate = endDateInput ? endDateInput.value : '';
        
        let query = `?page=${pageNum}`;

        if (startDate) {
            query += `&start_date=${startDate}`;
        }
        if (endDate) {
            query += `&end_date=${endDate}`;
        }
        return query;
    }
    
    /**
     * Fetches new data and updates the table/pagination.
     */
    async function loadData(fullQueryString) {
        if (!tableBody) return console.error("Error: tableBody element not found.");

        tableBody.innerHTML = '<tr><td colspan="4" class="text-center py-4">Loading...</td></tr>';
        
        try {
            const response = await fetch(currentUrlPath + fullQueryString, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });
            
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            
            const data = await response.json();

            tableBody.innerHTML = data.table_body_html;
            paginationControls.innerHTML = data.pagination_html;
            
            fillTableRows('myTable', 10); 

            // Update URL to reflect new query (important for clear button state)
            window.history.pushState({}, '', currentUrlPath + fullQueryString);
            
            attachPaginationListeners();
            
            document.querySelector('#myTable').scrollIntoView({ behavior: 'smooth' });
            
        } catch (error) {
            console.error('Fetch error:', error);
            tableBody.innerHTML = '<tr><td colspan="4" class="text-center py-4 text-red-500">Error loading data.</td></tr>';
        }
    }
    
    // --- Event Handlers ---

    // 1. Filter Button Click
    if (filterButton) {
        filterButton.addEventListener('click', function () {
            const newQuery = constructQuery(1);
            loadData(newQuery);
        });
    }
    
    // 2. Clear Filter Button Click (The fix is here)
    if (clearFilterButton) {
        clearFilterButton.addEventListener('click', function() {
            // CRITICAL: Ensure inputs exist and then clear their values.
            if (startDateInput) startDateInput.value = ''; 
            if (endDateInput) endDateInput.value = '';
            
            // constructQuery now reads the empty values and returns "?page=1"
            const newQuery = constructQuery(1); 
            loadData(newQuery); // Sends a request without start_date or end_date
        });
    }

    // 3. Pagination Link Clicks
    function attachPaginationListeners() {
        if (!paginationControls) return;

        paginationControls.querySelectorAll('.ajax-page').forEach(link => {
            link.removeEventListener('click', handlePaginationClick); 
            link.addEventListener('click', handlePaginationClick); 
        });
    }
    
    function handlePaginationClick(e) {
        e.preventDefault();
        const fullQueryString = e.target.getAttribute('href'); 
        loadData(fullQueryString);
    }
    
    // Initial setup
    attachPaginationListeners();
});