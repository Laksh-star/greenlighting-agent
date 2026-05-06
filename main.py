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
from config import OUTPUT_DIR, print_config_summary
from utils.sample_data import SAMPLE_PROJECT
from utils.helpers import (
    print_header, print_success, print_error, print_info, print_warning,
    sanitize_filename, extract_project_name, get_timestamp, format_currency
)


class GreenlightingCLI:
    """Command-line interface for the Greenlighting Agent."""
    
    def __init__(self):
        self.master_agent = MasterOrchestratorAgent()
        self.is_interactive = False
    
    async def analyze_project(
        self,
        description: str,
        budget: int = 0,
        genre: str = "Unknown",
        platform: str = "theatrical",
        comparables: list = None,
        target_audience: str = "general",
        demo_mode: bool = False,
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
            'target_audience': target_audience,
            'demo_mode': demo_mode,
        }
        
        # Run analysis
        results = await self.master_agent.analyze(project_data)
        
        # Generate report
        report_path = self._save_report(results)
        
        # Display results
        self._display_results(results, report_path)
        
        return results

    async def analyze_sample(self) -> Dict[str, Any]:
        """Run the no-key deterministic sample project."""
        return await self.analyze_project(**SAMPLE_PROJECT)
    
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

        decision_drivers = final_rec.get("decision_drivers", [])
        if decision_drivers:
            lines.append("### Decision Drivers")
            lines.append("")
            for driver in decision_drivers[:3]:
                lines.append(f"- {driver}")
            lines.append("")

        comparable_evidence = self._get_comparable_evidence(results)
        if comparable_evidence:
            lines.append("### Comparable Evidence")
            lines.append("")
            market_warning = self._get_agent_metadata(results, "market_research").get(
                "market_data_warning",
                "",
            )
            if market_warning:
                lines.append(f"**Data note:** {market_warning}")
                lines.append("")
            lines.extend(self._format_comparable_table(comparable_evidence))
            lines.append("")

        financial_metrics = self._get_financial_metrics(results)
        if financial_metrics:
            lines.append("### Financial Scenario Snapshot")
            lines.append("")
            lines.extend(self._format_financial_metrics(financial_metrics))
            lines.append("")

        risk_metadata = self._get_agent_metadata(results, "risk_analysis")
        if risk_metadata:
            lines.append("### Risk Matrix")
            lines.append("")
            lines.extend(self._format_risk_matrix(risk_metadata))
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

    def _get_agent_metadata(self, results: Dict[str, Any], agent_name: str) -> Dict[str, Any]:
        result = results.get("subagent_results", {}).get(agent_name, {})
        return result.get("metadata", {}) if isinstance(result, dict) else {}

    def _get_comparable_evidence(self, results: Dict[str, Any]) -> list:
        return self._get_agent_metadata(results, "market_research").get("comparable_evidence", [])

    def _get_financial_metrics(self, results: Dict[str, Any]) -> Dict[str, Any]:
        return self._get_agent_metadata(results, "financial_model").get("basic_metrics", {})

    def _format_comparable_table(self, comparable_evidence: list) -> list:
        lines = [
            "| Title | Year | Budget | Revenue | ROI | Rating | Similar Signals |",
            "| --- | --- | ---: | ---: | ---: | ---: | --- |",
        ]
        for item in comparable_evidence:
            similar = ", ".join(item.get("similar_titles", [])[:3])
            if not similar and item.get("source"):
                similar = item["source"]
            similar = similar or "n/a"
            lines.append(
                f"| {item.get('title', 'Unknown')} | {item.get('year', 'n/a')} | "
                f"{format_currency(item.get('budget', 0))} | "
                f"{format_currency(item.get('revenue', 0))} | "
                f"{item.get('roi', 0)}% | {item.get('rating', 0):.1f} | {similar} |"
            )
        return lines

    def _format_financial_metrics(self, metrics: Dict[str, Any]) -> list:
        rows = []
        if metrics.get("budget_warning"):
            rows.append(f"- {metrics['budget_warning']}")
        for label, revenue_key, roi_key in [
            ("Conservative", "conservative_revenue", "conservative_roi"),
            ("Moderate", "moderate_revenue", "moderate_roi"),
            ("Optimistic", "optimistic_revenue", "optimistic_roi"),
        ]:
            if revenue_key in metrics:
                rows.append(
                    f"- **{label}:** {format_currency(metrics.get(revenue_key, 0))} "
                    f"revenue, {metrics.get(roi_key, 0)}% ROI"
                )
        if "estimated_new_subscribers" in metrics:
            rows.append(f"- **Estimated new subscribers:** {metrics['estimated_new_subscribers']:,}")
            rows.append(f"- **Subscriber LTV:** {format_currency(metrics.get('subscriber_lifetime_value', 0))}")
            rows.append(f"- **Estimated ROI:** {metrics.get('estimated_roi', 0)}%")
        if metrics.get("comparable_average_revenue"):
            rows.append(
                f"- **Comparable average revenue:** "
                f"{format_currency(metrics['comparable_average_revenue'])}"
            )
        return rows

    def _format_risk_matrix(self, metadata: Dict[str, Any]) -> list:
        lines = [
            f"- **Overall Risk:** {metadata.get('risk_level', 'Unknown')} "
            f"({metadata.get('overall_risk_score', 'n/a')}/10)"
        ]
        for key, value in metadata.get("risk_factors", {}).items():
            lines.append(f"- **{key.replace('_', ' ').title()}:** {value}/10")
        return lines
    
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
        
        self.is_interactive = True
        
        while self.is_interactive:
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
            self.is_interactive = False
        
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
            comparables = parse_comparables(input("Comparables (comma-separated, optional): ").strip())
            target_audience = input("Target audience (optional): ").strip() or "general"
            
            await self.analyze_project(
                description=args,
                budget=budget,
                genre=genre,
                platform=platform,
                comparables=comparables,
                target_audience=target_audience,
            )

        elif cmd == "market-research":
            await self.analyze_project(
                description=args or "Market research request",
                genre=input("Genre: ").strip() or "Unknown",
                comparables=parse_comparables(input("Comparables (comma-separated): ").strip()),
            )

        elif cmd == "financial-model":
            budget_input = args or input("Budget in dollars: ").strip()
            try:
                budget = int(budget_input)
            except ValueError:
                budget = 0
            await self.analyze_project(
                description="Financial model request",
                budget=budget,
                target_audience=input("Target audience: ").strip() or "general",
            )

        elif cmd == "risk-assessment":
            if not args:
                print_warning("Usage: /risk-assessment <project description>")
                return
            await self.analyze_project(description=args)
        
        else:
            print_warning(f"Unknown command: /{cmd}")
            print_info("Type /help for available commands")
    
    def _show_help(self):
        """Display help information."""
        
        print_header("📚 AVAILABLE COMMANDS")
        print()
        print("  /analyze-script <description>  - Run full greenlighting analysis")
        print("  /market-research <description> - Run market-focused analysis")
        print("  /financial-model <budget>      - Run finance-focused analysis")
        print("  /risk-assessment <description> - Run risk-focused analysis")
        print("  /help                          - Show this help message")
        print("  /exit                          - Exit interactive mode")
        print()


def parse_comparables(value: str) -> list:
    """Parse comma-separated comparable titles from CLI input."""
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


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
        '--comparables',
        type=str,
        default='',
        help='Comma-separated comparable titles'
    )

    parser.add_argument(
        '--target-audience',
        type=str,
        default='general',
        help='Target demographic or audience segment'
    )
    
    parser.add_argument(
        '--interactive',
        action='store_true',
        help='Run in interactive mode'
    )

    parser.add_argument(
        '--sample',
        action='store_true',
        help='Run a deterministic no-key sample analysis'
    )
    
    args = parser.parse_args()
    
    print_config_summary()
    cli = GreenlightingCLI()
    
    if args.sample:
        await cli.analyze_sample()
    elif args.interactive or not args.project:
        # Interactive mode
        await cli.interactive_mode()
    else:
        # Direct analysis
        await cli.analyze_project(
            description=args.project,
            budget=args.budget,
            genre=args.genre,
            platform=args.platform,
            comparables=parse_comparables(args.comparables),
            target_audience=args.target_audience,
        )


if __name__ == "__main__":
    asyncio.run(main())
