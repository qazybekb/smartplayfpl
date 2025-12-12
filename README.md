<p align="center">
  <img src="https://img.shields.io/badge/SmartPlay-FPL-00ff87?style=for-the-badge&labelColor=37003c" alt="SmartPlay FPL" height="40">
</p>

<h1 align="center">SmartPlay FPL</h1>

<p align="center">
  <strong>AI-Powered Fantasy Premier League Assistant with Knowledge Graph Technology</strong>
</p>

<p align="center">
  <a href="https://smartplayfpl.com">
    <img src="https://img.shields.io/badge/Live%20Demo-smartplayfpl.com-00ff87?style=flat-square&labelColor=37003c" alt="Live Demo">
  </a>
  <a href="https://github.com/qazybekb/smartplayfpl/blob/main/LICENSE">
    <img src="https://img.shields.io/badge/License-MIT-blue?style=flat-square" alt="License">
  </a>
  <img src="https://img.shields.io/badge/Python-3.11+-3776ab?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Next.js-15-black?style=flat-square&logo=next.js" alt="Next.js">
  <img src="https://img.shields.io/badge/FastAPI-0.100+-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI">
</p>

<p align="center">
  <a href="#-features">Features</a> •
  <a href="#-demo">Demo</a> •
  <a href="#-tech-stack">Tech Stack</a> •
  <a href="#-getting-started">Getting Started</a> •
  <a href="#-architecture">Architecture</a> •
  <a href="#-api-reference">API</a>
</p>

---

## Overview

SmartPlay FPL is a full-stack application that helps Fantasy Premier League managers make data-driven decisions. It combines **Machine Learning**, **Knowledge Graphs**, and **AI** to provide intelligent recommendations for your FPL team.

### What Makes It Different?

| Feature | Description |
|---------|-------------|
| **Semantic Understanding** | Uses RDF/OWL ontology to classify players into smart categories |
| **ML-Powered Predictions** | Custom models trained on historical FPL data |
| **AI Analysis** | Claude-powered natural language insights for transfers |
| **Real-time Data** | Live integration with official FPL API |

---

## Features

### Core Features

| Feature | Description |
|---------|-------------|
| **My Team Dashboard** | Comprehensive analysis of your FPL team with AI insights |
| **Squad Builder** | Generate optimal 15-player squads with multiple strategies |
| **Transfer Recommendations** | ML-powered buy/sell analysis with explanations |
| **Chip Strategy** | Optimal chip usage recommendations based on fixtures |
| **Player Explorer** | Search and filter players with smart tags |

### Smart Tags (OWL-Inferred)

The system automatically classifies players using semantic reasoning:

```
Captain Candidate  → High form + available status
Differential Pick  → Low ownership + good form
Rotation Risk      → Limited minutes despite high price
Value Pick         → Excellent points per million
Premium Asset      → High price + consistent performer
Must Buy           → Strong form + good value + available
```

---

## Demo

**Live Application**: **[https://smartplayfpl.com](https://smartplayfpl.com)**

### Key Pages

| Page | Path | Description |
|------|------|-------------|
| Team Dashboard | `/my-team/[id]` | Full team analysis with AI insights |
| Squad Builder | `/build` | Strategy-based squad generation |
| Player Explorer | `/players` | Search players with smart filters |
| ML Model Info | `/model` | Model performance metrics |

---

## Tech Stack

### Frontend

```
Next.js 15      →  React framework with App Router
React 19        →  UI components
TypeScript      →  Type safety
Tailwind CSS    →  Styling
```

### Backend

```
FastAPI         →  Python API framework
Pydantic        →  Data validation
RDFLib          →  Knowledge graph storage
OWLRL           →  OWL reasoning engine
PySHACL         →  SHACL constraint validation
```

### Machine Learning

```
scikit-learn    →  ML models
LightGBM        →  Gradient boosting
XGBoost         →  Ensemble learning
pandas          →  Data processing
```

### Infrastructure

```
Vercel          →  Frontend hosting
Railway         →  Backend hosting
PostgreSQL      →  Production database
Claude API      →  AI analysis
```

---

## Architecture

```
smartplayfpl/
│
├── frontend/                   # Next.js 15 Application
│   ├── src/
│   │   ├── app/               # App router pages
│   │   │   ├── my-team/       # Team analysis
│   │   │   ├── build/         # Squad builder
│   │   │   ├── players/       # Player explorer
│   │   │   └── model/         # ML metrics
│   │   ├── components/        # React components
│   │   ├── contexts/          # React contexts
│   │   └── lib/               # Utilities & API
│   └── public/                # Static assets
│
├── backend/                    # FastAPI Application
│   ├── routers/               # API endpoints
│   │   ├── team.py           # Team data
│   │   ├── build.py          # Squad builder
│   │   ├── kg.py             # Knowledge graph
│   │   └── ml.py             # ML predictions
│   ├── services/              # Business logic
│   │   ├── fpl_service.py    # FPL API client
│   │   ├── kg_service.py     # KG operations
│   │   ├── squad_builder.py  # Squad optimization
│   │   └── claude_service.py # AI analysis
│   ├── middleware/            # Cross-cutting concerns
│   ├── ml/                    # Machine Learning
│   │   ├── data/             # Training data
│   │   ├── models/           # Trained models (.pkl)
│   │   ├── plots/            # Visualizations
│   │   └── *.ipynb           # Jupyter notebooks
│   └── kg/                    # Knowledge Graph
│       ├── ontology.ttl      # OWL ontology
│       └── shapes.ttl        # SHACL constraints
│
└── DATASHEET.md               # Dataset documentation
```

---

## Getting Started

### Prerequisites

- **Node.js** 18+
- **Python** 3.11+
- **npm** or **yarn**

### Backend Setup

```bash
# Navigate to backend
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys:
# - DATABASE_URL
# - ANTHROPIC_API_KEY

# Start server
./start_backend.sh
```

API available at `http://localhost:8000`

### Frontend Setup

```bash
# Navigate to frontend
cd frontend

# Install dependencies
npm install

# Configure environment
cp .env.example .env.local
# Edit .env.local:
# - NEXT_PUBLIC_API_URL=http://localhost:8000

# Start development server
npm run dev
```

App available at `http://localhost:3000`

---

## API Reference

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/team/{team_id}` | Fetch team data and analysis |
| `POST` | `/api/build/squad` | Generate optimized squad |
| `GET` | `/api/kg/smart-tags` | Get OWL-inferred player tags |
| `POST` | `/api/squad-analysis/` | AI-powered squad analysis |
| `GET` | `/api/ml/scores` | Get ML prediction scores |
| `GET` | `/api/health` | Health check |

### Example

```bash
# Get team analysis
curl https://smartplayfpl.com/api/team/123456

# Build a squad
curl -X POST https://smartplayfpl.com/api/build/squad \
  -H "Content-Type: application/json" \
  -d '{"strategy": "balanced", "budget": 100.0}'
```

---

## ML Pipeline

### Pipeline Stages

```
1. Data Collection    →  Fetch historical FPL data via API
2. Feature Engineering →  Create predictive features
3. Model Training     →  Train ensemble models
4. Score Generation   →  Produce player scores
```

### Models

| Model | Type | Purpose |
|-------|------|---------|
| Random Forest | Ensemble | Points prediction |
| XGBoost | Gradient Boosting | Form prediction |
| LightGBM | Gradient Boosting | Fast inference |
| Ridge | Linear | Baseline model |

### Notebooks

- **`fpl_final_predictor.ipynb`** - Main prediction pipeline
- **`fpl_ml_pipeline.ipynb`** - Full training and evaluation

---

## Knowledge Graph

### Ontology Structure

```turtle
@prefix fpl: <http://fantasykg.org/ontology#> .

# Classes
fpl:Player, fpl:Team, fpl:Fixture, fpl:Position

# Smart Tag Classes (OWL-inferred)
fpl:CaptainCandidate, fpl:DifferentialPick,
fpl:RotationRisk, fpl:ValuePick, fpl:PremiumAsset

# Properties
fpl:playsFor, fpl:hasPosition, fpl:price, fpl:form
```

### SHACL Constraints

Squad validation rules enforced via SHACL:

- ✓ Exactly 15 players
- ✓ Budget ≤ £100.0m
- ✓ Max 3 players per team
- ✓ Valid formation (e.g., 3-4-3, 4-4-2)

---

## Contributing

Contributions are welcome! Here's how:

1. **Fork** the repository
2. **Create** your feature branch (`git checkout -b feature/amazing`)
3. **Commit** your changes (`git commit -m 'Add amazing feature'`)
4. **Push** to the branch (`git push origin feature/amazing`)
5. **Open** a Pull Request

---

## Author

<p align="center">
  <strong>Qazybek Beken</strong><br>
  UC Berkeley • School of Information
</p>

<p align="center">
  <a href="https://www.linkedin.com/in/qazybek-beken/">
    <img src="https://img.shields.io/badge/LinkedIn-Connect-0077b5?style=for-the-badge&logo=linkedin&logoColor=white" alt="LinkedIn">
  </a>
  &nbsp;
  <a href="https://github.com/qazybekb">
    <img src="https://img.shields.io/badge/GitHub-Follow-181717?style=for-the-badge&logo=github&logoColor=white" alt="GitHub">
  </a>
</p>

---

## License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

---

## Acknowledgments

- [Fantasy Premier League](https://fantasy.premierleague.com/) for the API
- [Anthropic](https://anthropic.com/) for Claude AI
- The FPL community for inspiration

---

<p align="center">
  <sub>Built with passion for FPL managers everywhere</sub>
</p>
