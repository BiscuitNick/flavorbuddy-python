from django.test import SimpleTestCase

from .views import (
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
