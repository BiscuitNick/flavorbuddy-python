import json
from unittest.mock import patch

from django.test import SimpleTestCase
from django.urls import reverse

from .views import (
    RecipeStructError,
    normalize_description,
    normalize_instructions,
    normalize_recipe_url,
)


class NormalizeRecipeUrlTests(SimpleTestCase):
    def test_trailing_slash_removed(self):
        self.assertEqual(
            normalize_recipe_url("https://example.com/recipe/"),
            "https://example.com/recipe",
        )

    def test_multiple_trailing_slashes_removed(self):
        self.assertEqual(
            normalize_recipe_url("https://example.com/recipe//"),
            "https://example.com/recipe",
        )

    def test_url_without_trailing_slash_unchanged(self):
        self.assertEqual(
            normalize_recipe_url("https://example.com/recipe"),
            "https://example.com/recipe",
        )

    def test_whitespace_trimmed(self):
        self.assertEqual(
            normalize_recipe_url("  https://example.com/recipe/  "),
            "https://example.com/recipe",
        )


class NormalizeInstructionsTests(SimpleTestCase):
    def test_string_with_newlines_split_into_steps(self):
        instructions = "Step one.\nStep two.\n\nStep three."
        self.assertEqual(
            normalize_instructions(instructions),
            ["Step one.", "Step two.", "Step three."],
        )

    def test_list_of_steps_trimmed(self):
        self.assertEqual(
            normalize_instructions(["  First  ", "Second", ""]),
            ["First", "Second"],
        )

    def test_empty_payload_returns_empty_list(self):
        self.assertEqual(normalize_instructions(None), [])
        self.assertEqual(normalize_instructions(""), [])

    def test_string_without_newlines_preserved(self):
        self.assertEqual(
            normalize_instructions("Single step"),
            ["Single step"],
        )


class NormalizeDescriptionTests(SimpleTestCase):
    def test_string_description_trimmed(self):
        self.assertEqual(
            normalize_description("  Tasty pasta with pesto.  "),
            "Tasty pasta with pesto.",
        )

    def test_list_description_joined(self):
        self.assertEqual(
            normalize_description([" First line. ", "Second line.", ""]),
            "First line. Second line.",
        )

    def test_dict_description_uses_text_field(self):
        self.assertEqual(
            normalize_description({"text": "  Rich chocolate cake.  "}),
            "Rich chocolate cake.",
        )

    def test_nested_items_flattened(self):
        payload = [
            {"text": "Layered dessert"},
            ["Creamy filling"],
        ]
        self.assertEqual(
            normalize_description(payload),
            "Layered dessert Creamy filling",
        )

    def test_empty_description_returns_blank(self):
        self.assertEqual(normalize_description(None), "")
        self.assertEqual(normalize_description([]), "")


class ConvertRawRecipeViewTests(SimpleTestCase):
    def test_invalid_json_body_returns_400(self):
        response = self.client.post(
            reverse("convert-raw-recipe"),
            data="not-json",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_missing_raw_text_returns_400(self):
        response = self.client.post(
            reverse("convert-raw-recipe"),
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"error": "Field 'raw_text' is required."})

    @patch("scrape_me.views._invoke_recipe_struct_model")
    def test_successful_conversion_returns_payload(self, mock_invoke):
        mock_invoke.return_value = {"title": "Example", "id": None}

        payload = {
            "raw_text": "Some recipe text",
            "source_url": "https://example.com",
        }

        response = self.client.post(
            reverse("convert-raw-recipe"),
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"title": "Example", "id": None})
        mock_invoke.assert_called_once_with("https://example.com", "Some recipe text")

    @patch("scrape_me.views._invoke_recipe_struct_model")
    def test_service_error_returns_502(self, mock_invoke):
        mock_invoke.side_effect = RecipeStructError("Upstream error")

        response = self.client.post(
            reverse("convert-raw-recipe"),
            data=json.dumps({"raw_text": "text"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json(), {"error": "Upstream error"})
