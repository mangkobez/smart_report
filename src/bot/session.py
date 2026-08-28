from dataclasses import dataclass, field
from datetime import date
from PIL import Image


@dataclass
class Session:
    photos: list[Image.Image] = field(default_factory=list)
    scan_docs: list[bytes] = field(default_factory=list)  # PDF bytes dari scan surat
    title: str = ""
    location: str | None = None
    event_date: date = field(default_factory=date.today)
    job: object = None  # asyncio job handle (JobQueue)


_store: dict[int, Session] = {}


def get(chat_id: int) -> Session:
    if chat_id not in _store:
        _store[chat_id] = Session()
    return _store[chat_id]


def clear(chat_id: int) -> None:
    _store.pop(chat_id, None)


def has_photos(chat_id: int) -> bool:
    return chat_id in _store and bool(_store[chat_id].photos)
