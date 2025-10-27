// static/js/scheduling_export.js

var schedulingApp = schedulingApp || {};

schedulingApp.export = {
    exportVisibleDataToXlsx: function() {
        const exportBtn = document.getElementById('exportBtn');
        exportBtn.disabled = true;
        exportBtn.textContent = '📥 Generating...';

        const headers = Array.from(document.querySelectorAll('.grid-table thead th'))
            .filter(th => th.style.display !== 'none')
            .map(th => {
                const clone = th.cloneNode(true);
                const indicator = clone.querySelector('.sort-indicator');
                if (indicator) indicator.remove();
                return clone.textContent.trim();
            });

        const rows = [];
        document.querySelectorAll('#schedule-body tr:not(.hidden-row)').forEach(row => {
            const rowData = [];
            Array.from(row.cells).forEach((cell, index) => {
                const header = document.querySelector(`.grid-table thead th:nth-child(${index + 1})`);
                if (header && header.style.display !== 'none') {
                    const cellClone = cell.cloneNode(true);
                    cellClone.querySelectorAll('.status-indicator, .suggestion-fix').forEach(el => el.remove());
                    rowData.push(cellClone.textContent.trim());
                }
            });
            rows.push(rowData);
        });

        if (rows.length === 0) {
            dtUtils.showAlert('No data to export.', 'info');
            exportBtn.disabled = false;
            exportBtn.textContent = '📥 Download XLSX';
            return;
        }

        fetch('/scheduling/api/export-xlsx', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ headers, rows })
        })
        .then(response => {
            if (!response.ok) { throw new Error('Network response was not ok.'); }
            const disposition = response.headers.get('Content-Disposition');
            const matches = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/.exec(disposition);
            const filename = (matches != null && matches[1]) ? matches[1].replace(/['"]/g, '') : 'schedule_export.xlsx';
            return Promise.all([response.blob(), filename]);
        })
        .then(([blob, filename]) => {
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a); // Clean up link

            exportBtn.disabled = false;
            exportBtn.textContent = '📥 Download XLSX';
        })
        .catch(error => {
            console.error('Export error:', error);
            dtUtils.showAlert('An error occurred during the export.', 'error');
            exportBtn.disabled = false;
            exportBtn.textContent = '📥 Download XLSX';
        });
    }
};