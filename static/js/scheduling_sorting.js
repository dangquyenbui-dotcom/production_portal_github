// static/js/scheduling_sorting.js

var schedulingApp = schedulingApp || {};

schedulingApp.sorting = {
    SORT_STORAGE_KEY: 'schedulingSortState',
    sortState: { // Default sort
        column: null, // Example: 'Due to Ship'
        direction: 'none', // 'asc' or 'desc'
        columnIndex: -1, // Will be calculated
        columnType: 'string'
    },

    initializeSorting: function() {
        document.querySelectorAll('.grid-table .sortable').forEach(th => {
            th.removeEventListener('click', schedulingApp.sorting.handleSort); // Remove potential duplicates
            th.addEventListener('click', schedulingApp.sorting.handleSort);
        });
        schedulingApp.sorting.restoreSortState(); // Load saved or default state
        schedulingApp.sorting.updateSortIndicators(); // Apply indicators based on loaded state
    },

    handleSort: function(e) {
        const th = e.currentTarget;
        const columnId = th.dataset.columnId;
        const columnType = th.dataset.type || 'string';
        const columnIndex = Array.from(th.parentElement.children).indexOf(th);

        if (!columnId) return; // Ignore clicks on non-sortable headers if any

        if (schedulingApp.sorting.sortState.column === columnId) {
            schedulingApp.sorting.sortState.direction = schedulingApp.sorting.sortState.direction === 'asc' ? 'desc' : 'asc';
        } else {
            schedulingApp.sorting.sortState.column = columnId;
            schedulingApp.sorting.sortState.direction = 'asc'; // Default to ascending on new column
        }
        schedulingApp.sorting.sortState.columnIndex = columnIndex;
        schedulingApp.sorting.sortState.columnType = columnType;

        schedulingApp.sorting.saveSortState();
        schedulingApp.sorting.sortTable(); // Apply the sort immediately
        schedulingApp.sorting.updateSortIndicators();
    },

    updateSortIndicators: function() {
        document.querySelectorAll('.grid-table .sortable').forEach(th => {
            const indicator = th.querySelector('.sort-indicator');
            if (!indicator) return;

            th.classList.remove('sorted-asc', 'sorted-desc');
            indicator.textContent = ''; // Clear indicator

            if (th.dataset.columnId === schedulingApp.sorting.sortState.column) {
                if (schedulingApp.sorting.sortState.direction === 'asc') {
                    th.classList.add('sorted-asc');
                    indicator.textContent = '↑';
                } else if (schedulingApp.sorting.sortState.direction === 'desc') {
                    th.classList.add('sorted-desc');
                    indicator.textContent = '↓';
                }
            }
        });
    },

    sortTable: function() {
        const state = schedulingApp.sorting.sortState;
        if (!state.column || state.columnIndex < 0 || state.direction === 'none') {
            console.log("Sorting skipped: No column or direction selected.");
            return; // Don't sort if no column/direction
        }

        const tbody = document.getElementById('schedule-body');
        const rows = Array.from(tbody.querySelectorAll('tr:not(.hidden-row)')); // Only sort visible rows

        rows.sort((a, b) => {
            const cellA = a.cells.length > state.columnIndex ? a.cells[state.columnIndex] : null;
            const cellB = b.cells.length > state.columnIndex ? b.cells[state.columnIndex] : null;

            const valA = schedulingApp.utils.getSortValue(cellA, state.columnType);
            const valB = schedulingApp.utils.getSortValue(cellB, state.columnType);

            let comparison = 0;
            if (valA === null && valB === null) comparison = 0;
            else if (valA === null) comparison = -1; // Sort nulls first
            else if (valB === null) comparison = 1;
            else if (valA > valB) comparison = 1;
            else if (valA < valB) comparison = -1;

            return state.direction === 'asc' ? comparison : -comparison;
        });

        // Re-append sorted visible rows. Hidden rows remain untouched in their original order.
        rows.forEach(row => tbody.appendChild(row));

        // Re-attach listeners if sorting messed them up (though appendChild usually preserves them)
        schedulingApp.editing.attachEditableListeners(tbody);
    },

    saveSortState: function() {
        sessionStorage.setItem(schedulingApp.sorting.SORT_STORAGE_KEY, JSON.stringify(schedulingApp.sorting.sortState));
    },

    restoreSortState: function() {
        const savedSort = sessionStorage.getItem(schedulingApp.sorting.SORT_STORAGE_KEY);
        let needsDefault = true;
        if (savedSort) {
            try {
                const parsedSort = JSON.parse(savedSort);
                if (parsedSort && typeof parsedSort === 'object' && 'column' in parsedSort && parsedSort.column) {
                    const headerEl = document.querySelector(`.sortable[data-column-id="${parsedSort.column}"]`);
                    if(headerEl) {
                         // Recalculate index and type from the header element itself
                        parsedSort.columnIndex = Array.from(headerEl.parentElement.children).indexOf(headerEl);
                        parsedSort.columnType = headerEl.dataset.type || 'string';
                        schedulingApp.sorting.sortState = parsedSort;
                        needsDefault = false;
                        console.log("Restored sort state:", schedulingApp.sorting.sortState);
                    } else {
                         console.warn("Saved sort column not found, removing state:", parsedSort.column);
                         sessionStorage.removeItem(schedulingApp.sorting.SORT_STORAGE_KEY);
                    }
                }
            } catch (e) { console.error("Could not parse saved sort state:", e); sessionStorage.removeItem(schedulingApp.sorting.SORT_STORAGE_KEY); }
        }

        if (needsDefault) {
            // Define a default sort if none restored (e.g., by SO number asc)
            const defaultHeader = document.querySelector('.sortable[data-column-id="SO"]');
            if (defaultHeader) {
                schedulingApp.sorting.sortState = {
                    column: 'SO',
                    direction: 'asc',
                    columnIndex: Array.from(defaultHeader.parentElement.children).indexOf(defaultHeader),
                    columnType: defaultHeader.dataset.type || 'string'
                };
                 console.log("Applied default sort state:", schedulingApp.sorting.sortState);
            } else {
                 console.warn("Could not find default sort column 'SO'.");
                 // Ensure state is valid even if default fails
                 schedulingApp.sorting.sortState = { column: null, direction: 'none', columnIndex: -1, columnType: 'string'};
            }
        }
    }
};