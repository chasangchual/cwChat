from typing import Optional, Dict, List
from dataclasses import dataclass, asdict

@dataclass
class ChatMessage:
    role: str
    content: str
    at: str
    meta: Optional[Dict[str, any]] = None

MemoryStore: Dict[str, List[ChatMessage]] = {}