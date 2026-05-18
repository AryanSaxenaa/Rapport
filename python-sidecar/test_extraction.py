"""Tests for entity extraction and model configuration."""

import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from entity_extractor import fallback_extraction, extract_entities, _EXTRACTION_MODELS


class TestModelConfig(unittest.TestCase):
    """Verify the model configuration env var parsing."""

    def test_default_models(self):
        """Default should parse to a list of two models."""
        models = _EXTRACTION_MODELS
        self.assertEqual(len(models), 2)
        self.assertEqual(models[0], "openrouter/owl-alpha")
        self.assertEqual(models[1], "poolside/laguna-m.1:free")

    def test_custom_single_model(self):
        """Single model env var should produce a list of one."""
        os.environ["EXTRACTION_MODEL"] = "openai/gpt-4o"
        # Reimport to pick up new env var
        import importlib
        import entity_extractor
        importlib.reload(entity_extractor)
        models = entity_extractor._EXTRACTION_MODELS
        self.assertEqual(len(models), 1)
        self.assertEqual(models[0], "openai/gpt-4o")
        del os.environ["EXTRACTION_MODEL"]

    def test_custom_multi_model(self):
        """Multi-model env var should parse all entries."""
        os.environ["EXTRACTION_MODEL"] = "model-a, model-b ,  model-c  "
        import importlib
        import entity_extractor
        importlib.reload(entity_extractor)
        models = entity_extractor._EXTRACTION_MODELS
        self.assertEqual(len(models), 3)
        self.assertEqual(models, ["model-a", "model-b", "model-c"])
        del os.environ["EXTRACTION_MODEL"]


class TestFallbackExtraction(unittest.TestCase):
    """Verify fallback extraction returns correct schema."""

    def test_returns_dict(self):
        result = fallback_extraction("Test transcript")
        self.assertIsInstance(result, dict)

    def test_has_expected_keys(self):
        result = fallback_extraction("Test transcript")
        expected_keys = {"people", "companies", "topics", "commitments",
                         "stance", "sentiment_shift", "summary"}
        self.assertTrue(expected_keys.issubset(result.keys()))

    def test_fallback_stance_is_neutral(self):
        result = fallback_extraction("Test transcript")
        self.assertEqual(result["stance"], "neutral")

    def test_fallback_summary_truncates(self):
        long_text = "Hello world! " * 200
        result = fallback_extraction(long_text)
        self.assertLessEqual(len(result["summary"]), 500)
        self.assertIn("Hello", result["summary"])

    def test_empty_text_returns_not_none(self):
        result = fallback_extraction("")
        self.assertIsNotNone(result)
        self.assertEqual(result["summary"], "No transcript content available.")

    def test_whitespace_text_returns_fallback(self):
        result = fallback_extraction("   ")
        self.assertIsNotNone(result)
        self.assertEqual(result["summary"], "No transcript content available.")


class TestExtractEntities(unittest.IsolatedAsyncioTestCase):
    """Verify the async extraction function with mocked HTTP."""

    @mock.patch("entity_extractor.httpx.AsyncClient")
    async def test_mocked_extraction(self, mock_client):
        """With API key and a mocked response, extraction should parse JSON."""
        os.environ["OPENROUTER_API_KEY"] = "test-api-key"
        import importlib
        import entity_extractor
        importlib.reload(entity_extractor)

        expected_content = json.dumps({
            "people": [{"name": "Mira Voss"}],
            "companies": ["Acme Corp"],
            "topics": ["security", "rollout"],
            "commitments": [],
            "stance": "skeptic",
            "sentiment_shift": None,
            "summary": "Mira expressed security concerns."
        })

        # Use MagicMock (not AsyncMock) so response.json() is synchronous
        mock_response = mock.MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": expected_content}}]
        }
        mock_client.return_value.__aenter__.return_value.post.return_value = mock_response

        result = await entity_extractor.extract_entities("Mira is worried about security.")
        self.assertEqual(result["stance"], "skeptic")
        self.assertEqual(result["people"][0]["name"], "Mira Voss")
        del os.environ["OPENROUTER_API_KEY"]

    async def test_no_api_key_falls_back(self):
        """Without API key, extraction should return fallback."""
        os.environ.pop("OPENROUTER_API_KEY", None)
        import importlib
        import entity_extractor
        importlib.reload(entity_extractor)
        result = await entity_extractor.extract_entities("Test transcript")
        self.assertEqual(result["stance"], "neutral")
        self.assertIn("security", result["topics"])

    async def test_empty_text_falls_back(self):
        """Empty text should immediately return fallback."""
        os.environ["OPENROUTER_API_KEY"] = "test-key"
        import importlib
        import entity_extractor
        importlib.reload(entity_extractor)
        result = await entity_extractor.extract_entities("")
        self.assertEqual(result["stance"], "neutral")
        del os.environ["OPENROUTER_API_KEY"]


if __name__ == "__main__":
    unittest.main()
