#!/usr/bin/env python3
"""
Test script to verify the Greenlighting Agent setup.
Run this to ensure everything is configured correctly.
"""

import sys
from pathlib import Path

def test_imports():
    """Test that all required packages can be imported."""
    print("Testing imports...")
    
    required_packages = [
        ('anthropic', 'Anthropic SDK'),
        ('dotenv', 'python-dotenv'),
        ('requests', 'requests'),
        ('pydantic', 'pydantic'),
    ]
    
    for package, name in required_packages:
        try:
            __import__(package)
            print(f"  ✓ {name}")
        except ImportError:
            print(f"  ✗ {name} - MISSING")
            return False
    
    return True


def test_config():
    """Test configuration can load without requiring API keys."""
    print("\nTesting configuration...")
    
    try:
        import config
        print(f"  ✓ Configuration loaded")
        
        if config.ANTHROPIC_API_KEY:
            print(f"  ✓ Anthropic API key configured")
        else:
            print(f"  • Anthropic API key not configured; --sample still works")

        if config.TMDB_API_KEY:
            print(f"  ✓ TMDB API key configured")
        else:
            print(f"  • TMDB API key not configured; comparable enrichment will be skipped")
        
        print(f"  ✓ Model: {config.MODEL_NAME}")
        print(f"  ✓ Output dir: {config.OUTPUT_DIR}")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Configuration error: {str(e)}")
        return False


def test_agents():
    """Test that agents can be imported and initialized."""
    print("\nTesting agents...")
    
    try:
        from agents import BaseAgent
        print(f"  ✓ Base agent imported")
        
        from agents.market_research import MarketResearchAgent
        market_agent = MarketResearchAgent()
        print(f"  ✓ Market Research Agent")
        
        from agents.financial_model import FinancialModelingAgent
        finance_agent = FinancialModelingAgent()
        print(f"  ✓ Financial Modeling Agent")
        
        from agents.risk_analysis import RiskAnalysisAgent
        risk_agent = RiskAnalysisAgent()
        print(f"  ✓ Risk Analysis Agent")
        
        from agents.master_agent import MasterOrchestratorAgent
        master = MasterOrchestratorAgent()
        print(f"  ✓ Master Orchestrator")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Agent error: {str(e)}")
        return False


def test_tools():
    """Test TMDB tools can initialize; live calls require a key."""
    print("\nTesting TMDB tools...")
    
    try:
        from tools.tmdb_tools import TMDBClient
        client = TMDBClient()
        print(f"  ✓ TMDB Client initialized")
        
        try:
            from config import TMDB_API_KEY
            if TMDB_API_KEY:
                genres = client.get_genre_list()
                print(f"  ✓ TMDB API connection successful ({len(genres)} genres found)")
            else:
                print(f"  • TMDB API key not configured; skipped live API call")
            return True
        except Exception as e:
            print(f"  ✗ TMDB API call failed: {str(e)}")
            print(f"    → Check your TMDB API key in .env")
            return False
            
    except Exception as e:
        print(f"  ✗ TMDB tools error: {str(e)}")
        return False


def test_output_dir():
    """Test that output directory exists."""
    print("\nTesting output directory...")
    
    try:
        from config import OUTPUT_DIR
        if OUTPUT_DIR.exists():
            print(f"  ✓ Output directory exists: {OUTPUT_DIR}")
            return True
        else:
            print(f"  ✗ Output directory does not exist")
            return False
    except Exception as e:
        print(f"  ✗ Error: {str(e)}")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("GREENLIGHTING AGENT - SETUP TEST")
    print("=" * 60)
    
    tests = [
        ("Package Imports", test_imports),
        ("Configuration", test_config),
        ("Agents", test_agents),
        ("TMDB Tools", test_tools),
        ("Output Directory", test_output_dir),
    ]
    
    results = {}
    for name, test_func in tests:
        results[name] = test_func()
    
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status} - {name}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print("\n🎉 All tests passed! You're ready to run the agent.")
        print("\nTry this command:")
        print('  python main.py --sample')
        return 0
    else:
        print("\n⚠️  Some tests failed. Please fix the issues above.")
        print("\nCommon fixes:")
        print("  1. Make sure you copied .env.example to .env")
        print("  2. Add your API keys to the .env file")
        print("  3. Install requirements: pip install -r requirements.txt")
        return 1


if __name__ == "__main__":
    sys.exit(main())
