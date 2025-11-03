// static/js/scheduling_columns.js

var schedulingApp = schedulingApp || {};

schedulingApp.columns = {
    COLUMNS_CONFIG_KEY: 'schedulingColumnConfig',

    initializeColumnToggle: function() {
        const dropdown = document.getElementById('column-dropdown');
        const headers = document.querySelectorAll('.grid-table thead th');
        if (!dropdown || headers.length === 0) return;

        let savedConfig = JSON.parse(localStorage.getItem(schedulingApp.columns.COLUMNS_CONFIG_KEY));
        
        // --- MODIFIED: Removed 'SO Type' from defaultHidden ---
        const defaultHidden = ['Ord Qty - (00) Level', 'Total Shipped Qty', 'Produced Qty', 'ERP Can Make', 'ERP Low Risk', 'ERP High Risk', 'Unit Price', 'Qty Per UoM', 'Sales Rep'];
        // --- END MODIFICATION ---

        if (!savedConfig) {
            savedConfig = {};
            headers.forEach(th => {
                const id = th.dataset.columnId;
                if (id) {
                    savedConfig[id] = !defaultHidden.includes(id);
                }
            });
            localStorage.setItem(schedulingApp.columns.COLUMNS_CONFIG_KEY, JSON.stringify(savedConfig));
        }

        // Ensure all current headers are in the config
        headers.forEach(th => {
            const id = th.dataset.columnId;
            if (id && !(id in savedConfig)) {
                savedConfig[id] = !defaultHidden.includes(id);
            }
        });

        dropdown.innerHTML = ''; // Clear previous options
        headers.forEach(th => {
            const id = th.dataset.columnId;
            if (id) {
                const isVisible = savedConfig[id] !== false;
                const label = document.createElement('label');
                label.innerHTML = `<input type="checkbox" data-column-id="${id}" ${isVisible ? 'checked' : ''}> ${id}`;
                dropdown.appendChild(label);
                label.querySelector('input').addEventListener('change', schedulingApp.columns.handleColumnToggle);
            }
        });

        schedulingApp.columns.applyColumnVisibility(savedConfig);

        const columnsBtn = document.getElementById('columnsBtn');
        columnsBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            schedulingApp.utils.closeAllMultiSelectDropdowns(); // Close other dropdowns
            dropdown.classList.toggle('show');
        });

        // Prevent dropdown close on inside click
        dropdown.addEventListener('click', (e) => {
            e.stopPropagation();
        });

        // Close on outside click (handled globally in init.js)
    },

    handleColumnToggle: function(e) {
        const columnId = e.target.dataset.columnId;
        const isVisible = e.target.checked;
        let savedConfig = JSON.parse(localStorage.getItem(schedulingApp.columns.COLUMNS_CONFIG_KEY)) || {};
        savedConfig[columnId] = isVisible;
        localStorage.setItem(schedulingApp.columns.COLUMNS_CONFIG_KEY, JSON.stringify(savedConfig));
        schedulingApp.columns.applyColumnVisibility(savedConfig);
    },

    applyColumnVisibility: function(config) {
        const table = document.querySelector('.grid-table');
        if (!table) return;
        const headers = Array.from(table.querySelectorAll('thead th'));

        for (const columnId in config) {
            const isVisible = config[columnId];
            const headerIndex = headers.findIndex(th => th.dataset.columnId === columnId);

            if (headerIndex > -1) {
                const displayStyle = isVisible ? '' : 'none';
                const headerCell = table.querySelector(`th[data-column-id="${columnId}"]`);
                if (headerCell) headerCell.style.display = displayStyle;

                table.querySelectorAll(`tbody tr`).forEach(row => {
                    if (row.cells[headerIndex]) {
                        row.cells[headerIndex].style.display = displayStyle;
                    }
                });
            }
        }
    }
};