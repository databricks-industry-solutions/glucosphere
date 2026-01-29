# 📁 Codebase Reorganization Plan

**Goal:** Separate pages into independent modules so multiple developers can work on different dashboards without merge conflicts, while keeping common MCP/query infrastructure shared.

---

## Current Structure (Before)

```
src/
├── api/
│   ├── databricksAgent.js       # Multi-agent supervisor calls
│   └── databricksSQL.js         # All SQL queries for all pages
├── components/
│   └── AgentChatInterface.jsx   # Shared component
├── pages/
│   ├── CareManagementDashboard.jsx
│   ├── ClinicianDashboard.jsx
│   ├── DeviceSupportDashboard.jsx
│   └── GlucoseLandingDashboard.jsx
├── App.jsx
├── main.jsx
└── index.css
```

**Problem:** 
- All SQL queries for all pages are in one file (`databricksSQL.js`)
- If two people work on different dashboards, they both modify the same file
- Merge conflicts inevitable

---

## Proposed Structure (After)

```
src/
├── api/
│   ├── databricksAgent.js       # SHARED: Multi-agent supervisor MCP calls
│   └── databricksSQLClient.js   # SHARED: Core SQL executor (renamed)
│
├── shared/
│   └── components/
│       └── AgentChatInterface.jsx  # SHARED: Reusable components
│
├── pages/
│   ├── DeviceSupport/
│   │   ├── DeviceSupportDashboard.jsx    # Page component
│   │   ├── queries.js                    # Page-specific SQL queries
│   │   └── index.js                      # Export page
│   │
│   ├── CareManagement/
│   │   ├── CareManagementDashboard.jsx
│   │   ├── queries.js                    # (future: add real queries)
│   │   └── index.js
│   │
│   ├── Clinician/
│   │   ├── ClinicianDashboard.jsx
│   │   ├── queries.js                    # (future: add real queries)
│   │   └── index.js
│   │
│   └── GlucoseLanding/
│       ├── GlucoseLandingDashboard.jsx
│       ├── queries.js                    # (future: add real queries)
│       └── index.js
│
├── App.jsx
├── main.jsx
└── index.css
```

---

## What Gets Moved / Changed

### 1. ✅ SHARED - Stays Central (No Duplication)

**`src/api/databricksAgent.js`** - No changes
- Contains: `callMultiAgentSupervisor()`
- Used by: Any page that needs AI agent analysis
- **Reason:** Common MCP agent functionality

**`src/api/databricksSQLClient.js`** - Renamed from `databricksSQL.js`
- Contains: `executeSQLQuery()` (the core SQL executor)
- Removes: All page-specific query functions
- **Reason:** Core SQL/MCP infrastructure shared by all pages

**`src/shared/components/AgentChatInterface.jsx`** - Moved from `src/components/`
- **Reason:** Clearly mark as shared component

---

### 2. 📦 DEVICE SUPPORT - Isolated Module

**`src/pages/DeviceSupport/DeviceSupportDashboard.jsx`**
- Moved from: `src/pages/DeviceSupportDashboard.jsx`
- Imports queries from: `./queries`
- Imports shared: `../../api/databricksSQLClient`, `../../api/databricksAgent`

**`src/pages/DeviceSupport/queries.js`** - NEW FILE
- Contains (moved from `databricksSQL.js`):
  - `getDistinctDeviceCount()`
  - `getDeviceHeatmapData()`
  - `getOutOfRangeDevices()`
  - `getDevicePatternAlerts()`
- Imports: `executeSQLQuery` from `../../api/databricksSQLClient`

**`src/pages/DeviceSupport/index.js`** - NEW FILE
- Exports: `DeviceSupportDashboard` as default
- **Reason:** Clean imports elsewhere

---

### 3. 📦 CARE MANAGEMENT - Isolated Module

**`src/pages/CareManagement/CareManagementDashboard.jsx`**
- Moved from: `src/pages/CareManagementDashboard.jsx`

**`src/pages/CareManagement/queries.js`** - NEW FILE
- Currently: Empty (page uses hardcoded data)
- Future: Add real queries when ready

**`src/pages/CareManagement/index.js`** - NEW FILE
- Exports: `CareManagementDashboard`

---

### 4. 📦 CLINICIAN - Isolated Module

**`src/pages/Clinician/ClinicianDashboard.jsx`**
- Moved from: `src/pages/ClinicianDashboard.jsx`

**`src/pages/Clinician/queries.js`** - NEW FILE
- Currently: Empty (page uses hardcoded data)
- Future: Add real queries when ready

**`src/pages/Clinician/index.js`** - NEW FILE
- Exports: `ClinicianDashboard`

---

### 5. 📦 GLUCOSE LANDING - Isolated Module

**`src/pages/GlucoseLanding/GlucoseLandingDashboard.jsx`**
- Moved from: `src/pages/GlucoseLandingDashboard.jsx`

**`src/pages/GlucoseLanding/queries.js`** - NEW FILE
- Currently: Empty (landing page, no queries)

**`src/pages/GlucoseLanding/index.js`** - NEW FILE
- Exports: `GlucoseLandingDashboard`

---

## Import Path Changes

### Before:
```javascript
// In DeviceSupportDashboard.jsx
import { getDistinctDeviceCount } from '../api/databricksSQL';
import { callMultiAgentSupervisor } from '../api/databricksAgent';
```

### After:
```javascript
// In src/pages/DeviceSupport/DeviceSupportDashboard.jsx
import { getDistinctDeviceCount } from './queries';
import { callMultiAgentSupervisor } from '../../api/databricksAgent';
```

```javascript
// In src/pages/DeviceSupport/queries.js
import { executeSQLQuery } from '../../api/databricksSQLClient';

export async function getDistinctDeviceCount() {
  // ... query implementation
}
```

---

## App.jsx Route Changes

### Before:
```javascript
import DeviceSupportDashboard from './pages/DeviceSupportDashboard';
import CareManagementDashboard from './pages/CareManagementDashboard';
```

### After:
```javascript
import DeviceSupportDashboard from './pages/DeviceSupport';
import CareManagementDashboard from './pages/CareManagement';
import ClinicianDashboard from './pages/Clinician';
import GlucoseLandingDashboard from './pages/GlucoseLanding';
```

---

## Benefits

### ✅ Parallel Development
- **Developer A** works on Device Support → only touches `pages/DeviceSupport/`
- **Developer B** works on Care Management → only touches `pages/CareManagement/`
- **No merge conflicts** - different folders, different files

### ✅ Clear Ownership
- Each dashboard is self-contained in its own folder
- Easy to see what queries belong to what page
- Easy to test/debug a single dashboard

### ✅ Shared Infrastructure
- MCP/SQL client code stays centralized
- Agent functionality shared across all pages
- Shared components in one place

### ✅ Scalability
- Adding a new dashboard = create new folder with template
- New queries for a page = only edit that page's `queries.js`
- Shared utilities = edit once, all pages benefit

---

## Migration Steps

1. ✅ Create new folder structure
2. ✅ Rename `databricksSQL.js` → `databricksSQLClient.js` (remove query functions)
3. ✅ Move `AgentChatInterface.jsx` → `shared/components/`
4. ✅ Create `DeviceSupport/` folder and move files
5. ✅ Extract Device Support queries to `DeviceSupport/queries.js`
6. ✅ Create other page folders and move files
7. ✅ Create empty `queries.js` files for other pages
8. ✅ Update imports in `App.jsx`
9. ✅ Test all pages still work
10. ✅ Commit and push

---

## Files to Create/Modify

### Create:
- `src/shared/components/` (folder)
- `src/pages/DeviceSupport/` (folder)
- `src/pages/DeviceSupport/queries.js`
- `src/pages/DeviceSupport/index.js`
- `src/pages/CareManagement/` (folder)
- `src/pages/CareManagement/queries.js`
- `src/pages/CareManagement/index.js`
- `src/pages/Clinician/` (folder)
- `src/pages/Clinician/queries.js`
- `src/pages/Clinician/index.js`
- `src/pages/GlucoseLanding/` (folder)
- `src/pages/GlucoseLanding/queries.js`
- `src/pages/GlucoseLanding/index.js`

### Move:
- `src/components/AgentChatInterface.jsx` → `src/shared/components/AgentChatInterface.jsx`
- `src/pages/DeviceSupportDashboard.jsx` → `src/pages/DeviceSupport/DeviceSupportDashboard.jsx`
- `src/pages/CareManagementDashboard.jsx` → `src/pages/CareManagement/CareManagementDashboard.jsx`
- `src/pages/ClinicianDashboard.jsx` → `src/pages/Clinician/ClinicianDashboard.jsx`
- `src/pages/GlucoseLandingDashboard.jsx` → `src/pages/GlucoseLanding/GlucoseLandingDashboard.jsx`

### Rename:
- `src/api/databricksSQL.js` → `src/api/databricksSQLClient.js`

### Modify:
- `src/api/databricksSQLClient.js` - Remove all query functions, keep only `executeSQLQuery`
- `src/pages/DeviceSupport/DeviceSupportDashboard.jsx` - Update imports
- `src/App.jsx` - Update imports

### Delete:
- `src/api/databricksSQL.js` (after content moved)
- `src/components/` folder (after AgentChatInterface moved)

---

## Validation

After reorganization:
1. ✅ All pages load without errors
2. ✅ Device Support Dashboard still shows CGM data
3. ✅ AI Agent analysis still works
4. ✅ No import errors in console
5. ✅ Git status shows clean renames (not delete+add)

---

**Ready to Execute?** This will reorganize the codebase for better parallel development while maintaining shared MCP infrastructure.
