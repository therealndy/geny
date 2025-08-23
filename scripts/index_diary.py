from geny.geny_brain import GenyBrain
from geny_ai.rag.store import VectorStore

brain = GenyBrain()
vs = VectorStore()

w = brain.memory.get("world", {})
diary = list(w.get("diary", []))
docs = []
for d in diary:
    ts = (
        d.get("date")
        or d.get("meta", {}).get("since_real")
        or d.get("meta", {}).get("virtual", {}).get("now_real")
    )
    docs.append(
        {
            "id": ts or str(len(docs)),
            "text": d.get("entry", ""),
            "meta": {"insight": d.get("insight")},
        }
    )

print("Indexing", len(docs), "diary items...")
count = vs.rebuild_index(docs)
print("Indexed:", count)
