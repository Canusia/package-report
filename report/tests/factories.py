"""Shared fixtures for the report package's tests.

`login` disconnects django_login_history's post_login receiver, which blows up
on synthetic requests. `make_scheduler` backdates via .update() because
ReportScheduler.created_on is auto_now=True and .save() would rewrite it.
"""
import uuid
from datetime import timedelta

from django.contrib.auth.models import Group
from django.contrib.auth.signals import user_logged_in
from django.utils import timezone

from cis.models.customuser import CustomUser

from ..models.report import Report, ReportScheduler


def login(client, user):
    from django_login_history.models import post_login
    user_logged_in.disconnect(post_login)
    try:
        client.force_login(user)
    finally:
        user_logged_in.connect(post_login)


def make_user(username, email=None, *, superuser=False, groups=('ce',)):
    user = CustomUser.objects.create(
        username=username,
        email=email or f'{username}@example.com',
        first_name=username.title(),
        last_name='Tester',
        is_superuser=superuser,
        is_staff=superuser,
    )
    for name in groups:
        group, _ = Group.objects.get_or_create(name=name)
        user.groups.add(group)
    return user


def make_report(**overrides):
    values = {
        'app': 'cis',
        'name': f'report_{uuid.uuid4().hex[:8]}',
        'title': 'Sample Report',
        'description': 'A sample report.',
        'categories': ['Students'],
        'available_for': ['ce'],
    }
    values.update(overrides)
    return Report.objects.create(**values)


def make_scheduler(report, user, status='pending', days_ago=0):
    scheduler = ReportScheduler.objects.create(
        report=report, created_by=user, data={}, summary={}, status=status,
    )
    if days_ago:
        # auto_now=True means save() rewrites created_on; update() does not.
        ReportScheduler.objects.filter(pk=scheduler.pk).update(
            created_on=timezone.now() - timedelta(days=days_ago)
        )
        scheduler.refresh_from_db()
    return scheduler
