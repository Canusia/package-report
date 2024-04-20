from django.db.models import Q
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.shortcuts import get_object_or_404, redirect, render

#from cis.forms.note import NoteForm

from cis.utils import user_has_highschool_admin_role

from cis.menu import draw_menu, HS_ADMIN_MENU

from support_ticket.forms.types import SupportTicketNoteForm
from support_ticket.models.ticket import Ticket, TicketNote
from support_ticket.forms.types import SupportTicketForm

@user_passes_test(user_has_highschool_admin_role, login_url='/')
def tickets(request):
    """
    Return tickets created by student or for the student
    """
    menu = draw_menu(HS_ADMIN_MENU, 'support', '')

    template = 'support_ticket/highschool_admin/index.html'
    query = request.GET.get('q', '')
    page = request.GET.get('page', 1)
    order_by = request.GET.get('order_by', 'submitted_on').lower()
    order = request.GET.get('order', 'desc')

    valid_order_by_fields = [
        'submitted_on'
    ]
    if order_by not in valid_order_by_fields:
        order_by = 'submitted_on'

    valid_order = [
        'asc', 'desc'
    ]
    if order not in valid_order:
        order = 'asc'

    if not query:
        record_list = Ticket.objects.filter(
            submitted_by=request.user
        ).order_by(order_by if order == 'asc' else f"-{order_by}")
    else:
        record_list = Ticket.objects.filter(
            Q(name__contains=query)).order_by(
                order_by if order == 'asc' else f"-{order_by}")

    paginator = Paginator(record_list, 30)
    try:
        records = paginator.page(page)
    except PageNotAnInteger:
        records = paginator.page(1)
    except EmptyPage:
        records = paginator.page(paginator.num_pages)

    return render(
        request,
        template, {
            'page_title': 'Support Requests',
            'urls': {
                'add_new': 'hs_admin_support_ticket:add_new',
                'details': 'hs_admin_support_ticket:details'
            },
            'menu': menu,
            'count': len(records),
            'records':records,
            'q': query,
            'order_by': order_by,
            'order': order})

@user_passes_test(user_has_highschool_admin_role, login_url='/')
def add_new(request):
    """
    Manage handling new ticket creation
    """
    menu = draw_menu(HS_ADMIN_MENU, 'support', '')

    base_template = 'cis/logged-base.html'
    template = 'support_ticket/highschool_admin/add_new.html'
    form = SupportTicketForm(request, 'School Administrators')

    if request.method == 'POST':
        form = SupportTicketForm(
            request,
            'School Administrators',
            request.POST,
            request.FILES)
        if form.is_valid():
            support_ticket = form.save(commit=False)
            support_ticket.submitted_by = request.user
            support_ticket.status = 'Submitted'
            support_ticket.save()

            messages.add_message(
                request,
                messages.SUCCESS,
                'Successfully submitted request',
                'list-group-item-success') 
            return redirect('hs_admin_support_ticket:requests')

    return render(request,
        template, {
            'base_template': base_template,
            'form': form,
            'page_title': 'Submit New Support Request',
            'labels': {
                'all_items': 'All Requests'
            },
            'urls': {
                'all_items': 'hs_admin_support_ticket:requests'
            },
            'menu': menu})

@user_passes_test(user_has_highschool_admin_role, login_url='/')
def details(request, record_id):
    """
    Show details for ticket
    """
    '''
    Record details page
    '''
    template = 'support_ticket/highschool_admin/details.html'
    record = get_object_or_404(Ticket, pk=record_id)
    menu = draw_menu(HS_ADMIN_MENU, 'support', '')

    if request.method == 'POST':
        form = SupportTicketNoteForm(request.POST, request.FILES)

        if form.is_valid():
            note = TicketNote.add_note(request, form)
            if note:
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    'Successfully added note',
                    'list-group-item-success')
                return redirect('hs_admin_support_ticket:details', record_id=record_id)
    else:
        initial = {
            'model': f'ticketnote',
            'ajax': 0,
            'add_to': record_id,
            'id': -1
        }
        form = SupportTicketNoteForm(initial=initial)

    notes = TicketNote.objects.filter(
        support_ticket=record
    ).order_by('-createdon')

    return render(
        request,
        template, {
            'form': form,
            'page_title': "Support Request",
            'labels': {
                'all_items': 'All Requests'
            },
            'urls': {
                'all_items': 'hs_admin_support_ticket:requests'
            },
            'menu': menu,
            'notes': notes,
            'record': record,
            'form': form
        })

