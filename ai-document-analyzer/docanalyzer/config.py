"""Central configuration. Change defaults here, not in the UI code."""

from pathlib import Path

APP_NAME = "AI Document Analyzer"
APP_ICON = "🧠"

# Where chat history is stored (git-ignored).
DATA_DIR = Path("chat_history")

# Friendly name -> Anthropic model ID.
MODELS = {
    "Claude Sonnet 5.5 (balanced)": "claude-sonnet-5-5",
    "Claude Haiku 5.5 (fast, cheap)": "claude-haiku-5-5",
    "Claude Opus 5.5 (most capable)": "claude-opus-5-5",
}
DEFAULT_MODEL = "Claude Sonnet 5.5 (balanced)"

SUPPORTED_TYPES = ["pdf", "docx", "xlsx", "xls", "csv"]

# Roughly 4 characters per token. Above this budget we switch to map-reduce.
MAX_DIRECT_TOKENS = 120_000
CHUNK_CHARS = 25_000
CHUNK_OVERLAP = 1_000

# Excel sheets bigger than this are summarised instead of dumped in full.
EXCEL_FULL_DUMP_ROWS = 50
EXCEL_FULL_DUMP_COLS = 30

MAX_ANSWER_TOKENS = 4096
MAX_MAP_TOKENS = 1024
HISTORY_TURNS = 6  # previous messages sent back to the model for follow-ups

SYSTEM_PROMPT = (
    "You are a careful document analyst. Answer only from the supplied documents. "
    "Quote figures exactly, name the file (and page or sheet) your answer comes from, "
    "use tables or lists when they make the answer clearer, and say plainly when the "
    "documents do not contain the answer."
)
