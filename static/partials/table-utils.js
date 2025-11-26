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

    // Run initial padding
    fillTableRows('myTable', 10); 
    attachPaginationListeners(); 

    // --- Loan Application Search/Filter Handlers ---
    const searchInput = document.getElementById("loanSearch");
    const statusFilter = document.getElementById("statusFilter");
    const searchButton = document.getElementById("searchButton");
    const clearButton = document.getElementById("clearButton");
    
    // --- NEW SORTING VARIABLES AND SETUP ---
    const tableHeaders = document.querySelectorAll('th[data-sort]');
    let currentSortField = ''; // Stores the field currently being sorted (e.g., 'member_id__account_number')
    let currentSortOrder = ''; // Stores the current order ('asc' or 'desc')

    /**
     * Constructs the full query string, including search, filter, and sorting.
     */
    function constructLoanQuery(pageNum = 1) {
        const searchTerm = searchInput ? searchInput.value.trim() : '';
        const filterStatus = statusFilter ? statusFilter.value : '';
        
        let query = `?page=${pageNum}`;
        
        // 1. Add Search & Filter parameters
        if (searchTerm) {
            query += `&account=${encodeURIComponent(searchTerm)}`;
        }
        
        if (filterStatus) {
            query += `&status=${encodeURIComponent(filterStatus)}`;
        }
        
        // 2. Add Sorting parameters
        if (currentSortField) {
            query += `&sort_by=${encodeURIComponent(currentSortField)}`;
            query += `&order=${encodeURIComponent(currentSortOrder)}`;
        }
        
        return query;
    }
    
    // --- SORTING HANDLERS ---

    /**
     * Handles the click event on sortable table headers.
     */
    function handleSortClick(e) {
        const field = e.currentTarget.getAttribute('data-sort');
        let order = 'asc';

        if (field === currentSortField) {
            // If the same field is clicked, toggle the order
            order = currentSortOrder === 'asc' ? 'desc' : 'asc';
        }

        currentSortField = field;
        currentSortOrder = order;

        // Apply new sort logic and reload data (starting from page 1)
        const newQuery = constructLoanQuery(1); 
        loadData(newQuery);
        // Note: You would call a function here to update the visual sort icons/arrows
        updateSortIcons(currentSortField, currentSortOrder);
    }
    
    /**
     * Attaches click listeners to all sortable table headers.
     */
    tableHeaders.forEach(header => {
        header.addEventListener('click', handleSortClick);
    });
    
    // NOTE: You would define a function named 'updateSortIcons' 
    // elsewhere to handle visual feedback.
    function updateSortIcons(field, order) {
    // 1. Clear ALL icons on ALL headers first
    document.querySelectorAll('th[data-sort] .asc-icon, th[data-sort] .desc-icon').forEach(icon => {
        icon.classList.add('hidden'); // Hide all icons
    });
    
    // 2. If a field and order are provided, show the correct icon
    if (field && order) {
        // Find the specific sort-icon span for the current field
        const sortIconContainer = document.querySelector(`th[data-sort="${field}"] .sort-icon`);
        
        if (sortIconContainer) {
            if (order === 'asc') {
                // Find and SHOW the ascending icon
                sortIconContainer.querySelector('.asc-icon').classList.remove('hidden');
                sortIconContainer.querySelector('.desc-icon').classList.add('hidden');
                // Optional: Highlight the text color for the sorted column
                sortIconContainer.closest('th').classList.add('text-indigo-600'); 
            } else if (order === 'desc') {
                // Find and SHOW the descending icon
                sortIconContainer.querySelector('.asc-icon').classList.add('hidden');
                sortIconContainer.querySelector('.desc-icon').classList.remove('hidden');
                // Optional: Highlight the text color for the sorted column
                sortIconContainer.closest('th').classList.add('text-indigo-600');
            }
        }
    }
    
    // 3. Clear text color from headers that are NOT currently sorted
    document.querySelectorAll('th[data-sort]').forEach(th => {
        if (th.getAttribute('data-sort') !== field) {
            th.classList.remove('text-indigo-600');
        }
    });
}


    // --- SEARCH/FILTER HANDLERS (UNCHANGED, but now calls constructLoanQuery with sort state) ---

    if (searchButton) {
        searchButton.addEventListener('click', function () {
            // New search always starts at page 1
            const newQuery = constructLoanQuery(1); 
            loadData(newQuery); 
        });
    }

    if (clearButton) {
        clearButton.addEventListener('click', function() {
            // Clear search/filter inputs
            if (searchInput) searchInput.value = '';
            if (statusFilter) statusFilter.value = ''; 
            
            // OPTIONAL: Clear sort state on clear (if desired)
            currentSortField = '';
            currentSortOrder = '';
            updateSortIcons('', ''); // Clear visual icons
            
            const newQuery = constructLoanQuery(1); 
            loadData(newQuery); 
        });
    }
    
    if (searchInput) {
        searchInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                searchButton.click();
            }
        });
    }
});

document.addEventListener("DOMContentLoaded", function () {
    const startDateInput = document.getElementById('start_date');
    const endDateInput = document.getElementById('end_date');
    const exportPdfBtn = document.getElementById('exportPdfBtn');
    const filterButton = document.getElementById('filter-button');
    const clearFilterButton = document.getElementById('clear-filter-button');
    
    // Base URL for the PDF export (without query parameters)
    const baseExportUrl = exportPdfBtn.getAttribute('href');

    /**
     * Function to generate and update the PDF export link with current date filters.
     */
    function updateExportLink() {
        const startDate = startDateInput.value;
        const endDate = endDateInput.value;
        let params = [];
        
        if (startDate) {
            params.push(`start_date=${startDate}`);
        }
        if (endDate) {
            params.push(`end_date=${endDate}`);
        }
        
        // Construct the new URL
        let newExportUrl = baseExportUrl;
        if (params.length > 0) {
            newExportUrl += `?${params.join('&')}`;
        }
        
        // Update the link's href
        exportPdfBtn.setAttribute('href', newExportUrl);
    }

    // --- Event Listeners ---
    
    // 1. Update the link whenever a filter button is clicked
    if (filterButton) {
        filterButton.addEventListener('click', updateExportLink);
    }
    
    if (clearFilterButton) {
        clearFilterButton.addEventListener('click', function() {
            // Clear inputs first
            startDateInput.value = '';
            endDateInput.value = '';
            
            // Then update the link to remove parameters
            updateExportLink();
        });
    }

    // 2. Also update the link on input changes (optional, but robust)
    if (startDateInput) {
        startDateInput.addEventListener('change', updateExportLink);
    }
    if (endDateInput) {
        endDateInput.addEventListener('change', updateExportLink);
    }

    // 3. Initial call to set the link if dates are already present on load
    updateExportLink();
});