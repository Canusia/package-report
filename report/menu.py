"""Reports sidebar items (cis.menu_registry); id `reports` in ce and
highschool_admin. On a cis without the registry nothing registers.
"""
try:
    from cis.menu_registry import menu
except ImportError:   # cis without the registry: the menu migrations still apply
    menu = None

if menu is not None:
    menu.register('ce', 'reports', 'Reports', url='report:reports',
                  icon='fas fa-fw fa-file-alt', order=110)
    menu.register('highschool_admin', 'reports', 'Reports',
                  url='highschool_admin_report:reports',
                  icon='fas fa-fw fa-file-alt', order=100)
