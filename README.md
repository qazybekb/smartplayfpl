# SmartPlay FPL

> AI-Powered Fantasy Premier League Assistant with Knowledge Graph Technology

[![Live Demo](https://img.shields.io/badge/Live-smartplayfpl.com-blue)](https://smartplayfpl.com)
[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![Next.js](https://img.shields.io/badge/Next.js-15-black.svg)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com)

## Overview

SmartPlay FPL is a full-stack application that helps Fantasy Premier League managers make data-driven decisions using:

- **Machine Learning**: Custom points prediction models trained on historical FPL data
- **Knowledge Graph**: RDF/OWL ontology for semantic player classification
- **AI Analysis**: Claude-powered transfer recommendations and squad insights
- **Real-time Data**: Live integration with the official FPL API

## Features

### Core Features
- **My Team Dashboard** - Comprehensive analysis of your FPL team
- **Squad Builder** - AI-optimized squad generation with multiple strategies
- **Transfer Recommendations** - Buy/sell analysis powered by ML predictions
- **Chip Strategy** - Optimal chip usage recommendations based on fixtures

### Technical Highlights
- **Smart Tags**: OWL-inferred player classifications (Captain Candidate, Differential Pick, Rotation Risk, etc.)
- **SHACL Validation**: Constraint checking for squad rules
- **SPARQL Queries**: Complex player discovery and comparison
- **Prediction Pipeline**: ML models for points, playing time, and form prediction

## Architecture

```
SmartPlayFPL/
├── frontend/          # Next.js 15 + TypeScript + Tailwind CSS
│   └── src/
│       ├── app/       # App router pages
│       └── components/# React components
├── backend/           # FastAPI + Python
│   ├── services/      # Business logic
│   ├── routers/       # API endpoints
│   ├── ml/            # ML pipeline and models
│   └── middleware/    # Error handling, security
└── DATASHEET.md       # Dataset documentation
```

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js 15, React 19, TypeScript, Tailwind CSS |
| Backend | FastAPI, Python 3.11+, Pydantic |
| Database | PostgreSQL (production), SQLite (development) |
| ML | scikit-learn, pandas, NumPy |
| Knowledge Graph | RDFLib, OWLRL, PySHACL |
| AI | Claude API (Anthropic) |
| Deployment | Vercel (frontend), Railway (backend) |

## Getting Started

### Prerequisites
- Node.js 18+
- Python 3.11+
- npm or yarn

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your API keys

# Run the server
./start_backend.sh
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Set up environment variables
cp .env.example .env.local
# Edit .env.local with your backend URL

# Run the development server
./START_SERVER.sh
```

The app will be available at `http://localhost:3002`

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/team/{team_id}` | Fetch team data and analysis |
| `POST /api/build/squad` | Generate optimized squad |
| `GET /api/kg/smart-tags` | Get OWL-inferred player tags |
| `POST /api/squad-analysis/` | AI-powered squad analysis |
| `GET /api/health` | Health check |

## ML Pipeline

The machine learning pipeline (`backend/ml/`) includes:

1. **Data Collection** - Fetches historical FPL data
2. **Feature Engineering** - Creates predictive features
3. **Model Training** - Trains prediction models
4. **Score Generation** - Generates player scores for the app

Key notebooks:
- `fpl_final_predictor.ipynb` - Main prediction pipeline
- `fpl_ml_pipeline.ipynb` - ML training and evaluation

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Author

**Qazybek Beken**
UC Berkeley, School of Information

[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-blue)](https://www.linkedin.com/in/qazybek-beken/)

## License

This project is for educational purposes. The underlying FPL data is owned by the Premier League.

## Acknowledgments

- Fantasy Premier League for the API
- Anthropic for Claude AI
- The FPL community for inspiration
