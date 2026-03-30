from unittest.mock import patch


def test_load_model_caches_by_model_name():
    import beyin.embedder as embedder

    embedder._MODEL_CACHE.clear()

    created = []

    class FakeTextEmbedding:
        def __init__(self, model_name: str):
            created.append(model_name)
            self.model_name = model_name

        def embed(self, items):
            return [[0.0] for _ in items]

    with patch("fastembed.TextEmbedding", FakeTextEmbedding):
        first = embedder.load_model("all-MiniLM-L6-v2")
        second = embedder.load_model("all-MiniLM-L6-v2")
        third = embedder.load_model("other-model")

    assert first is second
    assert first is not third
    assert created == [
        "sentence-transformers/all-MiniLM-L6-v2",
        "other-model",
    ]
