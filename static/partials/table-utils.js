function fillTableRows(tableId, requiredRows) {
    const table = document.getElementById(tableId);
    if (!table) return;

    const tbody = table.querySelector('tbody');
    if (!tbody) return;

    const currentRows = tbody.querySelectorAll('tr').length;

    // Detect actual column count
    let columnsCount = 0;
    const firstDataRow = tbody.querySelector('tr');
    if (firstDataRow) {
        columnsCount = firstDataRow.children.length;
    } else {
        // fallback to first thead row
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
