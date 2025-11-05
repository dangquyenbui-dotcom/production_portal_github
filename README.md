# Production Portal

## 🌟 Overview

The Production Portal is a robust, enterprise-ready web application designed for a manufacturing environment. It provides a comprehensive suite of tools for production tracking, planning, and administration by interfacing directly with a live ERP database for read-only data and using its own local database for user-generated data.

Its core purpose is to bridge the gap between floor-level operations and high-level planning by providing a single, unified interface for:

* **Downtime Tracking:** An intuitive, tablet-friendly form for production staff to log downtime events against specific lines and ERP jobs.
* **Production Scheduling:** A powerful grid for planners to view open sales orders, see ERP-calculated component availability, and save their own production projections.
* **Material Requirements Planning (MRP):** A full-fledge MRP engine that calculates material shortfalls across all open orders, providing a dashboard for production priorities, a customer-centric summary, and a consolidated shortage report for purchasing.
* **Live Data Viewers:** Read-only, searchable interfaces for critical ERP data, including **Live Open Jobs**, **Bills of Materials (BOMs)**, and **Purchase Orders (POs)**.
* **Sales & Reporting:** Dashboards for customer sales analysis and a hub for operational reports like **Downtime Summaries**, **Shipment Forecasts**, and **Certificate of Compliance (CoC)** generation.
* **System Administration:** A complete admin panel for managing all local data, including facilities, lines, shifts, downtime categories, user access, and system auditing.

The application is built on a hybrid data architecture:
1.  **Local Database (ProductionDB):** A dedicated SQL Server database to store all application-specific data (users, sessions, downtime logs, admin configurations, scheduling projections, audit trails).
2.  **ERP Database:** A read-only `pyodbc` connection to the company's main ERP (e.g., Deacom) to pull live, real-time data on sales orders, inventory, jobs, BOMs, and POs.

Authentication is handled via **Active Directory**, with granular, role-based access control defined by AD security groups.

---

## 🛠️ Core Modules & Features

### Material Requirements Planning (MRP) Suite (`/mrp`)

This is the system's core planning engine. It analyzes all open sales orders against current ERP data (BOMs, On-Hand Inventory, QC-Pending Inventory, Open POs, and Open Jobs) to provide a complete production feasibility picture.

* **MRP Dashboard (`/mrp/`)**:
    * Calculates material availability sequentially, allocating available inventory based on the earliest sales order due dates.
    * Displays a filterable/sortable list of all open sales orders with a clear status:
        * `Ready to Ship`: Can be fulfilled from on-hand finished good stock.
        * `Pending QC`: Sufficient quantity is in inventory but awaiting QC approval.
        * `Job Created`: An ERP job already exists for this order.
        * `Partial Ship`: Can be partially fulfilled from stock, but production is needed for the rest.
        * `Full Production Ready`: All required components are available to produce the full amount.
        * `Partial Production Ready`: Some components are available, allowing for a partial production run.
        * `Critical Shortage`: One or more components are completely unavailable, blocking production.
    * Features expandable rows to show detailed component requirements, availability, allocation logic, and specific bottlenecks.
    * Includes Excel export of the current view.

* **MRP Customer Summary (`/mrp/summary`)**:
    * Provides a high-level MRP overview filtered by a specific customer.
    * Displays summary cards for On-Track, At-Risk, and Critical orders.
    * Lists all open orders for that customer, highlighting their status and primary bottleneck.

* **Purchasing Shortage Report (`/mrp/buyer-view`)**:
    * A consolidated, actionable report for the purchasing department.
    * Aggregates *all* component shortfalls from the entire MRP run into a single list.
    * Shows On-Hand, Open PO Qty, and Total Shortfall for each component.
    * Lists all affected Sales Orders and Customers for each shorted part.
    * Filterable by urgency (e.g., "Due within 15 days"), customer, and text search.
    * Includes Excel export.

### Production Scheduling (`/scheduling`)

* Displays a comprehensive grid of all open sales orders from the ERP, enriched with local data.
* Users with `Scheduling_Admin` permission can edit "No/Low Risk Qty" and "High Risk Qty" projections directly in the grid. All changes are saved to the local `ProductionDB`.
* **Summary Cards:** Provides a high-level financial overview, including:
    * `Shipped as [Month]`: Total value of shipments this month (clickable for Excel export).
    * `$ No/Low Risk Qty`: Total value of user-projected quantities.
    * `$ High Risk`: Total value of high-risk projected quantities.
    * `FG On Hand`: Value of finished goods, split into three date-based buckets (clickable for Excel export).
    * `Forecasting Shipment`: A "Likely" and "May Be" forecast based on projections and inventory.
* **Grid Features:**
    * Advanced multi-select filtering (Facility, SO Type, Due Date).
    * Single-select filtering (BU, Customer).
    * Persistent column visibility toggle (saves user's preferred columns to local storage).
    * Full sorting on all columns.
    * Validation highlighting (rows turn red if projections don't match Net Qty, with a "Fix" button).
    * Excel export of the current grid view.

### Downtime Tracking (`/downtime`)

* A tablet-optimized form for recording production downtime events.
* **Form Fields:**
    * Facility (filters Production Line)
    * Production Line (dynamically loads ERP jobs)
    * Time Range (auto-fills to the last 30 minutes)
    * Crew Size (stepper buttons for touch)
    * Job Number (Optional; dropdown of live ERP jobs for that line)
    * Shift (auto-detected or manually selected)
    * Main Category & Sub Category
    * Comments & Quick Notes
* **Live Feedback:**
    * Displays calculated duration automatically.
    * Shows a list of "Today's Downtime Entries" for the selected line *from all users*.
    * Allows users to edit or delete their *own* entries from this list.

### Live Open Jobs Viewer (`/jobs/open-jobs`)

* Provides a real-time view of all *open* production jobs from the ERP.
* Displays Job #, Part #, Customer, SO #, Required Qty, and Completed Qty.
* **Features:**
    * Filterable by Customer, Job, Part, and Sales Order.
    * Sortable on all columns.
    * Expandable rows show detailed component transactions (`dtfifo` and `dtfifo2`) aggregated by action (Issued, De-issue, Relieve Job, Finish Job).
    * Calculates and displays Yield Cost/Scrap and Yield Loss % for each component.
    * Optional "Live Update" toggle to automatically refresh data every 30 seconds.
    * Expanded/collapsed state of rows is preserved during live updates.

### ERP Data Viewers

* **BOM Viewer (`/bom`):** A read-only, searchable view of all active, latest-revision Bills of Materials from the ERP. Includes Excel export.
* **PO Viewer (`/po`):** A read-only, searchable view of all open Purchase Orders from the ERP. Includes Excel export.

### Sales & Reporting

* **Sales Analysis (`/sales/customer-analysis`):** A customer-centric dashboard. Users can select a customer to view KPIs (YTD Sales, Open Order Value), a sales trend chart, a top products chart, and tables of recent shipments and open orders.
* **Reports Hub (`/reports`):** A central dashboard for all reports.
    * **Downtime Summary:** Aggregated downtime analysis by Category and Line within a date range.
    * **Shipment Forecast:** Automated monthly forecast based on MRP results.
    * **Certificate of Compliance (CoC):** Generates a detailed component traceability and yield report for any given job number (open or closed), with a direct PDF export option.

### Admin Panel (`/admin`)

A secure area for configuring the application's local database and monitoring the system.
* **Facilities:** Manage manufacturing facilities (CRUD, Reactivate, View History).
* **Production Lines:** Manage lines within each facility (CRUD).
* **Production Capacity:** Define output capacity per shift for each line.
* **Downtime Categories:** Manage hierarchical downtime reason codes (CRUD, ReactGivate).
* **Shift Management:** Configure work shifts and schedules (CRUD, Reactivate).
* **User Management:** View user login history, detected AD groups, and activity stats.
* **Audit Log:** A filterable, chronological log of all changes made within the admin panel.
* **System Status:** A dashboard showing the connection status of the Local DB and Active Directory, plus a list of all active user sessions with the ability to "kick" a session.

### Core Application Features

* **Authentication:** Primary authentication via **Active Directory**. Includes a local fallback administrator (`production_portal_admin`) for emergency access.
* **Thread-Safe DB Connections:** All database connections (Local and ERP) are **thread-local**, preventing concurrency errors and ensuring stability under a multi-threaded server like Waitress.
* **Internationalization (i18n):** Full support for English (`en`) and Spanish (`es`) using Flask-Babel. User language preference is stored in their session and can be saved to their profile.
* **Dark/Light Mode:** User-selectable theme preference stored in browser local storage.
* **Single Session Enforcement:** Logging in automatically invalidates any other active session for that same user.
* **Click Prevention:** All dashboard and report hub links feature robust click-prevention logic to stop users from sending multiple requests for heavy pages.

---

## 🚀 Getting Started

### Prerequisites

* Python (3.8+ recommended)
* Microsoft SQL Server (for the local `ProductionDB`)
* Read-only access to the target ERP SQL Server database.
* **ODBC Drivers** installed on the server (e.g., "ODBC Driver 17 for SQL Server").
* Network access to an Active Directory domain controller (unless in `TEST_MODE`).

### Installation & Setup

1.  **Clone the Repository:**
    ```bash
    git clone <your-repository-url>
    cd production_portal_github
    ```

2.  **Set Up Environment Variables (`.env`):**
    * Copy `.env.template` to a new file named `.env` in the root directory.
    * **Crucially, edit `.env`** to fill in all your specific production details:
        * `SECRET_KEY`: **Generate a new, strong, random secret key.**
        * `AD_SERVER`, `AD_DOMAIN`, `AD_SERVICE_ACCOUNT`, `AD_SERVICE_PASSWORD`, `AD_BASE_DN`
        * `AD_ADMIN_GROUP`, `AD_USER_GROUP`, `AD_SCHEDULING_ADMIN_GROUP`, `AD_SCHEDULING_USER_GROUP`, `AD_PORTAL_ADMIN_GROUP` (must match your AD security groups)
        * `DB_SERVER`, `DB_NAME`, `DB_USERNAME`, `DB_PASSWORD` (for the local `ProductionDB`)
        * `ERP_DB_SERVER`, `ERP_DB_NAME`, `ERP_DB_USERNAME`, `ERP_DB_PASSWORD` (for the read-only ERP)
        * `ERP_DB_DRIVER` (e.g., `ODBC Driver 17 for SQL Server`)
        * Set `TEST_MODE=False` for production.

3.  **Create and Activate Virtual Environment:**
    ```bash
    # Create the virtual environment (named 'venv')
    python -m venv venv

    # Activate the environment
    # On Windows:
    .\venv\Scripts\activate
    # On macOS/Linux:
    # source venv/bin/activate
    ```

4.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

5.  **Database Initialization (`ProductionDB`):**
    * Ensure the `ProductionDB` database exists on your `DB_SERVER` instance.
    * Ensure the `DB_USERNAME` has `db_owner` (or equivalent) permissions on that database.
    * The application will automatically create all necessary tables (`Facilities`, `AuditLog`, `Sessions`, etc.) on its first run.

6.  **Run the Application (Production):**
    Use the provided `start_production_portal.bat` script (on Windows) or run Waitress directly:
    ```bash
    waitress-serve --host=0.0.0.0 --port=5000 --threads=10 --call app:create_app
    ```
    * Ensure your server's firewall allows incoming connections on port 5000.

7.  **Access in Browser:**
    Navigate to `http://<your-server-ip>:5000`.

---

## 🔐 Permissions Matrix

Access is controlled by Active Directory group membership. The local `production_portal_admin` user has full permissions.

| Feature / AD Group | `Downtime_Admin` | `Downtime_User` | `Scheduling_Admin` | `Scheduling_User` | `Portal_Admin` |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Downtime (Report)** | ✅ | ✅ | No | No | ✅ |
| **Downtime (Admin)** | ✅ | No | No | No | ✅ |
| **Scheduling (View)** | No | No | ✅ | ✅ | ✅ |
| **Scheduling (Edit)** | No | No | ✅ | No | ✅ |
| **MRP Dashboard** | No | No | ✅ | No | ✅ |
| **MRP Customer Summary**| No | No | ✅ | No | ✅ |
| **MRP Buyer View** | No | No | ✅ | ✅ | ✅ |
| **Sales Analysis** | No | No | ✅ | No | ✅ |
| **BOM Viewer** | ✅ | No | ✅ | ✅ | ✅ |
| **PO Viewer** | ✅ | No | ✅ | ✅ | ✅ |
| **Open Jobs Viewer** | ✅ | No | ✅ | ✅ | ✅ |
| **Reports Hub** | ✅ | No | ✅ | ✅ | ✅ |
| **Admin Panel** | ✅ | No | ✅ | No | ✅ |

---

## 🏗️ Technology Stack

* **Backend**: Python, Flask
* **WSGI Server**: Waitress
* **Database**: Microsoft SQL Server
* **Data Driver**: `pyodbc`
* **Authentication**: `ldap3` (for Active Directory)
* **Frontend**: Jinja2, Vanilla JavaScript, CSS
* **Internationalization**: Flask-Babel
* **Excel Export**: `openpyxl`
* **PDF Generation**: `reportlab`
* **Utilities**: `python-dotenv`, `Werkzeug`

---

## 📁 Project Structure

````

/production\_portal\_github/
│
├── app.py                  \# Flask application factory & runner
├── config.py               \# Configuration loader (reads .env)
├── requirements.txt        \# Python dependencies
├── .env                    \# Local environment variables (GITIGNORED)
├── .env.template           \# Template for .env file
├── README.md               \# This file
│
├── /auth/                  \# Authentication & Authorization
│   └── ad\_auth.py          \# AD logic, permission helpers, local admin
│
├── /database/              \# Data access layer
│   ├── connection.py       \# Local DB (ProductionDB) connection (thread-local)
│   ├── erp\_connection\_base.py \# ERP DB connection (thread-local)
│   ├── erp\_service.py      \# Facade for ERP queries
│   ├── mrp\_service.py      \# Core MRP calculation logic
│   ├── sales\_service.py    \# Sales analysis logic
│   ├── scheduling.py       \# Scheduling projection DB operations
│   ├── capacity.py         \# Production capacity DB operations
│   ├── downtimes.py        \# Downtime event DB operations
│   ├── facilities.py       \# Facilities DB operations
│   ├── ... (other db modules) ...
│   └── /erp\_queries/       \# Specific SQL queries for ERP
│       └── ... (query modules) ...
│
├── /routes/                \# Flask blueprints (controllers)
│   ├── main.py             \# Core routes (login, dashboard, logout, locale)
│   ├── downtime.py
│   ├── scheduling.py
│   ├── mrp.py
│   ├── jobs.py
│   ├── bom.py
│   ├── po.py
│   ├── sales.py
│   ├── /reports/           \# Combined reports blueprint package
│   │   ├── **init**.py
│   │   ├── hub.py
│   │   └── ... (other report routes) ...
│   └── /admin/             \# Admin panel blueprints
│       ├── panel.py
│       └── ... (other admin routes) ...
│
├── /static/                \# Frontend assets
│   ├── /css/
│   ├── /js/
│   └── /img/
│
├── /templates/             \# Jinja2 HTML templates
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   ├── /admin/
│   ├── /downtime/
│   ├── /scheduling/
│   ├── /mrp/
│   ├── /jobs/
│   └── /reports/
│
├── /translations/          \# Internationalization (i18n) files
│   ├── /en/LC\_MESSAGES/
│   └── /es/LC\_MESSAGES/
│   └── messages.pot        \# Translation template
│
├── /utils/                 \# Helper utilities
│   ├── helpers.py          \# General utilities
│   └── pdf\_generator.py    \# CoC PDF generation logic
│
└── start\_production\_portal.bat \# Production startup script

```
```
this is so cool
