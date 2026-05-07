# 🚀 Quick Start Guide

## Setup (5 minutes)

You can run the sample demo without API keys:

```bash
python main.py --sample
```

### 1. Get Your API Keys For Live Analysis

#### Anthropic API Key
1. Go to https://console.anthropic.com
2. Sign up or log in
3. Click "Get API Keys"
4. Copy your API key

#### TMDB API Key
1. Go to https://www.themoviedb.org/signup
2. Create a free account
3. Go to Settings → API
4. Request an API key (it's free!)
5. Copy your API key

### 2. Install Dependencies

```bash
# Make sure you're in the project directory
cd greenlighting-agent

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Mac/Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate

# Install requirements
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure Environment For Live Analysis

```bash
# Copy the example env file
cp .env.example .env

# Edit .env with your API keys
# On Mac/Linux:
nano .env
# Or use any text editor

# Add your keys:
# ANTHROPIC_API_KEY=sk-ant-your-actual-key-here
# TMDB_API_KEY=your-actual-tmdb-key-here
```

## Running the Agent

### Quick Test

```bash
# Run the no-key sample analysis
python main.py --sample
```

### Live Analysis With Comparables

```bash
python main.py --project "A sci-fi thriller about AI rebellion in 2045" --budget 50000000 --genre "Science Fiction" --platform "theatrical" --comparables "Arrival,Ex Machina,The Creator" --target-audience "adults 18-49"
```

### Local Web Demo

```bash
uvicorn web_app:app --reload
```

Open `http://127.0.0.1:8000` to run the same analysis pipeline from a browser with progress updates, report preview, and Markdown/JSON downloads.

### Batch Mode

```bash
# Cheap mechanics test with deterministic sample-mode analysis
python main.py --batch examples/projects.csv --sample

# Live batch analysis
python main.py --batch projects.csv
```

Batch summaries are saved to `outputs/batches/`.

### Interactive Mode (Recommended)

```bash
# Start interactive session
python main.py --interactive

# Then use commands like:
> /analyze-script A gritty crime drama set in 1970s New York, following a detective investigating corruption
# (You'll be prompted for budget, genre, platform, comparables, and audience)
```

### Example Projects to Test

#### 1. Low Budget Horror
```bash
python main.py --project "Found footage horror film about paranormal investigators in an abandoned asylum" --budget 2000000 --genre "Horror" --platform "theatrical" --comparables "Paranormal Activity,Host"
```

#### 2. Streaming Comedy
```bash
python main.py --project "Rom-com about a wedding planner who falls for the groom. Think 27 Dresses meets The Wedding Planner" --budget 15000000 --genre "Comedy" --platform "streaming" --target-audience "women 18-49, rom-com fans"
```

#### 3. Prestige Drama
```bash
python main.py --project "Biopic of a famous jazz musician during the civil rights era. Awards potential" --budget 35000000 --genre "Drama" --platform "hybrid" --comparables "Ray,Walk the Line"
```

#### 4. Tentpole Action
```bash
python main.py --project "Superhero team-up film with established characters. Think Avengers-scale" --budget 200000000 --genre "Action" --platform "theatrical" --comparables "The Avengers,Justice League"
```

## Understanding the Output

The agent will:
1. Run 6 specialized subagent analyses
2. Show real-time progress
3. Synthesize a final recommendation
4. Generate Markdown and structured JSON reports in `outputs/reports/`
5. Validate report quality before saving, including recommendation consistency, comparable evidence, financial scenarios, and risk matrix coverage
6. Save a run ledger in `outputs/runs/` with token usage, estimated Anthropic cost, TMDB request counts, and the report path

### Recommendation Types
- **GO** ✅ - Strong greenlight, proceed with production
- **CONDITIONAL GO** ⚠️ - Greenlight with specific conditions
- **NO-GO** ❌ - Do not proceed

### Confidence Levels
- **Very High** (90%+) - Strong data backing
- **High** (75-90%) - Good confidence
- **Moderate** (60-75%) - Reasonable confidence
- **Low** (40-60%) - Limited data
- **Very Low** (<40%) - Insufficient data

## Common Issues

### "ANTHROPIC_API_KEY not found"
- Use `python main.py --sample` if you only want the no-key demo
- Make sure you created the `.env` file (copy from `.env.example`)
- Check that your API key is correctly formatted
- Ensure no extra spaces around the `=` sign

### "TMDB API error"
- Verify your TMDB API key is active
- Check you haven't exceeded rate limits (40 requests/10 seconds)
- Make sure your TMDB account is verified

### "Module not found"
- Activate your virtual environment: `source venv/bin/activate`
- Reinstall requirements: `pip install -r requirements.txt`

## Next Steps

1. Try analyzing different types of projects
2. Compare recommendations for different budget levels
3. Test how platform choice (theatrical vs streaming) affects analysis
4. Review the generated reports in `outputs/reports/`
5. Review run ledgers in `outputs/runs/`

## Tips

- **Be specific** in project descriptions - more detail = better analysis
- **Include comparables** when you know them - helps market research
- **Try different budgets** - see how it affects financial projections
- **Review reports** - the detailed analyses contain valuable insights

## Getting Help

- Check the main README.md for full documentation
- Review example projects above
- Check the `outputs/reports/` folder for sample reports
- Check the `outputs/runs/` folder for token/cost ledgers

Happy greenlighting! 🎬
