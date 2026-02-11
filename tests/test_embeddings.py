import pytest

from patent_mvp.embeddings import SentenceTransformerProvider


def test_embedding_dimension_validation_error_message() -> None:
    provider = SentenceTransformerProvider.__new__(SentenceTransformerProvider)
    provider.model_name = "test-model"
    with pytest.raises(ValueError, match=r"vector\(768\)"):
        provider._validate_dimension(1024)
