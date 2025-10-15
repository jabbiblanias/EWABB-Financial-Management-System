function fillTableRows(tableId, requiredRows) {
    const table = document.getElementById(tableId);
    const tbody = table.querySelector('tbody');
    const currentRows = tbody.querySelectorAll('tr').length;
    const columnsCount = table.querySelectorAll('th').length;

    // Add empty rows if needed
    for (let i = currentRows; i < requiredRows; i++) {
        const row = document.createElement('tr');
        row.className = "border-b border-gray-200"

        for (let j = 0; j < columnsCount; j++) {
            const cell = document.createElement('td');
            cell.className = "px-6 py-3"
            cell.innerHTML = '&nbsp;'; // or leave empty: cell.textContent = '';
            row.appendChild(cell);
        }

        tbody.appendChild(row);
    }
}