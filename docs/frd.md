This updated **Functional Requirements Document (FRD)** and **Implementation Plan** reflect a modern, multi-cloud architecture. It leverages **Azure Maps** for spatial intelligence, **GCP/PostgreSQL** for data, and **OpenRouter** for flexible AI, all wrapped in a high-performance **FastAPI/React PWA**.

---

# Part 1: Updated Detailed FRD

## 1. System Architecture (The "Hybrid" Stack)
*   **Frontend:** React 18 (Vite), Tailwind CSS (Professional/Corporate Theme), Lucide Icons.
*   **PWA:** Service Workers for caching, `manifest.json` for "Add to Home Screen," and offline splash screen.
*   **Backend:** Python 3.11+ FastAPI.
*   **Database:** PostgreSQL with **PostGIS** extension (for advanced spatial queries).
*   **Mapping:** Azure Maps Creator (Indoor Maps WFS/WMS).
*   **AI/NLP:** OpenRouter (Accessing Claude 3.5 Sonnet or GPT-4o) via OpenAI-compatible SDK.

## 2. UI/UX Requirements
*   **Theme:** "Enterprise Modern." High contrast, clean whitespace, rounded corners (Tailwind `rounded-xl`).
*   **Mode Switcher:** Systematic support for Light and Dark modes using Tailwind’s `dark:` utility classes.
*   **PWA Features:** 
    *   Offline-first UI showing "System Offline" when no connection is found.
    *   Smooth transitions between map floors.
    *   Mobile-optimized "Bottom Sheet" for search results and directions.

## 3. Functional Modules
### 3.1 The "PostGIS" Data Layer
*   Store employee desk IDs, room polygons, and POIs.
*   **Spatial Search:** Ability to find "nearest" services using PostGIS `ST_Distance`.

### 3.2 AI Intent Engine (OpenRouter)
*   User Input: "Where can I find a quiet place to work on floor 2?"
*   OpenRouter Logic: Interprets "quiet place" as `category: 'Focus Room'` or `category: 'Library'`.
*   Safety: System prompt constrains AI to only return valid room categories found in the DB.

### 3.3 Indoor Wayfinding (Azure Maps)
*   Render 2D/3D indoor floor plans.
*   Execute routing between `current_location` and `target_destination`.
*   Support for "Waypoints" (e.g., "Stop at the Cafe on the way to the Tech Hub").

---

# Part 2: Phase-Wise Implementation Plan (Agent-Ready)

This plan is written as instructions for an AI Coding Agent (Cursor, Windsurf, etc.).

## Phase 1: Environment & Spatial Database (Week 1)
**Focus:** Backend infrastructure and PostGIS setup.

*   **Task 1 (Agent):** "Initialize a FastAPI project with a PostgreSQL connection using SQLModel. Configure PostGIS extension in the migration script. Create tables for `Employees` (with `geom` point column) and `Rooms` (with `geom` polygon column)."
*   **Task 2 (Agent):** "Create a Python script to parse the CSV roster. Use the `Shapely` library to convert desk coordinates into PostGIS-compatible geometry points and insert them into the database."
*   **Task 3 (Agent):** "Create a `.env` manager to handle Azure Maps Client ID, OpenRouter API Key, and Postgres Credentials."

## Phase 2: OpenRouter & Intent Logic (Week 2)
**Focus:** The "Concierge" brain.

*   **Task 1 (Agent):** "Create `app/services/ai_service.py`. Implement an OpenRouter client using the OpenAI Python SDK. Create a function `get_intent(user_query: str)` that returns a structured JSON object: `{'type': 'routing', 'target': 'HR', 'floor': 6}`."
*   **Task 2 (Agent):** "Write a FastAPI endpoint `/api/search` that: 1. Calls OpenRouter to get intent. 2. Queries Postgres/PostGIS to find the matching FeatureID. 3. Returns the FeatureID and Room Metadata."

## Phase 3: The "Professional" Frontend & PWA (Week 3)
**Focus:** React UI with Tailwind and Dark Mode.

*   **Task 1 (Agent):** "Setup a React project with Vite, Tailwind CSS, and Shadcn UI. Implement a `ThemeProvider` that toggles between light and dark modes. Use a professional color palette: Slate-900 for dark mode, Gray-50 for light mode, and Indigo-600 for primary actions."
*   **Task 2 (Agent):** "Integrate `vite-plugin-pwa` to generate a Web App Manifest and Service Worker. Ensure the app is installable and has an `offline.html` page."
*   **Task 3 (Agent):** "Create a 'Search Drawer' component that slides up from the bottom on mobile, containing the AI search bar."

## Phase 4: Azure Maps Integration (Week 4)
**Focus:** Visualizing the map and routing.

*   **Task 1 (Agent):** "Install Azure Maps Web SDK. Create a `Map.tsx` component. Use the `atlas.indoor.IndoorManager` to load the facility. Fetch the Map API key from the FastAPI backend (do not hardcode)."
*   **Task 2 (Agent):** "Implement a `drawNavigationPath(start, end)` function. Use the Azure Maps Route Service to fetch the path and render it as a polyline on the map. Add custom icons for 'Start' and 'Destination'."
*   **Task 3 (Agent):** "Link the Search Drawer to the Map. When a user selects a search result, the map should auto-zoom to that room/desk and trigger the routing logic."

## Phase 5: Polishing & Deployment (Week 5)
**Focus:** UX and Hosting.

*   **Task 1 (Agent):** "Add loading skeletons (Shadcn) for when the AI is 'thinking.' Add a 'You are Here' marker logic based on the URL QR code parameter `?loc=...`."
*   **Task 2 (Agent):** "Write a Dockerfile for the FastAPI backend and a separate one for the React frontend (Nginx). Add a `docker-compose.yml` for local testing with the Postgres DB."

---

# Part 3: Essential AI Agent System Prompt

*Give this to your AI Coding Agent to ensure it stays within the new architecture:*

> "You are building a Multi-Cloud Digital Concierge. 
> 1. **Data:** Use PostgreSQL with PostGIS for all spatial data. 
> 2. **AI:** Use OpenRouter for all NLP tasks (base_url: https://openrouter.ai/api/v1). 
> 3. **Maps:** Use Azure Maps Web SDK for the UI and Indoor Routing. 
> 4. **Styling:** Use Tailwind CSS. Follow a 'Professional/Corporate' aesthetic. Every component must support `dark:` mode. 
> 5. **Reliability:** The frontend must be a PWA. The backend must be FastAPI with asynchronous database calls (asyncpg)."