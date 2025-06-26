from typing import Any, Optional


class NorthResult(dict):
    def __init__(self, value: Any, *, title: Optional[str] = None, content: Optional[str] = None):
        super().__init__()
        self["result"] = value

        meta = {}
        if title is not None:
            meta["title"] = title
        if content is not None:
            meta["content"] = content

        if len(meta.keys()) > 0:
            self["_north_metadata"] = meta
