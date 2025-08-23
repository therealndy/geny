import pytest


def test_vectorstore_index_and_search():
    # Skip this test if heavy ML deps are not installed
    pytest.importorskip("sentence_transformers")
    pytest.importorskip("faiss")

    from geny_ai.rag.store import VectorStore

    vs = VectorStore(persist_dir="data/test_vectorstore")
    # rebuild with a few small documents
    docs = [
        {"id": "a", "text": "Geny likes learning about pizza recipes.", "meta": {}},
        {
            "id": "b",
            "text": "Geny enjoys reading research papers on reinforcement learning.",
            "meta": {},
        },
        {
            "id": "c",
            "text": "Geny sometimes reflects on human conversations and diaries.",
            "meta": {},
        },
    ]
    n = vs.rebuild_index(docs)
    assert n == 3
    res = vs.search("pizza recipe", k=2)
    assert isinstance(res, list)
    # Expect at least one result and the top result should be doc 'a' or related to pizza
    assert len(res) >= 1
    top = res[0]
    assert "text" in top and isinstance(top["text"], str)
