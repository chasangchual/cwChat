import datetime
from datetime import datetime, timezone

class DateUtils:
    @classmethod
    def now_iso(cls) -> str:
        return datetime.now(timezone.utc).isoformat()