// static/js/scheduling_init.js

// Ensure namespace exists
var schedulingApp = schedulingApp || {};

document.addEventListener('DOMContentLoaded', function() {
    console.log("Scheduling App Initializing...");

    // Initialize UI components first
    schedulingApp.columns.initializeColumnToggle();
    schedulingApp.sorting.initializeSorting(); // Reads saved state, sets initial indicators

    // Attach event listeners
    schedulingApp.init.attachAllEventListeners();

    // Populate filter options based on the full initial dataset
    schedulingApp.filters.updateFilterOptions(true);

    // Restore saved filter selections (multi-selects need options populated first)
    schedulingApp.filters.restoreFilters();

    // Apply filters and the restored/default sort to the grid
    schedulingApp.filters.filterGrid(); // This now calls sortTable internally

    // Update timestamp
    schedulingApp.utils.updateLastUpdatedTime();

    // Show refresh confirmation if applicable
    if (sessionStorage.getItem('wasRefreshed')) { // Corrected key check
        dtUtils.showAlert('Data refreshed successfully!', 'success');
        sessionStorage.removeItem('wasRefreshed'); // Corrected key removal
    }

     // --- Add global click listener AFTER other initializations ---
    document.addEventListener('click', (e) => {
        const isOutsideMulti = !e.target.closest('.multiselect-container');
        const isOutsideColumn = !e.target.closest('.column-toggle-container');
        const columnsBtn = document.getElementById('columnsBtn'); // Need ref to button

        if (isOutsideMulti) {
            schedulingApp.utils.closeAllMultiSelectDropdowns();
        }
        // Also close column dropdown if click is outside and not on the button
        if (isOutsideColumn && columnsBtn && !columnsBtn.contains(e.target)) {
             const columnDropdown = document.getElementById('column-dropdown');
             if (columnDropdown) columnDropdown.classList.remove('show');
        }
    });
     // --- END ---

    console.log("Scheduling App Initialized.");
});

schedulingApp.init = {
    attachAllEventListeners: function() {
        // Filter changes trigger filterGrid
        document.getElementById('buFilter').addEventListener('change', schedulingApp.filters.filterGrid);
        document.getElementById('customerFilter').addEventListener('change', schedulingApp.filters.filterGrid);
        // Multi-select changes are handled within setupMultiSelect

        // Buttons
        document.getElementById('exportBtn').addEventListener('click', schedulingApp.export.exportVisibleDataToXlsx);
        document.getElementById('resetBtn').addEventListener('click', schedulingApp.filters.resetFilters);
        document.getElementById('refreshBtn').addEventListener('click', () => {
            schedulingApp.filters.saveFilters();
            schedulingApp.sorting.saveSortState(); // Save sort state
            sessionStorage.setItem('wasRefreshed', 'true'); // Set refresh flag with correct key
            window.location.reload();
        });

        // Setup multi-select interactions
        schedulingApp.init.setupMultiSelect('facilityFilter');
        schedulingApp.init.setupMultiSelect('soTypeFilter');
        schedulingApp.init.setupMultiSelect('dueShipFilter');

        // Initial attachment for editable cells (will be re-attached after sorting/filtering)
        schedulingApp.editing.attachEditableListeners(document.getElementById('schedule-body'));

        // Sorting listeners are attached in schedulingApp.sorting.initializeSorting
        // Column listeners are attached in schedulingApp.columns.initializeColumnToggle

        // --- FG summary card clicks ---
        document.getElementById('fg-card-prior')?.addEventListener('click', function() {
            schedulingApp.export.exportFgDetails('prior', this);
        });
        document.getElementById('fg-card-mid')?.addEventListener('click', function() {
            schedulingApp.export.exportFgDetails('mid', this);
        });
        document.getElementById('fg-card-recent')?.addEventListener('click', function() {
            schedulingApp.export.exportFgDetails('recent', this);
        });

        // --- NEW: Add listener for Shipped summary card click ---
        document.getElementById('shipped-card')?.addEventListener('click', function() {
            schedulingApp.export.exportShippedDetails(this);
        });
        // --- END ---
    },

    setupMultiSelect: function(baseId) {
        // ... (existing code remains the same) ...
        const btn = document.getElementById(`${baseId}Btn`);
        const dropdown = document.getElementById(`${baseId}Dropdown`);
        if (!btn || !dropdown) return;

        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            // Close other dropdowns first
            document.querySelectorAll('.multiselect-dropdown.show, .column-toggle-dropdown.show').forEach(d => {
                if (d.id !== dropdown.id) d.classList.remove('show');
            });
             // Close column dropdown if open
             const columnDropdown = document.getElementById('column-dropdown');
             if (columnDropdown) columnDropdown.classList.remove('show');

            dropdown.classList.toggle('show');
        });

        dropdown.addEventListener('change', (e) => {
            if (e.target.type === 'checkbox') {
                schedulingApp.utils.updateMultiSelectButtonText(baseId);
                schedulingApp.filters.filterGrid(); // Trigger filtering on change
            }
        });

        // Prevent dropdown closing on internal clicks
        dropdown.addEventListener('click', (e) => {
            e.stopPropagation();
        });
    }
};