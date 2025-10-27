// static/js/scheduling_export.js

var schedulingApp = schedulingApp || {};

schedulingApp.export = {
    exportVisibleDataToXlsx: function() {
        // ... (existing code for grid export) ...
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
    },

    exportFgDetails: function(bucket, cardElement) {
        // ... (existing code - slightly modified) ...
        if (!bucket) return;

        const valueElement = cardElement.querySelector('.summary-value');
        const originalValueText = valueElement.textContent; // Store the formatted text

        // Indicate loading state (keep value, change opacity)
        cardElement.style.opacity = '0.7';
        cardElement.style.pointerEvents = 'none'; // Disable further clicks

        const url = `/scheduling/api/export-fg-details?bucket=${encodeURIComponent(bucket)}`;

        fetch(url)
            .then(response => {
                if (!response.ok) {
                     return response.text().then(text => {
                         try {
                             const data = JSON.parse(text);
                              // Check if flash message might be in HTML response on redirect
                             if (typeof data === 'string' && data.includes('alert-error')) {
                                 const match = data.match(/<div class="alert alert-error">\s*(.*?)\s*<\/div>/);
                                 throw new Error(match ? match[1] : response.statusText);
                             }
                             throw new Error(data.message || response.statusText);
                         } catch (e) {
                             throw new Error(text || response.statusText);
                         }
                     });
                }
                const disposition = response.headers.get('Content-Disposition');
                let filename = `fg_inventory_detail_${bucket}.xlsx`; // Default filename
                if (disposition && disposition.indexOf('attachment') !== -1) {
                    const filenameRegex = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/;
                    const matches = filenameRegex.exec(disposition);
                    if (matches != null && matches[1]) {
                        filename = matches[1].replace(/['"]/g, '');
                    }
                }
                return Promise.all([response.blob(), filename]);
            })
            .then(([blob, filename]) => {
                const downloadUrl = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.style.display = 'none'; a.href = downloadUrl; a.download = filename;
                document.body.appendChild(a); a.click();
                window.URL.revokeObjectURL(downloadUrl); document.body.removeChild(a);
                cardElement.style.opacity = '1'; cardElement.style.pointerEvents = 'auto';
                schedulingApp.utils.calculateTotals();
            })
            .catch(error => {
                console.error(`Error exporting FG details for bucket ${bucket}:`, error);
                dtUtils.showAlert(`Error exporting details: ${error.message}`, 'error');
                cardElement.style.opacity = '1'; cardElement.style.pointerEvents = 'auto';
                valueElement.textContent = originalValueText; // Restore original value on error
            });
    },

    // --- NEW FUNCTION ---
    exportShippedDetails: function(cardElement) {
        const valueElement = cardElement.querySelector('.summary-value');
        const originalValueText = valueElement.textContent; // Store the formatted text

        // Indicate loading state
        cardElement.style.opacity = '0.7';
        cardElement.style.pointerEvents = 'none'; // Disable further clicks

        const url = `/scheduling/api/export-shipped-details`; // No bucket needed

        fetch(url)
            .then(response => {
                if (!response.ok) {
                    return response.text().then(text => {
                        try {
                            const data = JSON.parse(text);
                            // Check for flash message in HTML response
                             if (typeof data === 'string' && data.includes('alert-error')) {
                                 const match = data.match(/<div class="alert alert-error">\s*(.*?)\s*<\/div>/);
                                 throw new Error(match ? match[1] : response.statusText);
                             }
                            throw new Error(data.message || response.statusText);
                        } catch (e) {
                            throw new Error(text || response.statusText);
                        }
                    });
                }
                const disposition = response.headers.get('Content-Disposition');
                let filename = `shipped_details_current_month.xlsx`; // Default
                if (disposition && disposition.indexOf('attachment') !== -1) {
                    const filenameRegex = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/;
                    const matches = filenameRegex.exec(disposition);
                    if (matches != null && matches[1]) {
                        filename = matches[1].replace(/['"]/g, '');
                    }
                }
                return Promise.all([response.blob(), filename]);
            })
            .then(([blob, filename]) => {
                const downloadUrl = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.style.display = 'none'; a.href = downloadUrl; a.download = filename;
                document.body.appendChild(a); a.click();
                window.URL.revokeObjectURL(downloadUrl); document.body.removeChild(a);
                cardElement.style.opacity = '1'; cardElement.style.pointerEvents = 'auto';
                // Value doesn't need recalculation here, it's static for the month
            })
            .catch(error => {
                console.error(`Error exporting shipped details:`, error);
                dtUtils.showAlert(`Error exporting shipped details: ${error.message}`, 'error');
                cardElement.style.opacity = '1'; cardElement.style.pointerEvents = 'auto';
                valueElement.textContent = originalValueText; // Restore original value on error
            });
    }
    // --- END NEW FUNCTION ---
};