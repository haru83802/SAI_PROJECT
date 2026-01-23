from sklearn.metrics.pairwise import cosine_similarity

def is_repeat(embedder, memory_texts, user_input, threshold=0.88):
    if not memory_texts:
        return False

    vec = embedder.encode([user_input])
    for past in memory_texts[-5:]:
        pvec = embedder.encode([past])
        sim = cosine_similarity(vec, pvec)[0][0]
        if sim > threshold:
            return True
    return False
