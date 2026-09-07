import io
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.storage import storages
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from scrape_me.models import Recipe, StarterRecipe


class ImageStorageTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'pix'
        self.source.mkdir()
        Image.new('RGB', (50, 30), 'red').save(self.source / 'test.webp', 'WEBP')
        self.content = {'title': 'Test', 'ingredients': ['Salt'], 'instructions': ['Mix'],
                        'source_url': 'https://publicdomainrecipes.com/test/',
                        'image': 'https://publicdomainrecipes.com/pix/test.webp'}
        self.provenance = {'repository': 'https://github.com/ronaldl29/public-domain-recipes',
                           'license': 'Unlicense', 'revision': 'fixture'}
        self.starter = StarterRecipe.objects.create(slug='test', title='Test',
                            content=self.content, provenance=self.provenance)
        directory = self.root / 'data/starter'
        directory.mkdir(parents=True)
        self.catalog = directory / 'public-domain-recipes.json'
        self.catalog.write_text(json.dumps({'target': 1, 'available': 1, 'recipes': [
            {'slug': 'test', 'content': self.content, 'provenance': self.provenance, 'source_markdown': ''}]}))
        self.settings_override = override_settings(BASE_DIR=self.root, STORAGES={
            'starter_images': {'BACKEND': 'django.core.files.storage.FileSystemStorage',
                'OPTIONS': {'location': self.root / 'media', 'base_url': 'http://localhost:8000/media/'}}})
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

    def run_command(self):
        call_command('store_starter_images', source_directory=self.source, stdout=io.StringIO())

    def test_copy_retry_reseed_and_preserve_private_edits(self):
        user = get_user_model().objects.create_user(username='owner')
        copied = Recipe.objects.create(owner=user, **self.content, provenance=self.provenance)
        other = get_user_model().objects.create_user(username='other')
        edited = Recipe.objects.create(owner=other, **{**self.content, 'image': 'https://example.com/custom.webp'}, provenance=self.provenance)
        self.run_command()
        self.starter.refresh_from_db()
        copied.refresh_from_db()
        self.assertEqual(copied.image, self.starter.content['image'])
        self.assertIn('/media/starters/', copied.image)
        version = copied.version
        self.run_command()
        copied.refresh_from_db()
        self.assertEqual(copied.version, version)
        self.assertEqual(len(list((self.root / 'media').rglob('*.webp'))), 1)
        edited.refresh_from_db()
        self.assertEqual(edited.image, 'https://example.com/custom.webp')
        call_command('seed_starter_recipes', file=self.catalog, stdout=io.StringIO())
        self.starter.refresh_from_db()
        self.assertEqual(self.starter.content['image'], copied.image)
        with storages['starter_images'].open(self.starter.provenance['image_storage']['key']) as image:
            self.assertEqual(Image.open(image).format, 'WEBP')

    def test_invalid_image_preserves_reference(self):
        (self.source / 'test.webp').write_text('<html>missing</html>')
        with self.assertRaises(CommandError):
            self.run_command()
        self.starter.refresh_from_db()
        self.assertEqual(self.starter.content['image'], self.content['image'])

    def test_upload_failure_preserves_reference_and_retry_recovers(self):
        with patch.object(storages['starter_images'], 'save', side_effect=OSError('offline')):
            with self.assertRaises(CommandError):
                self.run_command()
        self.starter.refresh_from_db()
        self.assertEqual(self.starter.content['image'], self.content['image'])
        self.run_command()
        self.starter.refresh_from_db()
        self.assertIn('/media/', self.starter.content['image'])
