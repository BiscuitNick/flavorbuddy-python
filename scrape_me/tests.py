from django.test import SimpleTestCase

from .views import normalize_instructions, normalize_recipe_url


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
