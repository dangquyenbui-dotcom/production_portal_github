// static/js/scheduling_filters.js

var schedulingApp = schedulingApp || {};

schedulingApp.filters = {
    FILTER_STORAGE_KEY: 'schedulingFilters',

    saveFilters: function() {
        const selectedSoTypes = Array.from(document.querySelectorAll('#soTypeFilterDropdown input:checked')).map(cb => cb.value);
        const selectedFacilities = Array.from(document.querySelectorAll('#facilityFilterDropdown input:checked')).map(cb => cb.value);
        const selectedDueShip = Array.from(document.querySelectorAll('#dueShipFilterDropdown input:checked')).map(cb => cb.value);

        const filters = {
            facility: selectedFacilities,
            bu: document.getElementById('buFilter').value,
            soType: selectedSoTypes,
            customer: document.getElementById('customerFilter').value,
            dueShip: selectedDueShip,
        };
        sessionStorage.setItem(schedulingApp.filters.FILTER_STORAGE_KEY, JSON.stringify(filters));
    },

    restoreFilters: function() {
        const savedFilters = JSON.parse(sessionStorage.getItem(schedulingApp.filters.FILTER_STORAGE_KEY));
        if (savedFilters) {
            // Restore single selects - populateSelect called during updateFilterOptions will handle keeping value
            document.getElementById('buFilter').value = savedFilters.bu || '';
            document.getElementById('customerFilter').value = savedFilters.customer || '';

            // Restore Multi-selects (will be fully applied during initial updateFilterOptions)
            schedulingApp.filters.restoreMultiSelect('soTypeFilter', savedFilters.soType);
            schedulingApp.filters.restoreMultiSelect('facilityFilter', savedFilters.facility);
            schedulingApp.filters.restoreMultiSelect('dueShipFilter', savedFilters.dueShip);
        }
    },

     // Helper specifically for restoreFilters, relies on elements existing
    restoreMultiSelect: function(baseId, values) {
        const dropdown = document.getElementById(`${baseId}Dropdown`);
        if (!dropdown) return;
        dropdown.querySelectorAll('input').forEach(cb => cb.checked = false); // Ensure clean slate
        if (values && values.length > 0) {
            values.forEach(value => {
                const checkbox = dropdown.querySelector(`input[value="${CSS.escape(value)}"]`);
                if (checkbox) checkbox.checked = true;
            });
        }
        schedulingApp.utils.updateMultiSelectButtonText(baseId); // Update button after restoring checks
    },

    resetFilters: function() {
        document.getElementById('buFilter').value = '';
        document.getElementById('customerFilter').value = '';

        ['soTypeFilter', 'facilityFilter', 'dueShipFilter'].forEach(baseId => {
            const dropdown = document.getElementById(`${baseId}Dropdown`);
            if(dropdown) {
                dropdown.querySelectorAll('input:checked').forEach(cb => cb.checked = false);
            }
            schedulingApp.utils.updateMultiSelectButtonText(baseId);
        });

        sessionStorage.removeItem(schedulingApp.filters.FILTER_STORAGE_KEY);
        // sessionStorage.removeItem(schedulingApp.sorting.SORT_STORAGE_KEY); // Optionally reset sort too

        schedulingApp.filters.filterGrid(); // Re-filter and update options
    },

    updateFilterOptions: function(isInitialLoad = false) {
        const currentSelections = {
            bu: document.getElementById('buFilter').value,
            customer: document.getElementById('customerFilter').value,
            facility: Array.from(document.querySelectorAll('#facilityFilterDropdown input:checked')).map(cb => cb.value),
            soType: Array.from(document.querySelectorAll('#soTypeFilterDropdown input:checked')).map(cb => cb.value),
            dueShip: Array.from(document.querySelectorAll('#dueShipFilterDropdown input:checked')).map(cb => cb.value)
        };

        const allRows = document.getElementById('schedule-body').querySelectorAll('tr');
        const allFoundOptions = {
            facility: new Set(), bu: new Set(), soType: new Set(), customer: new Set(), dueShip: new Set()
        };
        let anyBlanks = { dueShip: false };

        allRows.forEach(row => {
            if (row.cells.length < 5) return;

            const facility = row.querySelector('[data-field="Facility"]')?.textContent || '';
            const bu = row.querySelector('[data-field="BU"]')?.textContent || '';
            const soType = row.querySelector('[data-field="SO Type"]')?.textContent || '';
            const customer = row.querySelector('[data-field="Customer Name"]')?.textContent || '';
            const dueDate = row.querySelector('[data-field="Due to Ship"]')?.textContent.trim() || '';
            const dueDateMonthYear = (dueDate && dueDate.includes('/')) ? `${dueDate.split('/')[0].padStart(2, '0')}/${dueDate.split('/')[2]}` : 'Blank';

            if (facility) allFoundOptions.facility.add(facility);
            if (bu) allFoundOptions.bu.add(bu);
            if (soType) allFoundOptions.soType.add(soType);
            if (customer) allFoundOptions.customer.add(customer);
            if (dueDateMonthYear === 'Blank') anyBlanks.dueShip = true; else allFoundOptions.dueShip.add(dueDateMonthYear);
        });

        // Sort options
        const sortedFacilities = Array.from(allFoundOptions.facility).sort();
        const sortedBUs = Array.from(allFoundOptions.bu).sort();
        const sortedSoTypes = Array.from(allFoundOptions.soType).sort();
        const sortedCustomers = Array.from(allFoundOptions.customer).sort();
        const sortedDueDates = Array.from(allFoundOptions.dueShip).sort((a, b) => {
            const [aMonth, aYear] = a.split('/');
            const [bMonth, bYear] = b.split('/');
            return new Date(aYear, aMonth - 1) - new Date(bYear, bMonth - 1);
        });

        // Populate dropdowns with all options
        schedulingApp.utils.populateMultiSelect('facilityFilter', sortedFacilities, false);
        schedulingApp.utils.populateSelect('buFilter', sortedBUs, false, isInitialLoad ? (JSON.parse(sessionStorage.getItem(schedulingApp.filters.FILTER_STORAGE_KEY))?.bu || '') : currentSelections.bu);
        schedulingApp.utils.populateMultiSelect('soTypeFilter', sortedSoTypes, false);
        schedulingApp.utils.populateSelect('customerFilter', sortedCustomers, false, isInitialLoad ? (JSON.parse(sessionStorage.getItem(schedulingApp.filters.FILTER_STORAGE_KEY))?.customer || '') : currentSelections.customer);
        schedulingApp.utils.populateMultiSelect('dueShipFilter', sortedDueDates, anyBlanks.dueShip);

        // Reapply selections after population
        if (!isInitialLoad) {
            schedulingApp.filters.restoreMultiSelect('facilityFilter', currentSelections.facility);
            schedulingApp.filters.restoreMultiSelect('soTypeFilter', currentSelections.soType);
            schedulingApp.filters.restoreMultiSelect('dueShipFilter', currentSelections.dueShip);
            // Single selects retain value via populateSelect logic
        } else {
             // On initial load, restoreMultiSelect was already called by restoreFilters
        }
    },

    filterGrid: function() {
        console.log("Filtering grid..."); // Debug log
        const facilityFilter = Array.from(document.querySelectorAll('#facilityFilterDropdown input:checked')).map(cb => cb.value);
        const buFilter = document.getElementById('buFilter').value;
        const soTypeFilter = Array.from(document.querySelectorAll('#soTypeFilterDropdown input:checked')).map(cb => cb.value);
        const customerFilter = document.getElementById('customerFilter').value;
        const dueShipFilter = Array.from(document.querySelectorAll('#dueShipFilterDropdown input:checked')).map(cb => cb.value);

        let visibleCount = 0;
        const tbody = document.getElementById('schedule-body');
        if (!tbody) return;

        tbody.querySelectorAll('tr').forEach(row => {
            if (row.cells.length < 2) return;

            const facility = row.querySelector('[data-field="Facility"]')?.textContent || '';
            const bu = row.querySelector('[data-field="BU"]')?.textContent || '';
            const soType = row.querySelector('[data-field="SO Type"]')?.textContent || '';
            const customer = row.querySelector('[data-field="Customer Name"]')?.textContent || '';
            const dueDate = row.querySelector('[data-field="Due to Ship"]')?.textContent.trim() || '';
            const dueDateMonthYear = (dueDate && dueDate.includes('/')) ? `${dueDate.split('/')[0].padStart(2, '0')}/${dueDate.split('/')[2]}` : 'Blank';

            let show = true;
            if (facilityFilter.length > 0 && !facilityFilter.includes(facility)) show = false;
            if (buFilter && bu !== buFilter) show = false;
            if (soTypeFilter.length > 0 && !soTypeFilter.includes(soType)) show = false;
            if (customerFilter && customer !== customerFilter) show = false;
            if (dueShipFilter.length > 0 && !dueShipFilter.includes(dueDateMonthYear)) show = false;

            row.classList.toggle('hidden-row', !show);
            if (show) {
                visibleCount++;
            }
        });

        console.log(`Visible rows after filtering: ${visibleCount}`); // Debug log

        schedulingApp.filters.saveFilters(); // Save the state
        schedulingApp.filters.updateFilterOptions(false); // Update available options based on full dataset but restore current selections
        schedulingApp.utils.updateRowCount(); // Update displayed count
        schedulingApp.utils.calculateTotals(); // Recalculate summary cards
        schedulingApp.editing.validateAllRows(); // Re-apply validation styling

        // Apply sorting to the now visible rows
        schedulingApp.sorting.sortTable();
    }
};