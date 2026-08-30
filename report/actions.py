"""CE bulk actions for queued report runs.

Registers two superuser-only handlers on a local ActionRegistry, following the
support_ticket pattern:

  bulk_run_reports    : ajax, enqueues each selected pending run
  bulk_delete_reports : two-phase form, deletes selected pending runs

Both filter to status='pending'. Runs with status 'ran' own S3 artifacts and an
audit trail; neither action touches them.
"""
import uuid
from collections import OrderedDict

from django.http import JsonResponse
from django.template.loader import render_to_string
from django.urls import reverse

from myce.component_registry import ActionRegistry

from .models.report import ReportScheduler
from .tasks import process_report

BULK_ACTION_TEMPLATE = 'cis/students/bulk_action.html'


def _valid_uuids(ids):
    """Return only the items from *ids* that parse as UUIDs.

    filter(id__in=[...]) raises ValidationError on a malformed UUID, which
    surfaces as a 500. Callers must filter first.
    """
    out = []
    for value in ids or []:
        try:
            uuid.UUID(str(value))
            out.append(value)
        except (ValueError, TypeError, AttributeError):
            pass
    return out


def _is_superuser(user):
    return bool(user and user.is_authenticated and user.is_superuser)


def queue_pending(ids):
    """Enqueue every pending run in *ids*. Returns (queued, skipped).

    The single implementation of the pending-only queueing rule, shared by the
    CE bulk action and ReportSchedulerAdmin.run_selected_pending_reports.
    Anything in *ids* that is not a pending run — a malformed id, an id that
    does not exist, or a run already 'ran'/'error' — counts as skipped.
    """
    ids = list(ids or [])
    pending = list(
        ReportScheduler.objects
        .filter(id__in=_valid_uuids(ids), status='pending')
        .values_list('id', flat=True)
    )
    for pk in pending:
        process_report.enqueue(str(pk))
    return len(pending), len(ids) - len(pending)


def queued_message(queued, skipped):
    return (f'Queued {queued} report(s); '
            f'skipped {skipped} that were not pending.')


report_actions = ActionRegistry(OrderedDict({
    'bulk_scheduler': {'actions': OrderedDict()},
}))


@report_actions.action(
    'bulk_scheduler',
    label='Run Selected',
    scope=['bulk'],
    slug='bulk_run_reports',
    method='ajax',
    icon='fas fa-play',
    btn_class='btn-success',
    confirm='Queue the selected report(s) to run?',
    permission=_is_superuser,
)
def bulk_run_reports(request):
    raw_ids = request.POST.getlist('ids[]')
    queued, skipped = queue_pending(raw_ids)
    return JsonResponse({
        'outcome': 'call',
        'fn': 'refreshTable',
        'args': {
            'title': 'Done',
            'message': queued_message(queued, skipped),
            'status': 'success',
        },
    })


@report_actions.action(
    'bulk_scheduler',
    label='Delete Selected',
    scope=['bulk'],
    slug='bulk_delete_reports',
    method='form',
    icon='fas fa-trash',
    btn_class='btn-danger',
    permission=_is_superuser,
)
def bulk_delete_reports(request):
    from .forms import BulkDeleteSchedulerForm

    raw_ids = request.POST.getlist('ids[]')
    ids = _valid_uuids(raw_ids)

    if request.POST.get('action_confirmed'):
        form = BulkDeleteSchedulerForm(data=request.POST)
        if form.is_valid():
            deleted, _ = (
                ReportScheduler.objects
                .filter(id__in=ids, status='pending')
                .delete()
            )
            skipped = len(raw_ids) - deleted
            return JsonResponse({
                'outcome': 'call',
                'fn': 'refreshTable',
                'args': {
                    'title': 'Done',
                    'message': (f'Deleted {deleted} pending report run(s); '
                                f'skipped {skipped} that were not pending.'),
                    'status': 'success',
                },
            })
        return JsonResponse({
            'message': 'Please correct the errors and try again.',
            'errors': form.errors.as_json(),
        }, status=400)

    pending_count = ReportScheduler.objects.filter(
        id__in=ids, status='pending').count()
    html = render_to_string(BULK_ACTION_TEMPLATE, {
        'title': f'Delete {pending_count} Pending Report Run(s)',
        'form': BulkDeleteSchedulerForm(),
        'form_action': reverse('report:bulk_actions'),
        'action_slug': 'bulk_delete_reports',
        'ids': raw_ids,
    }, request=request)
    return JsonResponse({'outcome': 'modal', 'html': html})
