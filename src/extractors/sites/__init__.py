"""Site specific extraction overrides."""
from __future__ import annotations

from typing import Callable, Dict, Optional

from . import coindesk, cointelegraph

ExtractorFunc = Callable[[str], Dict[str, Optional[str]]]

SITE_EXTRACTORS: Dict[str, ExtractorFunc] = {
    "coindesk": coindesk.extract,
    "cointelegraph": cointelegraph.extract,
}


def get_extractor(source: str) -> Optional[ExtractorFunc]:
    return SITE_EXTRACTORS.get(source)
