from recipe_scrapers import scrape_me

scraper = scrape_me("https://www.allrecipes.com/recipe/16954/chinese-chicken-fried-rice-ii/")
print(scraper.title())
print(scraper.instructions())
print(scraper.to_json())


# for a complete list of methods:
# help(scraper)