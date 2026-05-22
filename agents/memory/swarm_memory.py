"""RAG vector memory — stores trade setups in ChromaDB and retrieves similar past trades before each decision."""

import json
import os
import uuid
from typing import List, Dict

from dotenv import load_dotenv

load_dotenv()

_PERSIST_DIR = os.path.join(os.path.dirname(__file__), "lessons")
_COLLECTION_NAME = "ace_trades"

_client = None
_collection = None


def _get_collection():
    """Lazy-initialise ChromaDB persistent client and collection."""
    global _client, _collection
    if _collection is None:
        import chromadb
        _client = chromadb.PersistentClient(path=_PERSIST_DIR)
        _collection = _client.get_or_create_collection(
            name=_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def _build_document(trade: dict) -> str:
    """Serialise a trade dict into a searchable text document."""
    return (
        f"pair={trade.get('pair','?')} "
        f"session={trade.get('session','?')} "
        f"confluence={trade.get('confluence_score','?')} "
        f"amd_phase={trade.get('amd_phase','?')} "
        f"entry={trade.get('entry_price','?')} "
        f"exit={trade.get('exit_price','?')} "
        f"pnl_pct={trade.get('pnl_pct','?')} "
        f"win={trade.get('win','?')} "
        f"setup={trade.get('setup_description','')}"
    )


def store_trade(trade_result: dict) -> None:
    """
    Store a completed trade in the vector database.

    trade_result must contain: pair, session, confluence_score, amd_phase,
    entry_price, exit_price, pnl, pnl_pct, win, setup_description, timestamp.
    """
    try:
        col = _get_collection()
        doc_id = trade_result.get("trade_id", str(uuid.uuid4()))
        document = _build_document(trade_result)
        metadata = {
            k: str(v)
            for k, v in trade_result.items()
            if isinstance(v, (str, int, float, bool))
        }
        col.upsert(documents=[document], metadatas=[metadata], ids=[doc_id])
    except Exception as exc:
        import logging
        logging.getLogger(__name__).error("swarm_memory store_trade failed: %s", exc)


def retrieve_similar(setup: dict, n: int = 5) -> List[Dict]:
    """
    Query ChromaDB for the n most similar past setups to the current one.

    setup should contain: pair, session, confluence_score, amd_phase, setup_description.
    Returns list of trade dicts (up to n), empty list on any error.
    """
    try:
        col = _get_collection()
        if col.count() == 0:
            return []
        query_text = _build_document(setup)
        results = col.query(query_texts=[query_text], n_results=min(n, col.count()))
        trades = []
        for i, metadata in enumerate(results.get("metadatas", [[]])[0]):
            trade = dict(metadata)
            # Convert numeric strings back
            for key in ("confluence_score", "entry_price", "exit_price", "pnl", "pnl_pct"):
                if key in trade:
                    try:
                        trade[key] = float(trade[key])
                    except (ValueError, TypeError):
                        pass
            if "win" in trade:
                trade["win"] = trade["win"].lower() == "true"
            trades.append(trade)
        return trades
    except Exception as exc:
        import logging
        logging.getLogger(__name__).error("swarm_memory retrieve_similar failed: %s", exc)
        return []


def get_session_stats(session: str) -> dict:
    """
    Return win rate, average P&L, and trade count for a given session name.
    Returns empty stats dict on any error.
    """
    try:
        col = _get_collection()
        if col.count() == 0:
            return {"session": session, "trade_count": 0, "win_rate": 0.0, "avg_pnl_pct": 0.0}

        results = col.get(where={"session": session}, include=["metadatas"])
        trades = results.get("metadatas", [])

        if not trades:
            return {"session": session, "trade_count": 0, "win_rate": 0.0, "avg_pnl_pct": 0.0}

        wins = sum(1 for t in trades if str(t.get("win", "false")).lower() == "true")
        pnls = []
        for t in trades:
            try:
                pnls.append(float(t.get("pnl_pct", 0)))
            except (ValueError, TypeError):
                pass

        return {
            "session": session,
            "trade_count": len(trades),
            "win_rate": round(wins / len(trades) * 100, 1),
            "avg_pnl_pct": round(sum(pnls) / len(pnls), 2) if pnls else 0.0,
        }
    except Exception as exc:
        import logging
        logging.getLogger(__name__).error("swarm_memory get_session_stats failed: %s", exc)
        return {"session": session, "trade_count": 0, "win_rate": 0.0, "avg_pnl_pct": 0.0}
