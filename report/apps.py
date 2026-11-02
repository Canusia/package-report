from django.apps import AppConfig


class ReportConfig(AppConfig):
    name = 'report'

    def ready(self):
        from . import menu  # noqa: F401  sidebar items (cis.menu_registry)

class DevReportConfig(AppConfig):
    name = 'report.report'

    def ready(self):
        from . import menu  # noqa: F401  sidebar items (cis.menu_registry)
