"""
Utility helper functions for the Greenlighting Agent.
"""

from typing import Dict, Any, List
from datetime import datetime
from pathlib import Path
import json


def format_currency(amount: int) -> str:
    """Format number as currency."""
    if amount >= 1_000_000_000:
        return f"${amount / 1_000_000_000:.2f}B"
    elif amount >= 1_000_000:
        return f"${amount / 1_000_000:.1f}M"
    elif amount >= 1_000:
        return f"${amount / 1_000:.0f}K"
    else:
        return f"${amount:,}"


def calculate_roi_percentage(revenue: float, cost: float) -> float:
    """Calculate ROI as percentage."""
    if cost == 0:
        return 0.0
    return round(((revenue - cost) / cost) * 100, 2)


def get_timestamp() -> str:
    """Get current timestamp string."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def get_date_string() -> str:
    """Get current date as readable string."""
    return datetime.now().strftime("%B %d, %Y")


def save_json(data: Dict, filepath: Path):
    """Save dictionary to JSON file."""
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)


def load_json(filepath: Path) -> Dict:
    """Load JSON file to dictionary."""
    with open(filepath, 'r') as f:
        return json.load(f)


def sanitize_filename(name: str) -> str:
    """Sanitize string for use as filename."""
    # Remove invalid characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, '')
    # Replace spaces with underscores
    name = name.replace(' ', '_')
    # Limit length
    return name[:100]


def extract_project_name(description: str) -> str:
    """Extract a short project name from description."""
    # Take first 5 words
    words = description.split()[:5]
    name = ' '.join(words)
    if len(description.split()) > 5:
        name += '...'
    return name


def confidence_to_text(confidence: float) -> str:
    """Convert confidence score to text."""
    if confidence >= 0.9:
        return "Very High"
    elif confidence >= 0.75:
        return "High"
    elif confidence >= 0.6:
        return "Moderate"
    elif confidence >= 0.4:
        return "Low"
    else:
        return "Very Low"


def risk_score_to_color(score: float) -> str:
    """Convert risk score to color indicator."""
    if score < 3:
        return "🟢 Green"
    elif score < 5:
        return "🟡 Yellow"
    elif score < 7:
        return "🟠 Orange"
    else:
        return "🔴 Red"


def format_analysis_summary(results: Dict[str, Any]) -> str:
    """Format analysis results into readable summary."""
    summary_lines = []
    
    summary_lines.append("=" * 60)
    summary_lines.append("GREENLIGHTING ANALYSIS SUMMARY")
    summary_lines.append("=" * 60)
    summary_lines.append("")
    
    for agent_name, result in results.items():
        if isinstance(result, dict):
            summary_lines.append(f"\n📊 {agent_name}")
            summary_lines.append("-" * 60)
            confidence = result.get('confidence', 0)
            summary_lines.append(f"Confidence: {confidence_to_text(confidence)} ({confidence:.1%})")
            
            metadata = result.get('metadata', {})
            if metadata:
                summary_lines.append("\nKey Metrics:")
                for key, value in metadata.items():
                    summary_lines.append(f"  • {key}: {value}")
    
    summary_lines.append("\n" + "=" * 60)
    
    return "\n".join(summary_lines)


def create_progress_bar(current: int, total: int, width: int = 50) -> str:
    """Create a text progress bar."""
    filled = int(width * current / total)
    bar = "█" * filled + "░" * (width - filled)
    percentage = current / total * 100
    return f"[{bar}] {percentage:.0f}% ({current}/{total})"


def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text to max length with ellipsis."""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


class Colors:
    """ANSI color codes for terminal output."""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def print_header(text: str):
    """Print colored header."""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{text}{Colors.ENDC}\n")


def print_success(text: str):
    """Print success message."""
    print(f"{Colors.OKGREEN}✓ {text}{Colors.ENDC}")


def print_warning(text: str):
    """Print warning message."""
    print(f"{Colors.WARNING}⚠ {text}{Colors.ENDC}")


def print_error(text: str):
    """Print error message."""
    print(f"{Colors.FAIL}✗ {text}{Colors.ENDC}")


def print_info(text: str):
    """Print info message."""
    print(f"{Colors.OKCYAN}ℹ {text}{Colors.ENDC}")
