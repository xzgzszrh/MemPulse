"""A single application facade for all transports. No silent fallback store."""

from .service import TopicFacade

MemoryFacade = TopicFacade


def get_facade(db_path=None, user_id="default", **kwargs):
    return TopicFacade(db_path, user_id=user_id, **kwargs)
