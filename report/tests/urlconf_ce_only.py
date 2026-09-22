"""A host URLconf that mounts only the CE reports portal.

Not every consuming project mounts both portals: umn's `myce/urls.py` includes
`report.urls.ce` alone, so the 'highschool_admin_report' namespace does not
exist there and reversing into it raises NoReverseMatch. Used to pin the
fallback in `ReportScheduler.download_email_link`.
"""
from django.urls import include, path

# This package is importable as either `report` or `report.report`, depending on
# whether the host uses the editable-submodule override, so the dotted path to
# the CE URLconf has to be derived rather than hardcoded.
_package = __name__.rsplit('.', 2)[0]

urlpatterns = [
    path('ce/reports/', include(f'{_package}.urls.ce')),
]
