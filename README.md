# Workplace Navigator

AI-powered workplace navigation and wayfinding application.

## Tech Stack

- **Frontend:** React 18 (Vite), Tailwind CSS, PWA
- **Backend:** Python 3.11+ FastAPI
- **Database:** PostgreSQL with PostGIS
- **Mapping:** Azure Maps Creator (Indoor Maps)
- **AI/NLP:** OpenRouter (Claude 3.5 Sonnet / GPT-4o)

## Quick Start

### Prerequisites

- Node.js 20+
- Python 3.11+
- PostgreSQL 16+ with PostGIS extension
- Docker & Docker Compose (optional)

### Option 1: Docker (Recommended)

1. Copy environment file and configure:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

2. Start all services:
   ```bash
   docker-compose up -d
   ```

3. Access the app:
   - Frontend: http://localhost
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

### Option 2: Local Development

#### Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Copy and configure environment
cp .env.example .env

# Run development server
uvicorn app.main:app --reload
```

#### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev
```

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── core/           # Config, database
│   │   ├── models/         # SQLModel + PostGIS
│   │   ├── routers/        # API endpoints
│   │   └── services/       # AI, spatial logic
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── components/     # React components
│   │   ├── hooks/          # Custom hooks
│   │   ├── providers/      # Context providers
│   │   └── services/       # API client
│   ├── Dockerfile
│   └── package.json
├── docs/
│   └── frd.md              # Functional Requirements
├── docker-compose.yml
└── .env.example
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/search` | AI-powered natural language search |
| GET | `/api/search/quick` | Quick search with query params |
| GET | `/api/map/config` | Azure Maps configuration |
| GET | `/api/map/building` | Building floor information |
| GET | `/health` | Health check |

## Features

- 🔍 **AI Search:** Natural language queries ("Where can I find coffee?")
- 🗺️ **Indoor Maps:** Azure Maps floor plan visualization
- 🧭 **Wayfinding:** Turn-by-turn indoor navigation
- 🌓 **Dark Mode:** Automatic theme switching
- 📱 **PWA:** Installable, works offline
- ♿ **Accessible:** WCAG compliant components

## Configuration

See [.env.example](.env.example) for all available configuration options.

### Required API Keys

1. **OpenRouter:** Get from https://openrouter.ai/keys
2. **Azure Maps:** Create account in Azure Portal

## License

Proprietary - Internal Use Only