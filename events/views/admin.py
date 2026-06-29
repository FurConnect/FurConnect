import colorsys
import random

from django.contrib import messages
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from ..auth import organizer_required
from ..forms import ConventionForm
from ..models import Convention, Panel, PanelHost, Room, Tag

ADMIN_PANEL_SECTIONS = frozenset({'dashboard', 'settings', 'rooms', 'hosts', 'tags'})


def _get_admin_panel_data(convention):
    rooms = Room.objects.filter(convention=convention).order_by('name')
    tags = (
        Tag.objects.filter(panels__convention_day__convention=convention)
        .distinct()
        .order_by('name')
    )
    panel_count = Panel.objects.filter(convention_day__convention=convention).count()
    day_count = convention.days.count()
    return {
        'rooms': rooms,
        'hosts_count': PanelHost.objects.count(),
        'tags': tags,
        'panel_count': panel_count,
        'day_count': day_count,
    }


@organizer_required
def admin_panel(request, pk, section='dashboard'):
    convention = get_object_or_404(Convention, pk=pk)
    if section not in ADMIN_PANEL_SECTIONS:
        section = 'dashboard'

    context = {
        'convention': convention,
        'section': section,
        'current_convention_name': convention.name,
        'concat_user_name': request.session.get('concat_user_name', ''),
    }
    context.update(_get_admin_panel_data(convention))

    if section == 'settings':
        if request.method == 'POST':
            form = ConventionForm(request.POST, request.FILES, instance=convention)
            if form.is_valid():
                form.save()
                messages.success(request, 'Event settings saved successfully!')
                return redirect('events:admin_panel_section', pk=pk, section='settings')
        else:
            form = ConventionForm(instance=convention)
        context['form'] = form

    return render(request, 'admin/convention_admin.html', context)


@organizer_required
def manage_convention_items(request, pk):
    return redirect('events:admin_panel_section', pk=pk, section='rooms')


def _admin_panel_redirect(convention_pk, section='dashboard'):
    return redirect('events:admin_panel_section', pk=convention_pk, section=section)


@organizer_required
def randomize_tag_colors(request):
    if request.method == 'POST':
        tags = Tag.objects.all()
        count = 0
        for tag in tags:
            hue = random.randint(0, 360)
            saturation = random.randint(60, 90)
            lightness = random.randint(40, 60)
            r, g, b = colorsys.hls_to_rgb(hue / 360.0, lightness / 100.0, saturation / 100.0)
            tag.color = f'#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}'
            tag.save()
            count += 1
        messages.success(request, f'Successfully randomized colors for {count} tags.')

    convention_pk = request.POST.get('convention_pk')
    if convention_pk:
        return _admin_panel_redirect(convention_pk, 'tags')
    return redirect(request.META.get('HTTP_REFERER', reverse('events:schedule')))
