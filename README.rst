MyCE - Report
====================
- Reports executor

In settings.py, 
    add the app to INSTALLED_APPS as 
        'report.apps.ReportConfig'

    Add path to STATIC_FILES_DIRS
        os.path.join(get_package_path("invoice"), 'staticfiles'),


In myce/urls
    path('ce/reports/', include('report.urls.ce')),
    path('faculty/reports/', include('report.urls.faculty')),
    path('highschool_admin/reports/', include('report.urls.highschool_admin')),