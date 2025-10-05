#!/usr/bin/env python3
"""
Movie/TV Project Greenlighting Agent - Main Entry Point

This agent helps studios and production companies evaluate whether to greenlight
film and TV projects through comprehensive multi-agent analysis.
"""

import asyncio
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

from agents.master_agent import MasterOrchestratorAgent
from config import OUTPUT_DIR
from utils.helpers import (
    print_header, print_success, print_error, print_info, print_warning,
    sanitize_filename, extract_project_name, get_timestamp
)


class GreenlightingCLI:
    """Command-line interface for the Greenlighting Agent."""
    
    def __init__(self):
        self.master_agent = MasterOrchestratorAgent()
        self.interactive_mode = False
    
    async def analyze_project(
        self,
        description: str,
        budget: int = 0,
        genre: str = "Unknown",
        platform: str = "theatrical",
        comparables: list = None,
        target_audience: str = "general"
    ) -> Dict[str, Any]:
        """
        Run full greenlighting analysis.
        
        Args:
            description: Project description
            budget: Production budget
            genre: Primary genre
            platform: Distribution platform (theatrical, streaming, hybrid)
            comparables: List of comparable titles
            target_audience: Target demographic
            
        Returns:
            Complete analysis results
        """
        
        project_data = {
            'description': description,
            'budget': budget,
            'genre': genre,
            'platform': platform,
            'comparables': comparables or [],
            'target_audience': target_audience
        }
        
        # Run analysis
        results = await self.master_agent.analyze(project_data)
        
        # Generate report
        report_path = self._save_report(results)
        
        # Display results
        self._display_results(results, report_path)
        
        return results
    
    def _save_report(self, results: Dict[str, Any]) -> Path:
        """Save analysis report to file."""
        
        project_desc = results['project_data']['description']
        project_name = sanitize_filename(extract_project_name(project_desc))
        timestamp = get_timestamp()
        
        filename = f"{project_name}_{timestamp}.md"
        filepath = OUTPUT_DIR / filename
        
        # Format report
        report_content = self._format_report(results)
        
        # Save to file
        with open(filepath, 'w') as f:
            f.write(report_content)
        
        return filepath
    
    def _format_report(self, results: Dict[str, Any]) -> str:
        """Format results into markdown report."""
        
        lines = []
        
        # Header
        lines.append("# 🎬 PROJECT GREENLIGHTING ANALYSIS REPORT")
        lines.append("")
        lines.append(f"**Generated:** {datetime.now().strftime('%B %d, %Y at %I:%M %p')}")
        lines.append(f"**Analyst:** Greenlighting Agent v1.0")
        lines.append("")
        lines.append("---")
        lines.append("")
        
        # Project Info
        project_data = results['project_data']
        lines.append("## 📋 PROJECT INFORMATION")
        lines.append("")
        lines.append(f"**Description:** {project_data['description']}")
        lines.append(f"**Budget:** ${project_data['budget']:,}")
        lines.append(f"**Genre:** {project_data['genre']}")
        lines.append(f"**Platform:** {project_data['platform']}")
        lines.append(f"**Target Audience:** {project_data['target_audience']}")
        
        if project_data.get('comparables'):
            lines.append(f"**Comparable Titles:** {', '.join(project_data['comparables'])}")
        
        lines.append("")
        lines.append("---")
        lines.append("")
        
        # Final Recommendation
        final_rec = results['final_recommendation']
        lines.append("## 🎯 FINAL RECOMMENDATION")
        lines.append("")
        lines.append(f"### {final_rec['recommendation']}")
        lines.append("")
        lines.append(f"**Confidence Level:** {final_rec['confidence']:.1%}")
        lines.append("")
        lines.append(f"**Executive Summary:** {final_rec['summary']}")
        lines.append("")
        lines.append("---")
        lines.append("")
        
        # Detailed Analysis
        lines.append("## 📊 DETAILED ANALYSIS")
        lines.append("")
        lines.append(final_rec['analysis'])
        lines.append("")
        lines.append("---")
        lines.append("")
        
        # Subagent Reports
        lines.append("## 🤖 SUBAGENT ANALYSES")
        lines.append("")
        
        for agent_name, result in results['subagent_results'].items():
            if isinstance(result, dict) and not result.get('error'):
                lines.append(f"### {result.get('agent', agent_name)}")
                lines.append("")
                lines.append(f"**Confidence:** {result.get('confidence', 0):.1%}")
                lines.append("")
                lines.append(result.get('findings', 'No findings available'))
                lines.append("")
                lines.append("---")
                lines.append("")
        
        # Footer
        lines.append("---")
        lines.append("")
        lines.append("*This report was generated by the Movie/TV Project Greenlighting Agent.*")
        lines.append("*Always conduct additional due diligence before making production decisions.*")
        
        return "\n".join(lines)
    
    def _display_results(self, results: Dict[str, Any], report_path: Path):
        """Display results to console."""
        
        print_header("✅ ANALYSIS COMPLETE")
        
        final_rec = results['final_recommendation']
        
        # Show recommendation with color coding
        rec = final_rec['recommendation']
        if rec == "GO":
            print_success(f"RECOMMENDATION: {rec}")
        elif rec == "NO-GO":
            print_error(f"RECOMMENDATION: {rec}")
        else:
            print_warning(f"RECOMMENDATION: {rec}")
        
        print_info(f"Confidence: {final_rec['confidence']:.1%}")
        print()
        print(f"📝 Full report saved to: {report_path}")
        print()
    
    async def interactive_mode(self):
        """Run in interactive mode with slash commands."""
        
        print_header("🎬 GREENLIGHTING AGENT - INTERACTIVE MODE")
        print_info("Type /help for available commands")
        print_info("Type /exit to quit")
        print()
        
        self.interactive_mode = True
        
        while self.interactive_mode:
            try:
                command = input("\n> ").strip()
                
                if not command:
                    continue
                
                if command.startswith('/'):
                    await self._handle_command(command)
                else:
                    print_warning("Commands must start with /. Type /help for options.")
                    
            except KeyboardInterrupt:
                print("\n")
                print_info("Exiting...")
                break
            except Exception as e:
                print_error(f"Error: {str(e)}")
    
    async def _handle_command(self, command: str):
        """Handle slash commands."""
        
        parts = command[1:].split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        if cmd == "help":
            self._show_help()
        
        elif cmd == "exit":
            print_info("Goodbye!")
            self.interactive_mode = False
        
        elif cmd == "analyze-script" or cmd == "analyze":
            if not args:
                print_warning("Usage: /analyze-script <project description>")
                return
            
            # Parse arguments (simplified - in production would be more robust)
            budget_input = input("Budget (in millions, e.g., 50): $").strip()
            try:
                budget = int(budget_input) * 1_000_000 if budget_input else 0
            except ValueError:
                budget = 0
            
            genre = input("Genre (e.g., Action, Drama, Horror): ").strip() or "Unknown"
            platform = input("Platform (theatrical/streaming/hybrid): ").strip() or "theatrical"
            
            await self.analyze_project(
                description=args,
                budget=budget,
                genre=genre,
                platform=platform
            )
        
        else:
            print_warning(f"Unknown command: /{cmd}")
            print_info("Type /help for available commands")
    
    def _show_help(self):
        """Display help information."""
        
        print_header("📚 AVAILABLE COMMANDS")
        print()
        print("  /analyze-script <description>  - Run full greenlighting analysis")
        print("  /help                          - Show this help message")
        print("  /exit                          - Exit interactive mode")
        print()
        print_info("More commands coming in future updates!")


async def main():
    """Main entry point."""
    
    parser = argparse.ArgumentParser(
        description="Movie/TV Project Greenlighting Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--project',
        type=str,
        help='Project description'
    )
    
    parser.add_argument(
        '--budget',
        type=int,
        default=0,
        help='Production budget in dollars'
    )
    
    parser.add_argument(
        '--genre',
        type=str,
        default='Unknown',
        help='Primary genre'
    )
    
    parser.add_argument(
        '--platform',
        type=str,
        default='theatrical',
        choices=['theatrical', 'streaming', 'hybrid'],
        help='Distribution platform'
    )
    
    parser.add_argument(
        '--interactive',
        action='store_true',
        help='Run in interactive mode'
    )
    
    args = parser.parse_args()
    
    cli = GreenlightingCLI()
    
    if args.interactive or not args.project:
        # Interactive mode
        await cli.interactive_mode()
    else:
        # Direct analysis
        await cli.analyze_project(
            description=args.project,
            budget=args.budget,
            genre=args.genre,
            platform=args.platform
        )


if __name__ == "__main__":
    asyncio.run(main())
