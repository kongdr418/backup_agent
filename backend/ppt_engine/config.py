"""Global configuration for the PPT SVG engine."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
BACKUP_AGENT_ROOT = PROJECT_ROOT.parent

# LLM API timeout settings (seconds)
LLM_CONNECT_TIMEOUT = 10.0
LLM_READ_TIMEOUT = 1800.0      # 30 min for DeepSeek reasoning models
LLM_WRITE_TIMEOUT = 30.0
LLM_POOL_TIMEOUT = 5.0

# Canvas format definitions
CANVAS_FORMATS = {
    "ppt169": {
        "name": "PPT 16:9",
        "width": 1280,
        "height": 720,
        "viewbox": "0 0 1280 720",
        "ratio": "16:9",
    },
    "ppt43": {
        "name": "PPT 4:3",
        "width": 1024,
        "height": 768,
        "viewbox": "0 0 1024 768",
        "ratio": "4:3",
    },
}

# Design color schemes
DESIGN_STYLES = {
    "academic": {
        "name": "Academic",
        "background": "#FFFFFF",
        "primary": "#1A365D",
        "accent": "#2B6CB0",
        "body_text": "#2D3748",
    },
    "education": {
        "name": "Education",
        "background": "#FFFFFF",
        "primary": "#2563EB",
        "accent": "#3B82F6",
        "body_text": "#1E293B",
    },
    "consulting": {
        "name": "Consulting",
        "background": "#FFFFFF",
        "primary": "#003A70",
        "accent": "#0077B6",
        "body_text": "#1A202C",
    },
    "tech": {
        "name": "Tech",
        "background": "#0F172A",
        "primary": "#3B82F6",
        "accent": "#06B6D4",
        "body_text": "#E2E8F0",
    },
    "general": {
        "name": "General",
        "background": "#FFFFFF",
        "primary": "#4F46E5",
        "accent": "#7C3AED",
        "body_text": "#374151",
    },
}

# Paths
ASSETS_DIR = PROJECT_ROOT / "assets"
WORKSPACES_DIR = BACKUP_AGENT_ROOT / "generated_svg_ppt"
ICONS_DIR = PROJECT_ROOT / "assets" / "icons"
REFERENCES_DIR = PROJECT_ROOT / "assets" / "references"

# LLM defaults
DEFAULT_LLM_PROVIDER = "deepseek"
DEFAULT_LLM_MODEL = "deepseek-v4-flash"


class _Settings:
    """Simple settings container matching source project's interface."""
    def __init__(self):
        self.icons_dir = ICONS_DIR
        self.assets_dir = ASSETS_DIR
        self.workspaces_dir = WORKSPACES_DIR
        self.references_dir = REFERENCES_DIR
        self.templates_dir = ASSETS_DIR / "templates"

settings = _Settings()


def get_deepseek_api_key() -> str | None:
    """Get DeepSeek API key from environment."""
    import os
    return os.environ.get("DEEPSEEK_API_KEY")


# SVG generation concurrency
SVG_MAX_CONCURRENCY = 4

# Visual Critic settings
VISUAL_CRITIC_ENABLED = False
VISUAL_CRITIC_MODEL = "deepseek-v4-pro"

# Deep Research settings
DEEP_RESEARCH_ENABLED = False
DEEP_RESEARCH_QUALITY_THRESHOLD = 28  # 7x5=35 满分
DEEP_RESEARCH_MAX_ATTEMPTS = 3
