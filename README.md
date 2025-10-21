# Production Portal: Downtime Tracker, Scheduling & Reporting

## Overview

A robust, enterprise-ready web application designed for manufacturing and co-packaging environments. This portal provides a comprehensive suite of tools for **tracking production downtime**, managing **production scheduling**, viewing critical ERP data like **Bills of Materials (BOM)** and **Purchase Orders (PO)**, generating reports including the **Certificate of Compliance (CoC)**, analyzing **sales data**, leveraging a powerful **Material Requirements Planning (MRP)** dashboard, and viewing **live open job data**.

The system utilizes a hybrid data architecture: it connects to a **read-only ERP database** (via `pyodbc`) for live production, inventory, sales, and material data, while storing all user-generated data—such as downtime events, scheduling projections, and system configurations—in a separate, local SQL Server database (`ProductionDB`). User authentication is handled via **Active Directory**.

**Current Version:** 2.7.0 (Reflects permission matrix, consolidated reports hub)
**Status:** **All core modules are complete and operational.**

-----

## 🚀 Getting Started

### Prerequisites

* Python 3.10+
* Microsoft SQL Server (for `ProductionDB`)
* Access to the target ERP SQL Server database.
* Required ODBC Drivers installed (e.g., ODBC Driver 17/18 for SQL Server)
* Access to an Active Directory domain (for production authentication).

### Installation & Setup

1.  **Clone the Repository:**
    ```bash
    git clone <your-repository-url>
    cd production_portal_github
    ```

2.  **Set Up Environment Variables:**
    Copy `.env.template` to a new file named `.env` in the project root. Update the variables within `.env` with your specific configuration details (database credentials, AD settings, ERP connection details, secret key, etc.).

3.  **Install Dependencies:**
    It is highly recommended to use a virtual environment.
    ```bash
    python -m venv venv
    # Activate the environment (Windows example):
    .\venv\Scripts\activate
    # Or (macOS/Linux):
    # source venv/bin/activate

    pip install -r requirements.txt
    ```
    Ensure necessary ODBC drivers for SQL Server are installed on the system running the application.

4.  **Database Initialization:**
    The application will attempt to create necessary tables in `ProductionDB` on first run if they don't exist (e.g., `AuditLog`, `ActiveSessions`, `DowntimeCategories`, `Shifts`, `ProductionCapacity`, `ScheduleProjections`, `UserPermissions`). Ensure the configured database user has `CREATE TABLE` and `ALTER TABLE` permissions initially.

5.  **Run the Application:**
    ```bash
    python app.py
    ```
    The application will start, typically accessible on `http://localhost:5000` and potentially a network IP address.

6.  **Access in Browser:**
    Navigate to the URL provided in the terminal. Log in using your Active Directory credentials. Access requires membership in specific AD groups defined in your `.env` file.

-----

## 🔐 Permissions Matrix

Access to different modules is controlled by Active Directory group membership:

| AD Group/Module               | Admin Panel | Scheduling (View Only) | Scheduling (Update) | BOM Viewer | PO Viewer | MRP Suggestions | Customer Analysis | Report Downtime | View Reports |
| :---------------------------- | :---------- | :--------------------- | :------------------ | :--------- | :-------- | :-------------- | :---------------- | :-------------- | :----------- |
| `DowntimeTracker_Admin`       | Yes         | No                     | No                  | Yes        | Yes       | No              | No                | Yes             | Yes          |
| `DowntimeTracker_User`        | No          | No                     | No                  | No         | No        | No              | No                | Yes             | No           |
| `Scheduling_Admin`            | Yes         | Yes                    | Yes                 | Yes        | Yes       | Yes             | Yes               | No              | Yes          |
| `Scheduling_User`             | No          | Yes                    | No                  | Yes        | Yes       | Yes             | Yes               | No              | Yes          |
| `Production_Portal_Admin`     | Yes         | Yes                    | Yes                 | Yes        | Yes       | Yes             | Yes               | Yes             | Yes          |
| `production_portal_admin` (local) | Yes     | Yes                    | Yes                 | Yes        | Yes       | Yes             | Yes               | Yes             | Yes          |

*Note: The `production_portal_admin` user is a local fallback and has full permissions.*
*Note: "View Reports" includes access to the Reports Hub page and specific reports like Downtime Summary, Shipment Forecast, CoC, Open Jobs, MRP Customer Summary, and Purchasing Shortage Report, subject to the individual report's data access needs.*

-----

## 🎯 Core Modules

### ✅ Material Requirements Planning (MRP) Suite

A powerful planning tool analyzing open sales orders against ERP data (BOMs, Inventory, POs, Jobs). Access generally requires Scheduling Admin or Portal Admin rights.

#### 1\. MRP Dashboard (`/mrp/`)

* **Logic:** Sorts open SOs by due date, allocates available Finished Goods (FG) inventory, then calculates production feasibility based on component availability (On-Hand Approved + Pending QC + Open POs), considering BOM requirements and scrap/overage. Uses a two-pass component check to determine the true bottleneck and allocates inventory sequentially.
* **Features:** Displays all open SOs, filterable by BU, Customer, FG, Due Date, and Status. Provides statuses like "Ready to Ship", "Pending QC", "Job Created", "Partial Ship", "Full/Partial Production Ready", "Critical Shortage". Includes expandable component details showing allocation, requirements, and shortfalls. Data refresh and Excel export available.
* **Access:** `Scheduling_Admin`, `Production_Portal_Admin`.

#### 2\. MRP Customer Summary (`/mrp/summary`)

* **Purpose:** Provides a focused view of MRP results filtered by a selected customer. Moved to Reports Hub.
* **Features:** Displays summary cards (Total, On-Track, At-Risk, Critical Orders) and a filterable list of the customer's orders with their status and bottleneck details.
* **Access:** `Scheduling_Admin`, `Production_Portal_Admin` (via Reports Hub).

#### 3\. Purchasing Shortage Report (`/mrp/buyer-view`)

* **Purpose:** Consolidates all component shortfalls identified by the MRP run into a single view for purchasing. Moved to Reports Hub.
* **Features:** Lists components with shortfalls, showing On-Hand, Open PO Qty, Total Shortfall, affected Customers/SOs, and earliest required Due Date. Filterable by urgency (due date proximity), customer, and text search. Includes Excel export.
* **Access:** `Scheduling_Admin`, `Scheduling_User`, `Production_Portal_Admin` (via Reports Hub).

### ✅ Production Scheduling Module (`/scheduling/`)

* **Purpose:** View open sales orders from ERP and input/save user projections for "No/Low Risk" and "High Risk" producible quantities.
* **Features:** Displays ERP data merged with local projections. Includes summary cards for FG On Hand value (split by date buckets), Shipped Value (Current Month), and Total Projected Values. Grid features filtering (Facility, BU, SO Type, Customer, Due Date), sorting, column visibility toggle, and inline editing of projection cells (for authorized users). Data refresh and Excel export available.
* **Access (View):** `Scheduling_Admin`, `Scheduling_User`, `Production_Portal_Admin`.
* **Access (Update):** `Scheduling_Admin`, `Production_Portal_Admin`.

### ✅ Downtime Tracking Module (`/downtime`)

* **Purpose:** Tablet-optimized interface for recording production downtime events.
* **Features:** Select Facility, Line, Time Range, Crew Size, Downtime Category (Main/Sub), optional ERP Job association, Shift (auto-detected or manual), and Comments. Includes "Quick Notes" buttons. Displays a list of today's entries for the selected line. Allows editing and deleting user's own entries. ERP job details are fetched live via API based on Facility/Line selection.
* **Access:** `DowntimeTracker_Admin`, `DowntimeTracker_User`, `Production_Portal_Admin`.

### ✅ Live Open Jobs Viewer (`/jobs/open-jobs`)

* **Purpose:** Real-time view of open production jobs from the ERP. Moved to Reports Hub.
* **Features:** Displays Job #, Part #, Customer, SO #, Required Qty, Completed Qty. Filterable by Customer, Job, Part, SO. Sortable columns. Expandable rows show component transaction details: Issued Inventory, De-issue, Relieve Job, calculated Yield Cost/Scrap, and Yield Loss %. Optional live auto-refresh via toggle.
* **Access:** `DowntimeTracker_Admin`, `Scheduling_Admin`, `Scheduling_User`, `Production_Portal_Admin` (via Reports Hub).

### ✅ BOM & PO Viewers

* **BOM Viewer (`/bom/`)**: Read-only interface to browse active, latest-revision Bill of Materials from ERP. Searchable by Parent Part, Component Part, or Description. Includes Excel export.
* **PO Viewer (`/po/`)**: Read-only interface to view open Purchase Orders from ERP. Searchable by PO #, Part #, Description, Vendor. Includes Excel export.
* **Access:** `DowntimeTracker_Admin`, `Scheduling_Admin`, `Scheduling_User`, `Production_Portal_Admin`.

### ✅ Sales Analysis Module (`/sales/customer-analysis`)

* **Purpose:** Provides a dashboard for analyzing sales performance by customer.
* **Features:** Select a customer to view KPIs (YTD Sales, Open Order Value, Total Open Orders, Avg. Open Order Value), charts for Sales Trends and Top Products (by Open Order Value), and tables for Recent Shipments and detailed Open Orders.
* **Access:** `Scheduling_Admin`, `Production_Portal_Admin`.

### ✅ Reporting Suite (`/reports/`)

Accessible via a central hub (`/reports/hub`).

* **Downtime Summary (`/reports/downtime-summary`)**: Analyzes downtime duration by Category and Line within a selected date range/facility/line. Includes charts and raw event data.
* **Shipment Forecast (`/reports/shipment-forecast`)**: Automated monthly forecast based on MRP results, categorizing orders into "Likely to Ship" and "At-Risk/Partial" based on material status and a 2-day lead time assumption.
* **Certificate of Compliance (CoC) (`/reports/coc`)**: Generates a report for *any* specified Job Number (open or closed) showing header info (Part, Customer, SO, Required/Completed Qty) and detailed component usage, tracking lots from "Starting Lot Qty" through "Packaged Qty" and "Ending Inventory" to calculate "Yield Cost/Scrap" and "Yield Loss %". Includes PDF export functionality.
* **(Moved)** **Open Jobs**: See Live Open Jobs Viewer above.
* **(Moved)** **MRP Customer Summary**: See MRP Suite above.
* **(Moved)** **Purchasing Shortage Report**: See MRP Suite above.
* **Access:** `DowntimeTracker_Admin`, `Scheduling_Admin`, `Scheduling_User`, `Production_Portal_Admin`. *Note: MRP Customer Summary requires Scheduling Admin or Portal Admin.*

### ✅ Admin Panel (`/admin/`)

Role-restricted area for system configuration and monitoring. Accessible via cards on the main admin page.

* **Facilities (`/admin/facilities`)**: Manage manufacturing locations (CRUD operations). Includes viewing change history.
* **Production Lines (`/admin/lines`)**: Configure lines within facilities (CRUD operations). Filterable view.
* **Production Capacity (`/admin/capacity`)**: Define output capacity per shift for each line (Upsert/Delete).
* **Downtime Categories (`/admin/categories`)**: Manage hierarchical downtime reason codes (CRUD + Reactivate). Includes color coding and notification flags.
* **Shift Management (`/admin/shifts`)**: Configure work shift timings (CRUD + Reactivate). Calculates duration and handles overnight shifts.
* **User Management (`/admin/users`)**: View user login history, access levels, activity statistics, and recent logins. Includes search and CSV export.
* **Permissions Management (`/admin/permissions`)**: _Portal Admins only._ Grant specific overrides to user permissions beyond AD group defaults.
* **Audit Log (`/admin/audit-log`)**: View a filterable history of all changes made to key system data (Facilities, Lines, Categories, Shifts, Downtimes, Logins, Permissions).
* **Access:** `DowntimeTracker_Admin`, `Scheduling_Admin`, `Production_Portal_Admin`. *(Permissions Management is restricted further)*.

### ✅ Internationalization (i18n)

* **Languages:** Supports English (US) and Spanish (MX).
* **Implementation:** Uses Flask-Babel with `.po` and `.mo` files located in the `/translations` directory. Language selection is persisted per user.

### ✅ Other Features

* **Dark/Light Mode:** User-selectable theme preference stored in local storage.
* **Single Session Enforcement:** Logs out previous sessions when a user logs in from a new location.
* **Session Validation:** Decorator (`@validate_session`) ensures session validity on relevant requests.

-----

## 🏗️ Architecture

### Technology Stack

* **Backend**: Python 3, Flask
* **Database**:
    * **Application DB**: Microsoft SQL Server (via `pyodbc`)
    * **ERP Connection**: Read-only to ERP SQL Server (via `pyodbc`)
* **Authentication**: Active Directory (via `ldap3`)
* **Frontend**: Jinja2, HTML, CSS, JavaScript (no heavy framework)
* **Internationalization**: Flask-Babel, Babel
* **Excel Export**: `openpyxl`
* **PDF Generation**: `reportlab`
* **Environment**: `python-dotenv`

### Project Structure (Highlights)

````

/production\_portal\_github/
│
├── app.py                  \# Main Flask application factory & runner
├── config.py               \# Configuration loader (reads .env)
├── requirements.txt        \# Python dependencies
├── .env                    \# Local environment variables (GITIGNORED)
├── .env.template           \# Template for .env file
├── README.md               \# This file
│
├── /auth/                  \# Authentication logic
│   ├── **init**.py  
│   └── ad\_auth.py          \# Active Directory authentication functions
│
├── /database/              \# Data access layer
│   ├── **init**.py         \# Exports DB instances and service getters
│   ├── connection.py       \# Local DB (ProductionDB) connection handler
│   ├── erp\_connection\_base.py \# Base ERP DB connection (raw pyodbc)
│   ├── erp\_service.py      \# Facade for ERP queries, uses erp\_queries modules
│   ├── mrp\_service.py      \# Core MRP calculation logic
│   ├── sales\_service.py    \# Sales analysis logic
│   ├── scheduling.py       \# Scheduling projection DB operations
│   ├── capacity.py         \# Production capacity DB operations
│   ├── downtimes.py        \# Downtime event DB operations
│   ├── facilities.py       \# Facilities DB operations
│   ├── production\_lines.py \# Production Lines DB operations
│   ├── categories.py       \# Downtime Categories DB operations
│   ├── shifts.py           \# Shift definitions DB operations
│   ├── users.py            \# User login/preferences DB operations
│   ├── sessions.py         \# Active session management DB operations
│   ├── audit.py            \# Audit log DB operations
│   ├── permissions.py      \# User-specific permissions override DB operations
│   └── /erp\_queries/       \# Specific SQL queries for ERP
│       ├── **init**.py  
│       ├── job\_queries.py
│       ├── coc\_queries.py  \# CoC Report specific queries
│       ├── inventory\_queries.py
│       ├── po\_queries.py  
│       ├── qc\_queries.py  
│       ├── bom\_queries.py
│       └── sales\_queries.py
│
├── /routes/                \# Flask blueprints defining application routes
│   ├── **init**.py  
│   ├── main.py             \# Core routes (login, dashboard, logout)
│   ├── downtime.py  
│   ├── scheduling.py  
│   ├── mrp.py  
│   ├── jobs.py  
│   ├── bom.py  
│   ├── po.py  
│   ├── sales.py  
│   ├── reports.py          \# Hub, Downtime Summary, Forecast, CoC routes
│   ├── erp\_routes.py       \# API routes for ERP data (e.g., jobs for downtime)
│   └── /admin/             \# Admin panel routes
│       ├── **init**.py  
│       ├── panel.py  
│       ├── facilities.py  
│       ├── production\_lines.py
│       ├── capacity.py  
│       ├── categories.py  
│       ├── shifts.py  
│       ├── users.py  
│       ├── permissions.py  \# User Permissions override routes
│       └── audit.py  
│
├── /static/                \# Frontend assets
│   ├── /css/               \# CSS files (base.css, admin.css, etc.)
│   ├── /js/                \# JavaScript files (common.js, theme.js, module-specific JS)
│   └── /img/               \# Images and logos
│
├── /templates/             \# Jinja2 HTML templates
│   ├── base.html           \# Base layout template
│   ├── login.html  
│   ├── dashboard.html  
│   ├── /admin/             \# Admin panel templates
│   ├── /downtime/          \# Downtime entry template
│   ├── /scheduling/        \# Scheduling grid template
│   ├── /mrp/               \# MRP dashboard, summary, buyer view templates
│   ├── /jobs/              \# Open Jobs viewer template
│   ├── /bom/               \# BOM viewer template
│   ├── /po/                \# PO viewer template
│   ├── /sales/             \# Sales analysis template
│   ├── /reports/           \# Report templates (hub, summary, forecast, CoC)
│   └── /components/        \# Reusable template components (filters, language selector)
│
├── /translations/          \# Internationalization files (Babel)
│   ├── /en/LC\_MESSAGES/    \# English translations (.po, .mo)
│   └── /es/LC\_MESSAGES/    \# Spanish translations (.po, .mo)
│   └── messages.pot        \# Template for translations
│
├── /utils/                 \# Helper utilities
│   ├── **init**.py  
│   ├── helpers.py          \# General utility functions
│   ├── validators.py       \# Input validation functions
│   └── pdf\_generator.py    \# CoC PDF generation logic
│
└── babel.cfg               \# Babel configuration for string extraction

```

-----

## 📄 License

(Specify your project's license here, e.g., MIT, GPL, Proprietary)

-----

## 🙏 Acknowledgements

* Flask, pyodbc, ldap3, Flask-Babel, openpyxl, reportlab, python-dotenv
```

-----

This updated README provides a more accurate picture of the application's current features, structure, and access control based on the information provided.