"""Tool modules, imported for their registration side effect.

Importing this package registers all six tools against the `MCPServer` instance
in `.._app`. `server.py` imports it for exactly that reason, and the re-exports
below are what let callers and tests reach a handler without knowing which
module it landed in.
"""

from __future__ import annotations

from .publication import gazette_get_publication
from .rubrics import gazette_list_rubrics
from .search import (
    gazette_search_detailed,
    gazette_search_procurement,
    gazette_search_publications,
)
from .status import gazette_source_status

__all__ = [
    "gazette_get_publication",
    "gazette_list_rubrics",
    "gazette_search_detailed",
    "gazette_search_procurement",
    "gazette_search_publications",
    "gazette_source_status",
]
