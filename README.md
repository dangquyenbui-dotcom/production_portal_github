Okay, here is the updated `README.md` file reflecting the recent changes, including the corrected Certificate of Compliance (CoC) report logic.

````markdown
# Production Portal v2.7.1

## 🌟 Overview

The Production Portal is a robust, enterprise-ready web application designed for manufacturing and co-packaging environments, specifically tailored for WePackItAll. This portal provides a comprehensive suite of tools for:

* **Tracking Production Downtime:** An intuitive interface for recording downtime events on the production floor.
* **Managing Production Scheduling:** Viewing open ERP sales orders and projecting producible quantities based on risk assessment.
* **ERP Data Viewing:** Accessing read-only views of crucial ERP data including Bills of Materials (BOM), Purchase Orders (PO), and live open production job details.
* **Material Requirements Planning (MRP):** A powerful dashboard analyzing material availability against open orders to suggest production priorities and identify component shortages.
* **Sales Analysis:** Dashboards for reviewing customer performance, sales trends, and open order status.
* **Reporting:** Generating key operational reports like Downtime Summaries, Shipment Forecasts, and detailed Certificate of Compliance (CoC) reports per job.
* **System Administration:** Configuring core application settings like facilities, production lines, shifts, and user permissions.

The system utilizes a hybrid data architecture: it connects to a **read-only ERP database** (Deacom Cloud via `pyodbc`) for live production, inventory, sales, BOM, PO, and job data, while storing all user-generated data (downtime events, scheduling projections, audit logs, system configurations) in a separate, local **SQL Server database** (`ProductionDB`). User authentication is primarily handled via **Active Directory** (`wepackitall.local`), with a local fallback administrator account for emergencies.

**Status:** All core modules described are implemented and operational. Recent updates include corrections to the Certificate of Compliance report to accurately account for 'Un-finish Job' transactions from the ERP's `dtfifo2` table when calculating the total completed quantity.

---

## 🚀 Getting Started

### Prerequisites

* Python 3.10+
* Microsoft SQL Server (for the local `ProductionDB`)
* Read-only access to the target ERP SQL Server database (Deacom Cloud).
* Appropriate **ODBC Drivers** installed on the server running the application (e.g., "ODBC Driver 17 for SQL Server" or similar, as specified in `.env`).
* Access to the `wepackitall.local` Active Directory domain for user authentication (unless using `TEST_MODE=True` or the local admin).

### Installation & Setup

1.  **Clone the Repository:**
    ```bash
    git clone <your-repository-url>
    cd production_portal_github
    ```

2.  **Set Up Environment Variables (`.env`):**
    * Copy the `.env.template` file to a new file named `.env` in the project root.
    * **Crucially, update the variables within `.env`** with your specific production configuration details:
        * `SECRET_KEY`: **Generate a new, strong, random secret key.** The placeholder is insecure.
        * `AD_SERVER`, `AD_DOMAIN`, `AD_SERVICE_ACCOUNT`, `AD_SERVICE_PASSWORD`, `AD_BASE_DN`, `AD_*_GROUP` names for production AD.
        * `DB_SERVER`, `DB_NAME`, `DB_USERNAME`, `DB_PASSWORD` (or `DB_USE_WINDOWS_AUTH`) for the local `ProductionDB`.
        * `ERP_DB_SERVER`, `ERP_DB_NAME`, `ERP_DB_USERNAME`, `ERP_DB_PASSWORD`, `ERP_DB_PORT`, `ERP_DB_DRIVER` for the read-only ERP connection.
        * Ensure `TEST_MODE=False` for production.

3.  **Create and Activate Virtual Environment:**
    It is highly recommended to use a Python virtual environment.
    ```bash
    # Navigate to the project root directory
    cd path/to/production_portal_github

    # Create the virtual environment (named 'venv')
    python -m venv venv

    # Activate the environment
    # Windows PowerShell:
    .\venv\Scripts\Activate.ps1
    # Windows CMD:
    # .\venv\Scripts\activate.bat
    # macOS/Linux:
    # source venv/bin/activate
    ```

4.  **Install Dependencies:**
    With the virtual environment activated, install the required packages:
    ```bash
    pip install -r requirements.txt
    ```

5.  **Database Initialization (`ProductionDB`):**
    * Ensure the `ProductionDB` database exists on your `DB_SERVER` instance.
    * Verify the `DB_USERNAME` (or the service account if using Windows Auth) has permissions to connect, SELECT, INSERT, UPDATE, DELETE, and potentially CREATE/ALTER TABLE within that database.
    * The application will attempt to create necessary tables (`AuditLog`, `ActiveSessions`, `DowntimeCategories`, `Shifts`, `ProductionCapacity`, `ScheduleProjections`, `UserLogins`, `UserPreferences`, etc.) on its first run if they don't exist.

6.  **Run the Application (Production):**
    Use a production-ready WSGI server like Waitress (included in requirements). Ensure the virtual environment is active.
    ```bash
    waitress-serve --host=0.0.0.0 --port=5000 --call app:create_app
    ```
    *(Adjust host/port as needed. Ensure the server's firewall allows traffic on the specified port.)* You can also use the provided `start_production_portal.bat` script on Windows.

7.  **Access in Browser:**
    Navigate to the server's IP address or hostname and the specified port (e.g., `http://your_server_ip:5000`). Log in using your Active Directory credentials. Access requires membership in specific AD groups defined in your `.env` file.

---

## 🛠️ Core Modules & Features

### Material Requirements Planning (MRP) Suite (`/mrp`)

Analyzes open sales orders against ERP data (BOMs, Inventory, POs, Jobs) to predict production feasibility and highlight shortages.

* **MRP Dashboard (`/mrp/`)**:
    * Calculates material availability considering on-hand, pending QC, and open POs against BOM requirements.
    * Allocates available inventory sequentially based on sales order due dates.
    * Displays filterable/sortable list of open SOs with statuses: `Ready to Ship`, `Pending QC`, `Job Created`, `Partial Ship`, `Full Production Ready`, `Partial Production Ready`, `Critical Shortage`.
    * Expandable component details show requirements, availability, allocation logic, and specific shortfalls.
    * Excel export of the current view.
* **MRP Customer Summary (`/mrp/summary`)**:
    * Provides an MRP overview filtered by a specific customer.
    * Summary cards show counts of On-Track, At-Risk, and Critical orders.
    * Filterable list showing order status and specific bottleneck components.
* **Purchasing Shortage Report (`/mrp/buyer-view`)**:
    * Consolidates all component shortfalls identified by the MRP run.
    * Lists shortages showing On-Hand, Open PO Qty, Total Shortfall, affected Customers/SOs, and earliest Due Date.
    * Filterable by urgency (due date proximity), customer, and text search. Excel export available.

### Production Scheduling (`/scheduling`)

* Displays open sales orders from ERP merged with user-editable production projections.
* Users (with permission) can input "No/Low Risk" and "High Risk" quantities per SO line, saved locally.
* Calculates projected dollar values based on user input and ERP unit prices.
* Features summary cards: FG On Hand Value (split by date buckets), Shipped Value (Current Month), Total Projected Values.
* Grid includes multi-select filtering (Facility, SO Type, Due Date), single-select filtering (BU, Customer), column visibility control (persisted in local storage), sorting, and validation highlighting discrepancies between Net Qty and projections.
* Excel export of the current view.

### Downtime Tracking (`/downtime`)

* Tablet-optimized form for recording production downtime.
* Inputs: Facility, Line, Start/End Time (auto-fills last 30 mins), Crew Size, Category (Main/Sub), optional ERP Job (dynamically loaded via API based on Line/Facility), Shift (auto-detected), Comments.
* Displays duration automatically. Includes "Quick Notes" buttons.
* Shows a list of today's entries for the selected line, allowing editing/deleting of own entries.
* Data saved to the local `ProductionDB`.

### Live Open Jobs Viewer (`/jobs/open-jobs`)

* Real-time view of *open* production jobs from ERP.
* Displays Job #, Part #, Customer, SO #, Required Qty, Completed Qty.
* Filterable by Customer, Job, Part, SO; Sortable columns.
* Expandable rows show detailed component transactions (`dtfifo`, `dtfifo2`) aggregated by action (Issued, De-issue, Relieve Job, Finish Job) and calculates Yield Cost/Scrap and Yield Loss %.
* Optional live auto-refresh toggle (fetches data via `/jobs/api/open-jobs-data`).

### ERP Data Viewers

* **BOM Viewer (`/bom`)**: Read-only view of active, latest-revision Bills of Materials from ERP. Searchable; Excel export.
* **PO Viewer (`/po`)**: Read-only view of open Purchase Orders from ERP. Searchable; Excel export.

### Sales Analysis (`/sales/customer-analysis`)

* Customer-centric dashboard.
* Select customer to view KPIs (YTD Sales, Open Order Value, etc.), Sales Trend chart, Top Products chart (by open value), Recent Shipments table, and Open Orders table.

### Reporting Suite (`/reports`)

Central hub linking to various reports.

* **Downtime Summary (`/reports/downtime-summary`)**: Aggregated downtime analysis by Category and Line within a selected date range/facility/line. Includes charts and raw data table.
* **Shipment Forecast (`/reports/shipment-forecast`)**: Automated monthly forecast based on MRP results, categorizing orders into "Likely" and "At-Risk" based on material status and lead time.
* **Certificate of Compliance (CoC) (`/reports/coc`)**: Generates a detailed report for any specified Job Number (open or closed) showing header info and component lot traceability, usage, and yield calculations. Correctly calculates completed quantity by accounting for 'Finish Job' (from `dtfifo`) and 'Un-finish Job' (from `dtfifo2`) transactions. Includes PDF export functionality (`/reports/coc/pdf`) using ReportLab.

### Admin Panel (`/admin`)

Restricted area for system configuration.

* **Facilities:** Manage locations (CRUD, History).
* **Production Lines:** Manage lines within facilities (CRUD).
* **Production Capacity:** Define output per shift per line (CRUD).
* **Downtime Categories:** Manage hierarchical reason codes (CRUD, Reactivate, Color, Notifications).
* **Shift Management:** Configure work shifts (CRUD, Reactivate).
* **User Management:** View user login history, detected AD groups, activity stats (CRUD for permissions planned but not shown in current files).
* **Audit Log:** Filterable view of all system changes logged in `AuditLog` table.

### Other Features

* **Authentication:** Primarily Active Directory; includes a local admin fallback (`production_portal_admin`).
* **Internationalization (i18n):** Supports English (en_US) and Spanish (es_MX) using Flask-Babel. User language preference stored in session and optionally in `UserPreferences` table. Language can be switched via navbar links.
* **Dark/Light Mode:** User-selectable theme preference stored in local storage, applies dynamically.
* **Single Session Enforcement:** Invalidates previous sessions upon new login for the same user.
* **Session Validation:** Decorator (`@validate_session`) checks session validity on protected routes.

---

## 💻 Technology Stack

* **Backend**: Python 3, Flask
* **WSGI Server**: Waitress
* **Database ORM/Driver**: `pyodbc` for both local SQL Server and ERP SQL Server connections
* **Authentication**: `ldap3` for Active Directory communication
* **Frontend**: Jinja2 Templating, HTML, CSS, Vanilla JavaScript (no major JS framework)
* **Internationalization**: Flask-Babel, Babel
* **Excel Export**: `openpyxl`
* **PDF Generation**: `reportlab`
* **Environment Variables**: `python-dotenv`
* **Password Hashing:** `Werkzeug` (for local admin fallback)

---

## 🏗️ Architecture

* **Flask Application Factory:** Uses `create_app()` pattern in `app.py`.
* **Blueprints:** Modular structure using Flask Blueprints for different sections (main, downtime, scheduling, admin, etc.).
* **Database Layer:**
    * Separate connection handlers for local `ProductionDB` (`database/connection.py`) and read-only ERP (`database/erp_connection_base.py`).
    * Service layer (`database/erp_service.py`) acts as a facade for ERP queries, delegating to specialized query modules (`database/erp_queries/*`).
    * Dedicated modules for local DB table operations (e.g., `database/downtimes.py`, `database/scheduling.py`).
* **Authentication:** Handled in the `auth` package, interacting with AD via `ldap3` or checking local hash. Permission checks (`require_admin`, `require_scheduling_user`, etc.) are used in routes and templates.
* **Frontend:** Server-side rendering with Jinja2; client-side interactions via Vanilla JavaScript, including AJAX calls for dynamic data loading (e.g., ERP jobs, line lists) and updates (e.g., scheduling projections).

---

## 📁 Project Structure

```text
/production_portal_github/
│
├── app.py                  # Flask application factory & runner
├── config.py               # Configuration loader (reads .env)
├── requirements.txt        # Python dependencies
├── .env                    # Local environment variables (GITIGNORED)
├── .env.template           # Template for .env file
├── README.md               # This file
│
├── /auth/                  # Authentication & Authorization
│   ├── __init__.py
│   └── ad_auth.py          # AD logic, permission helpers, local admin
│
├── /database/              # Data access layer
│   ├── __init__.py         # Exports DB instances & service getters
│   ├── connection.py       # Local DB (ProductionDB) connection
│   ├── erp_connection_base.py # Base ERP DB connection (pyodbc)
│   ├── erp_service.py      # Facade for ERP queries
│   ├── mrp_service.py      # Core MRP calculation logic
│   ├── sales_service.py    # Sales analysis logic
│   ├── scheduling.py       # Scheduling projection DB operations
│   ├── capacity.py         # Production capacity DB operations
│   ├── downtimes.py        # Downtime event DB operations
│   ├── facilities.py       # Facilities DB operations
│   ├── production_lines.py # Production Lines DB operations
│   ├── categories.py       # Downtime Categories DB operations
│   ├── shifts.py           # Shift definitions DB operations
│   ├── users.py            # User login/preferences DB operations
│   ├── sessions.py         # Active session management DB operations
│   ├── audit.py            # Audit log DB operations
│   ├── reports.py          # Report generation DB queries
│   └── /erp_queries/       # Specific SQL queries for ERP
│       ├── __init__.py
│       ├── job_queries.py
│       ├── inventory_queries.py
│       ├── po_queries.py
│       ├── qc_queries.py
│       ├── bom_queries.py
│       ├── sales_queries.py
│       └── coc_queries.py   # CoC Report specific queries
│
├── /routes/                # Flask blueprints (controllers)
│   ├── __init__.py
│   ├── main.py             # Core routes (login, dashboard, logout, locale)
│   ├── downtime.py
│   ├── scheduling.py
│   ├── mrp.py
│   ├── jobs.py
│   ├── bom.py
│   ├── po.py
│   ├── sales.py
│   ├── reports/            # Combined reports blueprint package
│   │   ├── __init__.py     # Registers report sub-blueprints
│   │   ├── hub.py          # Reports hub route
│   │   ├── downtime_summary.py
│   │   ├── shipment_forecast.py
│   │   └── coc.py          # CoC report routes
│   ├── erp_routes.py       # API for ERP data (e.g., jobs for downtime form)
│   └── /admin/             # Admin panel blueprints
│       ├── __init__.py
│       ├── panel.py
│       ├── facilities.py
│       ├── production_lines.py
│       ├── capacity.py
│       ├── categories.py
│       ├── shifts.py
│       ├── users.py
│       └── audit.py
│
├── /static/                # Frontend assets (CSS, JS, Images)
│   ├── /css/
│   ├── /js/
│   └── /img/
│
├── /templates/             # Jinja2 HTML templates
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   ├── status.html
│   ├── /admin/
│   ├── /downtime/
│   ├── /scheduling/
│   ├── /mrp/
│   ├── /jobs/
│   ├── /bom/
│   ├── /po/
│   ├── /sales/
│   ├── /reports/
│   └── /components/        # Reusable template snippets
│
├── /translations/          # Internationalization (i18n) files
│   ├── /en/LC_MESSAGES/    # English (.po, .mo)
│   └── /es/LC_MESSAGES/    # Spanish (.po, .mo)
│   └── messages.pot        # Translation template
│
├── /utils/                 # Helper utilities
│   ├── __init__.py
│   ├── helpers.py          # General utilities (client info, formatting)
│   ├── validators.py       # Input validation
│   └── pdf_generator.py    # CoC PDF generation logic
│
├── babel.cfg               # Babel config for string extraction
├── start_production_portal.bat # Example startup script for Windows
└── .gitignore              # Files/folders ignored by Git
````

-----

## ⚙️ Configuration (`.env`)

Key settings managed via the `.env` file:

  * `SECRET_KEY`: **Must be set to a unique, random string for security.**
  * `SESSION_HOURS`: Duration for user sessions.
  * `TEST_MODE`: `True` bypasses AD for development/testing, `False` uses live AD.
  * `AD_*`: Configuration for Active Directory connection and group names. **Includes `AD_PORTAL_ADMIN_GROUP`**.
  * `DB_*`: Connection details for the local `ProductionDB` SQL Server.
  * `ERP_*`: Connection details for the read-only ERP SQL Server.
  * `SMTP_*`, `EMAIL_*`: Optional settings for email notifications (used by Categories).

-----

## 🔐 Permissions Matrix

Access is controlled by Active Directory group membership. A local user `production_portal_admin` exists as a fallback with full permissions.

| AD Group/Module               | Admin Panel | Sched (View) | Sched (Update) | BOM | PO  | MRP | Sales | Downtime | Reports | Jobs |
| :---------------------------- | :---------- | :----------- | :------------- | :-: | :-: | :-: | :-: | :------- | :------ | :--: |
| `DowntimeTracker_Admin`       | Yes         | No           | No             | Yes | Yes | No  | No  | Yes      | Yes     | Yes  |
| `DowntimeTracker_User`        | No          | No           | No             | No  | No  | No  | No  | Yes      | No      | No   |
| `Scheduling_Admin`            | Yes         | Yes          | Yes            | Yes | Yes | Yes | Yes | No       | Yes     | Yes  |
| `Scheduling_User`             | No          | Yes          | No             | Yes | Yes | Yes | Yes | No       | Yes     | Yes  |
| `Production_Portal_Admin`     | Yes         | Yes          | Yes            | Yes | Yes | Yes | Yes | Yes      | Yes     | Yes  |
| `production_portal_admin` (local) | Yes     | Yes          | Yes            | Yes | Yes | Yes | Yes | Yes      | Yes     | Yes  |

*(Note: "Reports" access grants entry to the `/reports/` hub and individual reports based on the matrix logic. "Jobs" refers to the Live Open Jobs Viewer.)*

-----

## 🌍 Internationalization (i18n)

  * **Supported Languages:** English (US `en`), Spanish (MX `es`).
  * **Implementation:** Uses Flask-Babel. Translatable strings are extracted using `babel.cfg` into `messages.pot`, compiled into `.mo` files. User language preference is stored in the session and can be saved to the `UserPreferences` table. Language can be switched via navbar links.

-----

## 🏭 Running for Production

  * **WSGI Server:** Use Waitress (or Gunicorn/uWSGI). **Do not use `flask run` or `python app.py` with `debug=True`**.
    ```bash
    waitress-serve --host=0.0.0.0 --port=5000 --call app:create_app
    ```
    *(See `start_production_portal.bat` for a Windows example.)*
  * **Configuration:** Ensure `TEST_MODE=False` and a strong `SECRET_KEY` are set in `.env`. Verify all DB/ERP/AD settings point to production resources.
  * **HTTPS:** Strongly recommended. Set up a reverse proxy (Nginx, Apache, IIS) to handle SSL termination.
  * **Logging:** Configure proper file-based logging for monitoring.
  * **Virtual Environment:** Always run within the activated project virtual environment.

-----

## 📄 License

(Specify your project's license here, e.g., MIT, GPL, Proprietary)

-----

## 🙏 Acknowledgements

  * Flask
  * Waitress
  * pyodbc
  * ldap3
  * Flask-Babel
  * openpyxl
  * reportlab
  * python-dotenv
  * Werkzeug

-----

```
```