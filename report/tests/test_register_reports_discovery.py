"""`register_reports` found apps by calling `import_string()` on each
INSTALLED_APPS entry, which only resolves when the entry is the dotted path
to the AppConfig class. A plain entry ('student', 'instructor',
'highschool_admin', ...) raised, and a bare `except:` swallowed it, so those
apps' REPORTS were never registered and nothing in the output said so.

It also only ever looked at the AppConfig, though README and CLAUDE.md both
document declaring REPORTS "in your app's `apps.py` or `__init__.py`".

Discovery now walks the app registry and accepts either placement.
"""
from types import SimpleNamespace

from django.test import TestCase

from ..management.commands.register_reports import discover_manifests


def manifest(name):
    return {
        'app': name, 'name': f'{name}_report', 'title': 'T',
        'description': 'D', 'categories': ['Students'], 'available_for': ['ce'],
    }


def fake_config(name, *, on_config=None, on_module=None):
    module = SimpleNamespace()
    if on_module is not None:
        module.REPORTS = on_module
    config = SimpleNamespace(name=name, module=module)
    if on_config is not None:
        config.REPORTS = on_config
    return config


class DiscoverManifestsTests(TestCase):
    def test_reports_declared_on_the_appconfig_are_found(self):
        config = fake_config('pd_event', on_config=[manifest('pd_event')])
        self.assertEqual(
            list(discover_manifests([config])),
            [('pd_event', [manifest('pd_event')])],
        )

    def test_reports_declared_in_the_app_module_are_found(self):
        """The case the old import_string() path could not reach."""
        config = fake_config('student', on_module=[manifest('student')])
        self.assertEqual(
            list(discover_manifests([config])),
            [('student', [manifest('student')])],
        )

    def test_the_appconfig_wins_when_both_declare_reports(self):
        config = fake_config(
            'cis', on_config=[manifest('from_config')],
            on_module=[manifest('from_module')],
        )
        self.assertEqual(
            list(discover_manifests([config])),
            [('cis', [manifest('from_config')])],
        )

    def test_apps_without_reports_are_skipped(self):
        self.assertEqual(list(discover_manifests([fake_config('auth')])), [])

    def test_an_empty_reports_list_is_skipped(self):
        config = fake_config('empty', on_config=[])
        self.assertEqual(list(discover_manifests([config])), [])
