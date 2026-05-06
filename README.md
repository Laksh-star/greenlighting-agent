# 🎬 Movie/TV Project Greenlighting Agent

<div align="center">
  <img src="demo.gif" alt="Greenlighting Agent Demo" width="100%"/>
  <br/>
  <sub>Courtesy: Replit Free Agent Day</sub>
</div>

An AI-powered decision support system that helps studios and production companies evaluate whether to greenlight film and TV projects.

## 🎯 What It Does

The Greenlighting Agent conducts comprehensive analysis across 6 implemented subagents plus master orchestration:

1. **Market Research** - Comparable titles, box office trends, streaming performance
2. **Audience Intelligence** - Demographics, social sentiment, fan communities  
3. **Financial Modeling** - ROI projections, budget feasibility, revenue forecasts
4. **Competitive Analysis** - Market saturation, release timing, competitive landscape
5. **Creative Assessment** - Script elements, cast potential, genre appeal
6. **Risk Analysis** - Potential pitfalls, controversies, execution challenges
7. **Master Orchestration** - Synthesizes findings into final recommendation

## 🏗️ Architecture

### Multi-Agent System
- **6 Specialized Subagents** for domain-specific analysis
- **TMDB API comparable enrichment** when a TMDB key is configured
- **No-key sample mode** for deterministic local demos
- **Slash Commands** for workflow control

### Technology Stack
- **Anthropic Python SDK**
- **TMDB API** for movie/TV data
- **Anthropic API** (Claude Sonnet 4.5)
- **Python 3.10+**

## 📋 Prerequisites

1. **Python 3.10 or higher**
2. **Anthropic API Key** - Required for full live analysis
3. **TMDB API Key** - Optional, used for comparable-title enrichment
4. **Git** (optional, for version control)

## 🚀 Installation

### Step 1: Clone/Download Project

```bash
# If using git
git clone <your-repo-url>
cd greenlighting-agent

# Or download and extract ZIP, then:
cd greenlighting-agent
```

### Step 2: Create Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate it
# On Mac/Linux:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

### Step 3: Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 4: Configure Environment Variables

```bash
# Copy the example env file
cp .env.example .env

# Edit .env and add your API keys:
# - ANTHROPIC_API_KEY=your_anthropic_key_here
# - TMDB_API_KEY=your_tmdb_key_here
```

## 🎮 Usage

### Basic Analysis

```bash
python main.py --project "Sci-fi thriller about AI rebellion" --budget 50000000 --genre "Science Fiction" --comparables "Arrival,Ex Machina,The Creator" --target-audience "adults 18-49"
```

### No-Key Sample Demo

```bash
python main.py --sample
```

### Interactive Mode

```bash
python main.py --interactive
```

Then use slash commands:
- `/analyze-script <project_description>` - Full greenlight analysis
- `/market-research <genre> <comparable_titles>` - Market analysis only
- `/financial-model <budget> <target_audience>` - Financial projections
- `/risk-assessment <project_description>` - Risk analysis
- `/help` - Show all commands

### Example Workflow

```bash
# Start interactive session
python main.py --interactive

# Analyze a project
/analyze-script A gritty crime drama set in 1970s New York, following a detective investigating corruption. Think Serpico meets The Godfather. Budget: $35M

# Get detailed market research
/market-research crime-drama Serpico,French-Connection,Donnie-Brasco

# Run financial model
/financial-model 35000000 adults-25-54

# Check risks
/risk-assessment Period crime drama with dark themes
```

## 📁 Project Structure

```
greenlighting-agent/
├── README.md                 # This file
├── requirements.txt          # Python dependencies
├── .env.example             # Environment variables template
├── .env                     # Your actual API keys (DO NOT COMMIT)
├── main.py                  # Entry point
├── config.py                # Configuration management
├── agents/
│   ├── __init__.py
│   ├── master_agent.py      # Main orchestrator
│   ├── market_research.py   # Market analysis subagent
│   ├── audience_intel.py    # Audience intelligence
│   ├── financial_model.py   # Financial modeling
│   ├── competitive.py       # Competitive analysis
│   ├── creative_assess.py   # Creative assessment
│   └── risk_analysis.py     # Risk analysis
├── tools/
│   ├── __init__.py
│   ├── tmdb_tools.py        # TMDB API wrapper
├── utils/
│   ├── __init__.py
│   ├── prompt_templates.py  # Agent prompts
│   ├── sample_data.py       # Offline demo fixture
│   └── helpers.py           # Utility functions
└── outputs/
    └── reports/             # Generated analysis reports
```

## 🔧 Configuration

### API Rate Limits
- TMDB: 40 requests per 10 seconds
- Anthropic: Varies by plan (check your console)

### Model Selection
Default: `claude-sonnet-4-5-20250929`

To use a different model, edit `config.py`:
```python
MODEL_NAME = "claude-opus-4-20250514"  # For more complex analysis
```

## 📊 Output Formats

The agent generates comprehensive reports including:

1. **Executive Summary** - TL;DR recommendation
2. **Decision Drivers** - Top reasons behind the recommendation
3. **Comparable Evidence Table** - Budget, revenue, ROI, rating, and similar-title signals
4. **Financial Scenario Snapshot** - Conservative, moderate, and optimistic revenue/ROI
5. **Audience Insights** - Demographics, platform fit, and audience demand
6. **Competitive Landscape** - Release timing, market gaps
7. **Creative Evaluation** - Script/concept strengths
8. **Risk Matrix** - Identified risks with mitigation strategies
9. **Final Recommendation** - Go/No-Go with confidence level

Reports saved to: `outputs/reports/project_name_YYYYMMDD_HHMMSS.md`

## 🛠️ Development

### Adding New Subagents

1. Create new file in `agents/` directory
2. Inherit from base agent class
3. Implement `analyze()` method
4. Register in `master_agent.py`

### MCP Servers

MCP server packaging is still a future integration. The current runnable path is a CLI app with direct TMDB API enrichment.

## 🐛 Troubleshooting

### "Module not found" errors
```bash
# Make sure you're in the virtual environment
source venv/bin/activate  # Mac/Linux
venv\Scripts\activate     # Windows

# Reinstall dependencies
pip install -r requirements.txt
```

### API Key Issues
`python main.py --sample` does not need API keys. Full live analysis requires `ANTHROPIC_API_KEY`; TMDB enrichment requires `TMDB_API_KEY`.

```bash
# Check your .env file exists and has keys
cat .env

# Verify environment variables are loaded
python -c "from config import ANTHROPIC_API_KEY; print('Key loaded:', bool(ANTHROPIC_API_KEY))"
```

### TMDB API Errors
- Verify your API key is active at https://www.themoviedb.org/settings/api
- Check you haven't exceeded rate limits (40 req/10 sec)

## 📚 Resources

- [TMDB API Documentation](https://developer.themoviedb.org/docs)
- [Anthropic API Reference](https://docs.anthropic.com/en/api)

## 🤝 Contributing

This is a demonstration project. Feel free to fork and customize for your needs.

## 📄 License

MIT License - Feel free to use for commercial or personal projects.

## ⚠️ Disclaimer

This tool provides decision support only. Always conduct thorough due diligence and consult with industry professionals before making production decisions.

---

**Built with Claude Agent SDK | Powered by Claude Sonnet 4.5**
