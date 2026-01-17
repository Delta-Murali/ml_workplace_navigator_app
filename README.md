# Workplace Navigator

AI-powered indoor workplace navigation and wayfinding application. Find people, rooms, and amenities in your office building using natural language search.

![Workplace Navigator](https://img.shields.io/badge/React-18-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-0.109-green) ![Python](https://img.shields.io/badge/Python-3.11+-yellow) ![License](https://img.shields.io/badge/License-MIT-purple)

## 🎯 What This App Does

Workplace Navigator is a **digital concierge** for office buildings that helps employees:

- **🔍 Find People** - Search for colleagues by name or job title (e.g., "Where is the CEO?", "Find John Smith")
- **🏢 Find Rooms** - Locate meeting rooms, conference rooms, huddle spaces by name
- **☕ Find Amenities** - Navigate to restrooms, cafeteria, kitchen, elevators, IT helpdesk
- **🗺️ Visual Navigation** - Interactive floor map with highlighted destinations
- **🤖 AI-Powered Search** - Natural language understanding for intuitive queries

### Example Searches
- "Where is the nearest restroom?"
- "Find the CEO"
- "Take me to Conference Room A"
- "Where can I get coffee?"
- "Find IT helpdesk"

## 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | React 18, TypeScript, Vite, Tailwind CSS, MapLibre GL |
| **Backend** | Python 3.11+, FastAPI, Pydantic |
| **AI/NLP** | OpenRouter API (Claude 3.5 Sonnet) |
| **Data** | GeoJSON (IMDF format) |
| **PWA** | Offline support, installable |

## 📋 Prerequisites

- **Node.js** 18+ (for frontend)
- **Python** 3.11+ (for backend)
- **OpenRouter API Key** (optional, for AI-powered search)

## 🚀 Quick Start

### Option 1: Run Locally (Recommended for Development)

#### 1. Clone the Repository
```bash
git clone <repository-url>
cd ml_workplace_navigator_app
```

#### 2. Start the Backend
```bash
cd backend

# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment (optional - for AI features)
cp .env.example .env
# Edit .env and add your OPENROUTER_API_KEY

# Run the server
./run.sh
# Or: python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Backend will be running at: **http://localhost:8000**
- API Documentation: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

#### 3. Start the Frontend
```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev
```

Frontend will be running at: **http://localhost:5173**

### Option 2: Run with Docker

```bash
# Start all services
docker-compose up --build

# Access the app
# Frontend: http://localhost
# Backend API: http://localhost:8000
```

## ⚙️ Configuration

### Backend Environment Variables

Create `backend/.env` file:

```env
# Application
DEBUG=true
PORT=8000

# CORS origins (JSON array)
CORS_ORIGINS=["http://localhost:5173","http://localhost:3000"]

# OpenRouter AI (Optional - enables AI-powered natural language search)
OPENROUTER_API_KEY=your_api_key_here
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet

# Azure Maps (Optional - for advanced mapping features)
AZURE_MAPS_CLIENT_ID=
AZURE_MAPS_SUBSCRIPTION_KEY=
```

### Frontend Environment Variables

Create `frontend/.env` file:

```env
# API Configuration
VITE_API_URL=http://localhost:8000
VITE_API_PREFIX=/api

# Application
VITE_APP_NAME=Workplace Navigator
VITE_DEV_PORT=5173
```

## 📁 Project Structure

```
ml_workplace_navigator_app/
├── backend/
│   ├── app/
│   │   ├── core/           # Configuration
│   │   │   └── config.py   # Environment settings
│   │   ├── models/         # Data models
│   │   ├── routers/        # API endpoints
│   │   │   ├── search.py   # Search API
│   │   │   ├── floorplan.py # Floor plan & navigation
│   │   │   └── map_config.py
│   │   └── services/       # Business logic
│   │       └── ai_service.py # OpenRouter integration
│   ├── floorplan_geojson/  # Floor plan data (IMDF format)
│   │   └── imdf_package/
│   │       ├── unit.geojson     # Rooms & workspaces
│   │       ├── level.geojson    # Floor levels
│   │       ├── opening.geojson  # Doors & connections
│   │       └── amenity.geojson  # Points of interest
│   ├── requirements.txt
│   ├── run.sh              # Startup script
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/     # React components
│   │   │   ├── MapLibre.tsx    # Interactive map
│   │   │   ├── SearchPanel.tsx # Search interface
│   │   │   └── FloorSelector.tsx
│   │   ├── services/
│   │   │   └── api.ts      # Backend API client
│   │   └── App.tsx
│   ├── .env                # Environment config
│   ├── package.json
│   └── Dockerfile
├── docs/                   # Documentation
├── docker-compose.yml
└── README.md
```

## 🔌 API Endpoints

### Search
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/search` | AI-powered search with natural language |
| `GET` | `/api/search/quick?q=<query>` | Quick text search |

### Floor Plan
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/floorplan/levels` | Get all floor levels |
| `GET` | `/api/floorplan/units/floor/{floor}` | Get rooms for a floor |
| `GET` | `/api/floorplan/amenities/floor/{floor}` | Get amenities for a floor |
| `POST` | `/api/floorplan/navigate/smart` | Get navigation path |

### Health
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Basic health check |
| `GET` | `/health` | Detailed health status |

## 🗺️ Floor Plan Data

The app uses **IMDF (Indoor Mapping Data Format)** GeoJSON files located in `backend/floorplan_geojson/imdf_package/`:

- **unit.geojson** - Rooms, offices, workspaces with occupant information
- **level.geojson** - Floor levels with ordinal numbers
- **opening.geojson** - Doors and navigation connections between units
- **amenity.geojson** - Points of interest (workstations, equipment)

### Adding/Modifying Floor Plan Data

Edit the GeoJSON files directly. Each unit can have:
- `name` - Room name
- `category` - Room type (office, conferenceroom, restroom, etc.)
- `occupant` - Person assigned to the room
- `seats` - Array of workstations with employee info

## 🧪 Testing the App

1. Open the app at http://localhost:5173
2. Use the search bar to try queries like:
   - "Find restroom"
   - "Where is the CEO"
   - "Conference room"
   - "Kitchen"
3. Click on search results to highlight locations on the map
4. Use the floor selector to switch between floors

## 🐛 Troubleshooting

### Backend won't start
```bash
# Check Python version (needs 3.11+)
python3 --version

# Install dependencies
pip install -r requirements.txt
```

### Frontend can't connect to backend
```bash
# Ensure backend is running on port 8000
# Check frontend/.env has correct VITE_API_URL
```

### Search returns no results
- Check that GeoJSON files exist in `backend/floorplan_geojson/imdf_package/`
- AI features require `OPENROUTER_API_KEY` in backend/.env

## 📄 License

MIT License - See LICENSE file for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request