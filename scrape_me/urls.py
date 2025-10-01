from django.urls import path

from .views import convert_raw_recipe, get_recipes, home, parse_recipe_url, test_scrape

urlpatterns = [
    path("", home, name="home"),
    path("test-example", test_scrape, name="test-example"),
    path("parse-recipe-url", parse_recipe_url, name="parse-recipe-url"),
    path("get-recipes", get_recipes, name="get-recipes"),
    path("convert-raw-recipe", convert_raw_recipe, name="convert-raw-recipe"),
]
