# 🚀 Quick Start Guide

## Setup (5 minutes)

### 1. Get Your API Keys

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

### 3. Configure Environment

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
# Run a quick analysis
python main.py --project "A sci-fi thriller about AI rebellion in 2045" --budget 50000000 --genre "Science Fiction"
```

### Interactive Mode (Recommended)

```bash
# Start interactive session
python main.py --interactive

# Then use commands like:
> /analyze-script A gritty crime drama set in 1970s New York, following a detective investigating corruption
# (You'll be prompted for budget, genre, etc.)
```

### Example Projects to Test

#### 1. Low Budget Horror
```bash
python main.py --project "Found footage horror film about paranormal investigators in an abandoned asylum" --budget 2000000 --genre "Horror" --platform "theatrical"
```

#### 2. Streaming Comedy
```bash
python main.py --project "Rom-com about a wedding planner who falls for the groom. Think 27 Dresses meets The Wedding Planner" --budget 15000000 --genre "Comedy" --platform "streaming"
```

#### 3. Prestige Drama
```bash
python main.py --project "Biopic of a famous jazz musician during the civil rights era. Awards potential" --budget 35000000 --genre "Drama" --platform "hybrid"
```

#### 4. Tentpole Action
```bash
python main.py --project "Superhero team-up film with established characters. Think Avengers-scale" --budget 200000000 --genre "Action" --platform "theatrical"
```

## Understanding the Output

The agent will:
1. Run 3-7 specialized subagent analyses in parallel
2. Show real-time progress
3. Synthesize a final recommendation
4. Generate a comprehensive markdown report in `outputs/reports/`

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

## Tips

- **Be specific** in project descriptions - more detail = better analysis
- **Include comparables** when you know them - helps market research
- **Try different budgets** - see how it affects financial projections
- **Review reports** - the detailed analyses contain valuable insights

## Getting Help

- Check the main README.md for full documentation
- Review example projects above
- Check the `outputs/reports/` folder for sample reports

Happy greenlighting! 🎬
