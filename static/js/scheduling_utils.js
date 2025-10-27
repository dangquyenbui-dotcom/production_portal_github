// static/js/scheduling_utils.js

// Create or use existing namespace
var schedulingApp = schedulingApp || {};

schedulingApp.utils = {
    // --- UI Update Functions ---
    updateLastUpdatedTime: function() {
        const timestampEl = document.getElementById('lastUpdated');
        if (timestampEl) {
            const now = new Date();
            const timeString = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            timestampEl.textContent = `Last Updated: ${timeString}`;
        }
    },

    calculateTotals: function() {
        let totalNoLowRisk = 0;
        let totalHighRisk = 0;

        document.querySelectorAll('#schedule-body tr:not(.hidden-row)').forEach(row => {
            const noLowRiskCell = row.querySelector('[data-calculated-for="No/Low Risk Qty"]');
            const highRiskCell = row.querySelector('[data-calculated-for="High Risk Qty"]');

            if (noLowRiskCell) totalNoLowRisk += parseFloat(noLowRiskCell.textContent.replace(/[$,]/g, '')) || 0;
            if (highRiskCell) totalHighRisk += parseFloat(highRiskCell.textContent.replace(/[$,]/g, '')) || 0;
        });

        document.getElementById('total-no-low-risk').textContent = totalNoLowRisk.toLocaleString('en-US', { style: 'currency', currency: 'USD' });
        document.getElementById('total-high-risk').textContent = totalHighRisk.toLocaleString('en-US', { style: 'currency', currency: 'USD' });

        schedulingApp.utils.updateForecastCards(totalNoLowRisk, totalHighRisk);
    },

    updateForecastCards: function(totalNoLowRisk, totalHighRisk) {
        const getValueFromCardById = (elementId) => {
            const cardElement = document.getElementById(elementId);
            if (!cardElement) return 0;
            return parseFloat(cardElement.textContent.replace(/[$,]/g, '')) || 0;
        };

        const shippedCurrentMonth = getValueFromCardById('shipped-as-value');
        const fgBefore = getValueFromCardById('fg-on-hand-before');
        const fgCurrent = getValueFromCardById('fg-on-hand-current');
        const fgFuture = getValueFromCardById('fg-on-hand-future');

        const forecastLikelyValue = shippedCurrentMonth + totalNoLowRisk + fgBefore + fgCurrent;
        const forecastMaybeValue = shippedCurrentMonth + totalNoLowRisk + totalHighRisk + fgBefore + fgCurrent + fgFuture;

        document.getElementById('forecast-likely-value').textContent = forecastLikelyValue.toLocaleString('en-US', { style: 'currency', currency: 'USD' });
        document.getElementById('forecast-maybe-value').textContent = forecastMaybeValue.toLocaleString('en-US', { style: 'currency', currency: 'USD' });
    },

    updateRowCount: function() {
        const totalRows = document.querySelectorAll('#schedule-body tr[data-so-number]').length;
        const visibleRows = document.querySelectorAll('#schedule-body tr:not(.hidden-row)').length;
        const rowCountEl = document.getElementById('rowCount');
        if (rowCountEl) {
             if (totalRows === 0 && document.querySelector('#schedule-body td[colspan]')) {
                 rowCountEl.textContent = `Showing 0 of 0 rows`;
            } else {
                 rowCountEl.textContent = `Showing ${visibleRows} of ${totalRows} rows`;
            }
        }
    },

    // --- Dropdown/Select Helpers ---
    populateSelect: function(selectId, options, addBlankOption = false, selectedValue = null) {
        const select = document.getElementById(selectId);
        if (!select) return;
        const currentValue = select.value; // Store current value

        select.innerHTML = `<option value="">All</option>`; // Reset options
        options.forEach(optionText => {
            if (optionText) {
                const option = document.createElement('option');
                option.value = optionText;
                option.textContent = optionText;
                select.appendChild(option);
            }
        });
        if (addBlankOption) {
            const blankOption = document.createElement('option');
            blankOption.value = 'Blank';
            blankOption.textContent = '(No Date)';
            select.appendChild(blankOption);
        }

        // Try to restore original value if it exists, otherwise use selectedValue
        const optionExists = Array.from(select.options).some(opt => opt.value === currentValue);
        if (optionExists) {
            select.value = currentValue;
        } else if (selectedValue) {
             const selectedOptionExists = Array.from(select.options).some(opt => opt.value === selectedValue);
             if (selectedOptionExists) {
                select.value = selectedValue;
             } else {
                 select.value = ""; // Default to "All" if selectedValue no longer valid
             }
        } else {
            select.value = ""; // Default to "All"
        }
    },

    populateMultiSelect: function(baseId, options, addBlankOption = false) {
        const dropdown = document.getElementById(`${baseId}Dropdown`);
        if (!dropdown) return;
        const currentValues = new Set(Array.from(dropdown.querySelectorAll('input:checked')).map(cb => cb.value)); // Store current selections

        dropdown.innerHTML = ''; // Clear existing options

        options.forEach(optionText => {
            if (optionText) {
                const label = document.createElement('label');
                const checkbox = document.createElement('input');
                checkbox.type = 'checkbox';
                checkbox.value = optionText;
                label.appendChild(checkbox);
                label.appendChild(document.createTextNode(' ' + optionText));
                dropdown.appendChild(label);
            }
        });

        if (addBlankOption) {
            const label = document.createElement('label');
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.value = 'Blank';
            label.appendChild(checkbox);
            label.appendChild(document.createTextNode(' (No Date)'));
            dropdown.appendChild(label);
        }

        // Reapply original selections if they still exist
        dropdown.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
            // Use CSS.escape for values that might contain special characters (like '/')
            if (currentValues.has(checkbox.value)) {
                checkbox.checked = true;
            }
        });

        schedulingApp.utils.updateMultiSelectButtonText(baseId); // Update button text
    },

    updateMultiSelectButtonText: function(baseId) {
        const dropdown = document.getElementById(`${baseId}Dropdown`);
        const selected = Array.from(dropdown.querySelectorAll('input:checked'));
        const btn = document.getElementById(`${baseId}Btn`);
        if (selected.length === 0) {
            btn.textContent = 'All';
        } else if (selected.length === 1) {
            btn.textContent = selected[0].value === 'Blank' ? '(No Date)' : selected[0].value;
        } else {
            btn.textContent = `${selected.length} selected`;
        }
    },

    closeAllMultiSelectDropdowns: function() {
        document.querySelectorAll('.multiselect-dropdown.show').forEach(d => {
            d.classList.remove('show');
        });
    },

    // --- Sorting Helper ---
    getSortValue: function(cell, type) {
        if (!cell) return null;
        let text = cell.textContent.trim();

        // Clean up text by removing indicators/buttons
        cell.querySelectorAll('.status-indicator, .suggestion-fix').forEach(el => {
            text = text.replace(el.textContent, '').trim();
        });

        switch (type) {
            case 'numeric':
                const num = parseFloat(text.replace(/[$,]/g, ''));
                return isNaN(num) ? -Infinity : num; // Sort non-numbers first
            case 'date':
                if (!text || !text.includes('/')) return new Date(0); // Sort empty/invalid dates first
                const parts = text.split('/');
                if (parts.length !== 3) return new Date(0);
                let year = parseInt(parts[2]);
                if (isNaN(year)) return new Date(0);
                if (year < 100) year += 2000;
                const month = parseInt(parts[0]) - 1;
                const day = parseInt(parts[1]);
                if (isNaN(month) || isNaN(day)) return new Date(0);
                return new Date(year, month, day);
            default: // string
                return text.toLowerCase();
        }
    }
};