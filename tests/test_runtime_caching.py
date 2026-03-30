from unittest.mock import patch


def test_load_model_caches_by_model_name():
    import beyin.embedder as embedder

    embedder.SentenceTransformer = None
    embedder._MODEL_CACHE.clear()

    created = []

    class FakeSentenceTransformer:
        def __init__(self, model_name: str):
            created.append(model_name)
            self.model_name = model_name

    with patch("sentence_transformers.SentenceTransformer", FakeSentenceTransformer):
        first = embedder.load_model("all-MiniLM-L6-v2")
        second = embedder.load_model("all-MiniLM-L6-v2")
        third = embedder.load_model("other-model")

    assert first is second
    assert first is not third
    assert created == ["all-MiniLM-L6-v2", "other-model"]
