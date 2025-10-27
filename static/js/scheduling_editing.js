// static/js/scheduling_editing.js

var schedulingApp = schedulingApp || {};

schedulingApp.editing = {
    attachEditableListeners: function(scope) {
        scope.querySelectorAll('.editable:not(.view-only)').forEach(cell => {
            cell.removeEventListener('blur', schedulingApp.editing.handleCellBlur);
            cell.removeEventListener('focus', schedulingApp.editing.handleCellFocus);
            cell.removeEventListener('keydown', schedulingApp.editing.handleCellKeyDown);

            cell.addEventListener('blur', schedulingApp.editing.handleCellBlur);
            cell.addEventListener('focus', schedulingApp.editing.handleCellFocus);
            cell.addEventListener('keydown', schedulingApp.editing.handleCellKeyDown);
        });
    },

    handleCellBlur: function() {
        const el = this;
        el.querySelectorAll('.status-indicator').forEach(indicator => indicator.remove()); // Clear indicators first

        const originalValue = el.getAttribute('data-original-value') || '0';
        let newValue = el.textContent.trim().replace(/[$,]/g, '');

        if (isNaN(newValue) || newValue.trim() === '') {
            newValue = originalValue; // Revert
            dtUtils.showAlert('Please enter a valid number.', 'error');
        }

        const quantity = parseFloat(newValue);
        // Format content AFTER validation
        el.textContent = quantity.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

        // Re-validate row styling AFTER formatting
        schedulingApp.editing.validateRow(el.closest('tr'));

        // Only save if changed
        if (Math.abs(parseFloat(originalValue) - quantity) < 0.01) {
            return;
        }

        // Add saving indicator
        const statusIndicator = document.createElement('span');
        statusIndicator.className = 'status-indicator saving';
        el.appendChild(statusIndicator);

        const row = el.closest('tr');
        const soNumber = row.dataset.soNumber;
        const partNumber = row.dataset.partNumber;
        const riskType = el.dataset.riskType;
        const price = parseFloat(el.dataset.price) || 0;
        const payload = { so_number: soNumber, part_number: partNumber, risk_type: riskType, quantity: quantity };

        fetch('/scheduling/api/update-projection', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
        .then(response => {
            if (!response.ok) { throw new Error(`HTTP error ${response.status}`); }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                statusIndicator.className = 'status-indicator success';
                el.setAttribute('data-original-value', quantity.toString()); // Update stored original on success

                const calculatedCell = row.querySelector(`[data-calculated-for="${riskType}"]`);
                if (calculatedCell) {
                    const newDollarValue = quantity * price;
                    calculatedCell.textContent = newDollarValue.toLocaleString('en-US', { style: 'currency', currency: 'USD' });
                }
                schedulingApp.utils.calculateTotals(); // Recalculate totals
                setTimeout(() => { statusIndicator.remove(); }, 2000);
            } else {
                throw new Error(data.message || 'Save failed.');
            }
        })
        .catch(error => {
            console.error('Save Error:', error);
            statusIndicator.className = 'status-indicator error';
            // Revert cell content on error
            el.textContent = (parseFloat(originalValue) || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
            // Re-run validation might add back suggestion button
            schedulingApp.editing.validateRow(row);
            dtUtils.showAlert(`Save failed: ${error.message}`, 'error');
        });
    },

    handleCellFocus: function(e) {
        const el = e.target;
        const currentValue = el.textContent.trim().replace(/[$,]/g, '');
        el.setAttribute('data-original-value', parseFloat(currentValue) || 0); // Store numerical value
        el.textContent = currentValue; // Show raw number for editing
        el.querySelectorAll('.suggestion-fix').forEach(btn => btn.remove()); // Remove 'Fix' button

        // Select text
        window.setTimeout(() => {
          const range = document.createRange();
          range.selectNodeContents(el);
          const sel = window.getSelection();
          if (sel) {
              sel.removeAllRanges();
              sel.addRange(range);
          }
        }, 1);
    },

    handleCellKeyDown: function(e) {
        if (!/[\d.]/.test(e.key) && !['Backspace', 'Delete', 'ArrowLeft', 'ArrowRight', 'Tab', 'Enter', 'Home', 'End'].includes(e.key)) {
            if (!(e.ctrlKey && ['a', 'c', 'v', 'x'].includes(e.key.toLowerCase()))) {
                e.preventDefault();
            }
        }
        if (e.key === '.' && e.target.textContent.includes('.')) {
            e.preventDefault();
        }
        if (e.key === 'Enter') {
            e.preventDefault();
            e.target.blur(); // Trigger blur to save
        }
        if (e.key === 'Escape') {
             e.preventDefault();
             const originalValue = e.target.getAttribute('data-original-value') || '0';
             e.target.textContent = (parseFloat(originalValue) || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
             e.target.blur(); // Trigger blur without saving change
        }
    },

    // --- Validation & Suggestion Logic ---
    validateAllRows: function() {
        document.querySelectorAll('#schedule-body tr:not(.hidden-row)').forEach(schedulingApp.editing.validateRow);
    },

    validateRow: function(row) {
        row.classList.remove('row-warning');
        row.querySelectorAll('.suggestion-fix').forEach(btn => btn.remove());

        const netQtyCell = row.querySelector('[data-field="Net Qty"]');
        const noLowRiskCell = row.querySelector('[data-risk-type="No/Low Risk Qty"]');
        const highRiskCell = row.querySelector('[data-risk-type="High Risk Qty"]');

        if (!netQtyCell || !noLowRiskCell || !highRiskCell) return;

        const netQty = parseFloat(netQtyCell.textContent.replace(/,/g, '')) || 0;
        const noLowRiskQty = parseFloat(noLowRiskCell.textContent.replace(/[$,]/g, '')) || 0;
        const highRiskQty = parseFloat(highRiskCell.textContent.replace(/[$,]/g, '')) || 0;
        const totalProjected = noLowRiskQty + highRiskQty;
        const difference = totalProjected - netQty;

        if (Math.abs(difference) > 0.01) {
            row.classList.add('row-warning');
            const suggestedNoLowRisk = Math.max(0, noLowRiskQty - difference);

            if (!noLowRiskCell.querySelector('.suggestion-fix')) { // Prevent adding multiple buttons
                const fixButton = document.createElement('button');
                fixButton.textContent = 'Fix';
                fixButton.dataset.suggestion = suggestedNoLowRisk;
                fixButton.onclick = function(event) {
                    event.stopPropagation();
                    schedulingApp.editing.applySuggestion(this);
                };

                if (difference < 0) { // SHORTFALL
                    fixButton.className = 'suggestion-fix fix-shortfall';
                    fixButton.title = `SHORTFALL (${difference.toFixed(2)}): Suggest setting No/Low Risk to ${suggestedNoLowRisk.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})} to match Net Qty`;
                } else { // SURPLUS
                    fixButton.className = 'suggestion-fix fix-surplus';
                    fixButton.title = `SURPLUS (+${difference.toFixed(2)}): Suggest setting No/Low Risk to ${suggestedNoLowRisk.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})} to match Net Qty`;
                }
                noLowRiskCell.appendChild(fixButton);
            }
        }
    },

    applySuggestion: function(buttonElement) {
        const suggestion = parseFloat(buttonElement.dataset.suggestion);
        const cell = buttonElement.closest('td');

        if (cell && !isNaN(suggestion)) {
            const originalValue = cell.getAttribute('data-original-value') || cell.textContent.trim().replace(/[$,]/g, '');
            cell.textContent = suggestion.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
            buttonElement.remove(); // Remove button

            // Add saving indicator
            const statusIndicator = document.createElement('span');
            statusIndicator.className = 'status-indicator saving';
            cell.appendChild(statusIndicator);

            const row = cell.closest('tr');
            const soNumber = row.dataset.soNumber;
            const partNumber = row.dataset.partNumber;
            const riskType = cell.dataset.riskType;
            const price = parseFloat(cell.dataset.price) || 0;
            const payload = { so_number: soNumber, part_number: partNumber, risk_type: riskType, quantity: suggestion };

            fetch('/scheduling/api/update-projection', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            })
            .then(response => {
                if (!response.ok) { throw new Error(`HTTP error ${response.status}`); }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    statusIndicator.className = 'status-indicator success';
                    cell.setAttribute('data-original-value', suggestion.toString()); // Update original on success

                    const calculatedCell = row.querySelector(`[data-calculated-for="${riskType}"]`);
                    if (calculatedCell) {
                        const newDollarValue = suggestion * price;
                        calculatedCell.textContent = newDollarValue.toLocaleString('en-US', { style: 'currency', currency: 'USD' });
                    }
                    schedulingApp.utils.calculateTotals(); // Recalculate totals
                    schedulingApp.editing.validateRow(row); // Re-validate (should remove warning)
                    setTimeout(() => { statusIndicator.remove(); }, 2000);
                } else {
                    throw new Error(data.message || 'Save failed.');
                }
            })
            .catch(error => {
                console.error('Save Error:', error);
                dtUtils.showAlert(`Save failed: ${error.message}`, 'error');
                cell.textContent = (parseFloat(originalValue) || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
                statusIndicator.className = 'status-indicator error';
                schedulingApp.editing.validateRow(row); // Re-validate to potentially show button again
            });
        }
    }
};