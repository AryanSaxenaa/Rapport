"""Tests for entity extraction and model configuration."""

import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from entity_extractor import _EXTRACTION_MODELS, _EMPTY_EXTRACTION


class TestModelConfig(unittest.TestCase):
    """Verify the model configuration env var parsing."""

    def test_default_models(self):
        models = _EXTRACTION_MODELS
        self.assertEqual(len(models), 2)
        self.assertEqual(models[0], "openrouter/owl-alpha")
        self.assertEqual(models[1], "poolside/laguna-m.1:free")

    def test_custom_single_model(self):
        os.environ["EXTRACTION_MODEL"] = "openai/gpt-4o"
        import importlib
        import entity_extractor
        importlib.reload(entity_extractor)
        models = entity_extractor._EXTRACTION_MODELS
        self.assertEqual(len(models), 1)
        self.assertEqual(models[0], "openai/gpt-4o")
        del os.environ["EXTRACTION_MODEL"]

    def test_custom_multi_model(self):
        os.environ["EXTRACTION_MODEL"] = "model-a, model-b ,  model-c  "
        import importlib
        import entity_extractor
        importlib.reload(entity_extractor)
        models = entity_extractor._EXTRACTION_MODELS
        self.assertEqual(len(models), 3)
        self.assertEqual(models, ["model-a", "model-b", "model-c"])
        del os.environ["EXTRACTION_MODEL"]


class TestEmptyExtraction(unittest.TestCase):
    """Verify the empty extraction return value shape."""

    def test_returns_dict(self):
        self.assertIsInstance(_EMPTY_EXTRACTION, dict)

    def test_has_expected_keys(self):
        expected_keys = {
            "people", "companies", "topics", "commitments",
            "relations", "unresolved", "stance", "sentiment_shift", "summary",
        }
        self.assertTrue(expected_keys.issubset(_EMPTY_EXTRACTION.keys()))

    def test_empty_stance_is_neutral(self):
        self.assertEqual(_EMPTY_EXTRACTION["stance"], "neutral")

    def test_empty_summary_is_empty(self):
        self.assertEqual(_EMPTY_EXTRACTION["summary"], "")


class TestExtractEntities(unittest.IsolatedAsyncioTestCase):
    """Verify the async extraction function with mocked HTTP."""

    @mock.patch("entity_extractor.httpx.AsyncClient")
    async def test_mocked_extraction(self, mock_client):
        os.environ["OPENROUTER_API_KEY"] = "test-api-key"
        import importlib
        import entity_extractor
        importlib.reload(entity_extractor)

        expected_content = json.dumps({
            "people": [{"name": "Mira Voss"}],
            "companies": ["Acme Corp"],
            "topics": ["security", "rollout"],
            "commitments": [],
            "relations": [],
            "unresolved": [],
            "stance": "skeptic",
            "sentiment_shift": None,
            "summary": "Mira expressed security concerns."
        })

        mock_response = mock.MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": expected_content}}]
        }
        mock_client.return_value.__aenter__.return_value.post.return_value = mock_response

        result = await entity_extractor.extract_entities("Mira is worried about security.")
        self.assertEqual(result["stance"], "skeptic")
        self.assertEqual(result["people"][0]["name"], "Mira Voss")
        del os.environ["OPENROUTER_API_KEY"]

    async def test_no_api_key_returns_empty(self):
        os.environ.pop("OPENROUTER_API_KEY", None)
        import importlib
        import entity_extractor
        importlib.reload(entity_extractor)
        result = await entity_extractor.extract_entities("Test transcript")
        self.assertEqual(result["stance"], "neutral")
        self.assertEqual(result["topics"], [])

    async def test_empty_text_returns_empty(self):
        os.environ["OPENROUTER_API_KEY"] = "test-key"
        import importlib
        import entity_extractor
        importlib.reload(entity_extractor)
        result = await entity_extractor.extract_entities("")
        self.assertEqual(result["stance"], "neutral")
        self.assertEqual(result["summary"], "")
        del os.environ["OPENROUTER_API_KEY"]


if __name__ == "__main__":
    unittest.main()
