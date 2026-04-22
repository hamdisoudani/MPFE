"""BaseStore — InMemoryStore stub for now, PostgresStore later.

Namespaces: ("scrapes", url_hash), ("serper", query_hash).
"""
from langgraph.store.memory import InMemoryStore

_store = InMemoryStore()

def get_store():
    return _store
