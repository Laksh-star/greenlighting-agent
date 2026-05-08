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
from tools.tmdb_tools import tmdb_client
from utils.helpers import (
    print_header, print_success, print_error, print_info, print_warning,
    sanitize_filename, extract_project_name, get_timestamp, format_currency
)
from utils.analysis_report import save_analysis_json
from utils.batch import (
    build_batch_summary_row,
    load_batch_projects,
    save_batch_summary,
)
from utils.report_quality import assert_report_quality
from utils.run_ledger import save_run_ledger
from utils.source_material import load_source_material


class GreenlightingCLI:
    """Command-line interface for the Greenlighting Agent."""
    
    def __init__(self, progress_callback=None):
        self.master_agent = MasterOrchestratorAgent(progress_callback=progress_callback)
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
        comparable_evidence: list = None,
        market_data_warning: str = "",
        comparable_source: str = "tmdb",
        private_dataset_id: str = "",
        financial_assumptions: Dict[str, Any] = None,
        source_material: Dict[str, Any] = None,
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
            'comparable_source': comparable_source,
            'private_dataset_id': private_dataset_id,
            'financial_assumptions': financial_assumptions or {},
        }
        if source_material:
            project_data["source_material"] = source_material
        if comparable_evidence is not None:
            project_data["comparable_evidence"] = comparable_evidence
        if market_data_warning:
            project_data["market_data_warning"] = market_data_warning
        requested_project_data = self._public_project_data(project_data)
        
        tmdb_client.reset_usage_metrics()

        # Run analysis
        results = await self.master_agent.analyze(project_data)
        results["requested_project_data"] = requested_project_data
        
        # Generate report
        report_path = self._save_report(results)
        ledger_path = save_run_ledger(results, report_path)
        results["run_ledger_path"] = str(ledger_path)
        analysis_json_path = save_analysis_json(results, report_path, ledger_path)
        results["analysis_json_path"] = str(analysis_json_path)
        results["report_path"] = str(report_path)
        
        # Display results
        self._display_results(results, report_path)
        
        return results

    async def analyze_sample(self) -> Dict[str, Any]:
        """Run the no-key deterministic sample project."""
        return await self.analyze_project(**SAMPLE_PROJECT)

    async def analyze_batch(self, csv_path: Path, sample: bool = False) -> Dict[str, Any]:
        """Run analysis for every project in a CSV batch."""
        projects = load_batch_projects(csv_path)
        rows = []

        print_header(f"📚 BATCH ANALYSIS STARTING ({len(projects)} PROJECTS)")
        for index, project in enumerate(projects, start=1):
            print_info(f"Batch project {index}/{len(projects)}")
            results = await self.analyze_project(
                **project,
                demo_mode=sample,
            )
            rows.append(build_batch_summary_row(results))

        summary_paths = save_batch_summary(rows)
        print_header("✅ BATCH ANALYSIS COMPLETE")
        print(f"📊 Batch CSV summary saved to: {summary_paths['csv_path']}")
        print(f"🧾 Batch JSON summary saved to: {summary_paths['json_path']}")
        return {
            "rows": rows,
            **summary_paths,
        }
    
    def _save_report(self, results: Dict[str, Any]) -> Path:
        """Save analysis report to file."""
        
        project_desc = results['project_data']['description']
        project_name = sanitize_filename(extract_project_name(project_desc))
        timestamp = get_timestamp()
        
        filename = f"{project_name}_{timestamp}.md"
        filepath = OUTPUT_DIR / filename
        
        # Format report
        report_content = self._format_report(results)
        quality = assert_report_quality(results, report_content)
        results["report_quality"] = quality
        for warning in quality.get("warnings", []):
            print_warning(f"Report quality warning: {warning}")
        
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

        source_material = project_data.get("source_material", {})
        if source_material:
            lines.append(f"**Source Material:** {source_material.get('name', 'provided')}")
        
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

        if source_material:
            lines.append("### Source Material Snapshot")
            lines.append("")
            lines.extend(self._format_source_material_snapshot(source_material))
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
            assumptions = financial_metrics.get("assumptions", {})
            if assumptions:
                lines.append("### Model Assumptions")
                lines.append("")
                lines.extend(self._format_model_assumptions(assumptions))
                lines.append("")

            lines.append("### Financial Scenario Snapshot")
            lines.append("")
            lines.extend(self._format_financial_metrics(financial_metrics))
            lines.append("")

            sensitivity = financial_metrics.get("sensitivity_table", [])
            if sensitivity:
                lines.append("### Sensitivity Table")
                lines.append("")
                lines.extend(self._format_sensitivity_table(sensitivity))
                lines.append("")

            scenario_comparison = self._get_scenario_comparison(results)
            if scenario_comparison:
                lines.append("### Scenario Comparison")
                lines.append("")
                lines.extend(self._format_scenario_comparison(scenario_comparison))
                lines.append("")

            lines.append("### Break-even Analysis")
            lines.append("")
            lines.extend(self._format_break_even(financial_metrics))
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

    def _public_project_data(self, project_data: Dict[str, Any]) -> Dict[str, Any]:
        public_data = dict(project_data)
        source_material = public_data.get("source_material")
        if source_material:
            public_data["source_material"] = {
                "name": source_material.get("name", ""),
                "excerpt": source_material.get("excerpt", ""),
                "word_count": source_material.get("word_count", 0),
                "character_count": source_material.get("character_count", 0),
                "line_count": source_material.get("line_count", 0),
            }
        return public_data

    def _get_comparable_evidence(self, results: Dict[str, Any]) -> list:
        return self._get_agent_metadata(results, "market_research").get("comparable_evidence", [])

    def _get_financial_metrics(self, results: Dict[str, Any]) -> Dict[str, Any]:
        return self._get_agent_metadata(results, "financial_model").get("basic_metrics", {})

    def _get_scenario_comparison(self, results: Dict[str, Any]) -> list:
        return self._get_agent_metadata(results, "financial_model").get("scenario_comparison", [])

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
                    f"gross revenue, {metrics.get(roi_key, 0)}% net ROI"
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

    def _format_model_assumptions(self, assumptions: Dict[str, Any]) -> list:
        return [
            f"- **Marketing / P&A:** {format_currency(assumptions.get('marketing_spend', 0))}",
            f"- **Distribution fee:** {assumptions.get('distribution_fee_pct', 0) * 100:.1f}%",
            f"- **Theatrical revenue share:** {assumptions.get('theatrical_revenue_share', 0) * 100:.1f}%",
            f"- **Streaming/license value:** {format_currency(assumptions.get('streaming_license_value', 0))}",
            f"- **Risk tolerance:** {assumptions.get('risk_tolerance', 'balanced')}",
        ]

    def _format_sensitivity_table(self, rows: list) -> list:
        has_subscribers = any("subscribers" in row for row in rows)
        if has_subscribers:
            lines = [
                "| Scenario | Subscribers | Net Revenue | ROI |",
                "| --- | ---: | ---: | ---: |",
            ]
            for row in rows:
                lines.append(
                    f"| {row.get('scenario', 'n/a')} | "
                    f"{row.get('subscribers', 0):,} | "
                    f"{format_currency(row.get('net_revenue', 0) or 0)} | "
                    f"{row.get('roi', 0)}% |"
                )
            return lines

        lines = [
            "| Scenario | Gross Revenue | Net Revenue | ROI |",
            "| --- | ---: | ---: | ---: |",
        ]
        for row in rows:
            lines.append(
                f"| {row.get('scenario', 'n/a')} | "
                f"{format_currency(row.get('gross_revenue', 0) or 0)} | "
                f"{format_currency(row.get('net_revenue', 0) or 0)} | "
                f"{row.get('roi', 0)}% |"
            )
        return lines

    def _format_scenario_comparison(self, rows: list) -> list:
        has_subscribers = any("break_even_subscribers" in row for row in rows)
        if has_subscribers:
            lines = [
                "| Case | Risk Tolerance | Exposure | Break-even Subs | Base Subs | Base Net | Base ROI |",
                "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
            ]
            for row in rows:
                lines.append(
                    f"| {row.get('case', 'n/a')} | "
                    f"{row.get('risk_tolerance', 'n/a')} | "
                    f"{format_currency(row.get('total_exposure', 0) or 0)} | "
                    f"{row.get('break_even_subscribers', 0):,} | "
                    f"{row.get('base_subscribers', 0):,} | "
                    f"{format_currency(row.get('base_net_revenue', 0) or 0)} | "
                    f"{row.get('base_roi', 0)}% |"
                )
            return lines

        lines = [
            "| Case | Risk Tolerance | Exposure | Break-even Gross | Base Gross | Base Net | Base ROI |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
        ]
        for row in rows:
            lines.append(
                f"| {row.get('case', 'n/a')} | "
                f"{row.get('risk_tolerance', 'n/a')} | "
                f"{format_currency(row.get('total_exposure', 0) or 0)} | "
                f"{format_currency(row.get('break_even_revenue', 0) or 0)} | "
                f"{format_currency(row.get('base_gross_revenue', 0) or 0)} | "
                f"{format_currency(row.get('base_net_revenue', 0) or 0)} | "
                f"{row.get('base_roi', 0)}% |"
            )
        return lines

    def _format_break_even(self, metrics: Dict[str, Any]) -> list:
        rows = []
        if metrics.get("total_exposure") is not None:
            rows.append(f"- **Total exposure:** {format_currency(metrics.get('total_exposure', 0))}")
        if metrics.get("break_even_revenue") is not None:
            rows.append(f"- **Break-even gross revenue:** {format_currency(metrics.get('break_even_revenue', 0))}")
        if metrics.get("break_even_subscribers") is not None:
            rows.append(f"- **Break-even subscribers:** {metrics.get('break_even_subscribers', 0):,}")
        thresholds = metrics.get("decision_thresholds", {})
        if thresholds:
            rows.append(
                "- **Decision thresholds:** "
                f"GO at {thresholds.get('go_roi')}% ROI, "
                f"CONDITIONAL GO at {thresholds.get('conditional_roi')}% ROI"
            )
        if not rows:
            rows.append("- Break-even calculation unavailable.")
        return rows

    def _format_source_material_snapshot(self, source_material: Dict[str, Any]) -> list:
        excerpt = source_material.get("excerpt", "")
        first_line = next((line.strip() for line in excerpt.splitlines() if line.strip()), "")
        return [
            f"- **File/name:** {source_material.get('name', 'source material')}",
            f"- **Words:** {source_material.get('word_count', 0):,}",
            f"- **Characters:** {source_material.get('character_count', 0):,}",
            f"- **Opening signal:** {first_line[:240] or 'n/a'}",
        ]

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
        if results.get("analysis_json_path"):
            print(f"🧾 Structured JSON saved to: {results['analysis_json_path']}")
        if results.get("run_ledger_path"):
            print(f"📒 Run ledger saved to: {results['run_ledger_path']}")
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
        '--batch',
        type=str,
        help='CSV file with project rows to analyze'
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
        '--source-file',
        type=str,
        default='',
        help='Plain text or Markdown treatment/script file to include in analysis'
    )

    parser.add_argument('--marketing-spend', type=int, default=0, help='Marketing/P&A spend in dollars')
    parser.add_argument('--distribution-fee-pct', type=float, default=0.12, help='Distribution fee as decimal, e.g. 0.12')
    parser.add_argument('--theatrical-revenue-share', type=float, default=0.5, help='Theatrical revenue share as decimal')
    parser.add_argument('--streaming-license-value', type=int, default=0, help='Streaming/license value in dollars')
    parser.add_argument('--subscriber-lifetime-value', type=int, default=120, help='Subscriber lifetime value for streaming model')
    parser.add_argument('--downside-revenue-multiplier', type=float, default=0, help='Override downside gross revenue multiple')
    parser.add_argument('--base-revenue-multiplier', type=float, default=0, help='Override base gross revenue multiple')
    parser.add_argument('--upside-revenue-multiplier', type=float, default=0, help='Override upside gross revenue multiple')
    parser.add_argument(
        '--risk-tolerance',
        type=str,
        default='balanced',
        choices=['conservative', 'balanced', 'aggressive'],
        help='Financial decision threshold profile'
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
    
    if args.batch:
        await cli.analyze_batch(Path(args.batch), sample=args.sample)
    elif args.sample:
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
            financial_assumptions={
                "marketing_spend": args.marketing_spend,
                "distribution_fee_pct": args.distribution_fee_pct,
                "theatrical_revenue_share": args.theatrical_revenue_share,
                "streaming_license_value": args.streaming_license_value,
                "subscriber_lifetime_value": args.subscriber_lifetime_value,
                "downside_revenue_multiplier": args.downside_revenue_multiplier,
                "base_revenue_multiplier": args.base_revenue_multiplier,
                "upside_revenue_multiplier": args.upside_revenue_multiplier,
                "risk_tolerance": args.risk_tolerance,
            },
            source_material=load_source_material(Path(args.source_file)) if args.source_file else None,
        )


if __name__ == "__main__":
    asyncio.run(main())
