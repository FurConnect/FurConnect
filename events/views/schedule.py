from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET

from ..models import Convention

def schedule(request):
    convention = Convention.objects.first()
    if convention:
        return redirect('events:convention_detail', pk=convention.pk)
    return render(request, 'events/schedule.html', {'conventions': [], 'current_convention_name': 'FurConnect'})


@require_GET
def privacy_policy(request):
    return render(request, 'events/privacy_policy.html')
