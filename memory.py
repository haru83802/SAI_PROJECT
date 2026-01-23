import faiss
from sentence_transformers import SentenceTransformer

class MemoryStore:
    def __init__(self, dim=384):
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        self.index = faiss.IndexFlatL2(dim)
        self.texts = []

    def add(self, text: str):
        vec = self.model.encode([text]).astype("float32")
        self.index.add(vec)
        self.texts.append(text)

    def search(self, query: str, k=3) -> str:
        if not self.texts:
            return ""
        qvec = self.model.encode([query]).astype("float32")
        _, idx = self.index.search(qvec, k)
        return "\n".join(
            self.texts[i]
            for i in idx[0]
            if i < len(self.texts)
        )
