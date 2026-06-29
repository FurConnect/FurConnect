from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render
from django.urls import reverse
from urllib.parse import quote

def logout_view(request):
    logout(request)
    messages.success(request, 'You have been successfully logged out.')
    return redirect('events:schedule')


def register_view(request):
    messages.error(request, 'Staff registration is disabled. Sign in with ConCat using an organizer role.')
    return redirect('events:schedule')


def login_view(request):
    if settings.CONCAT_ENABLED:
        messages.info(request, 'Sign in with ConCat using an organizer role to manage events.')
        next_path = request.GET.get('next', '')
        if next_path:
            return redirect(f"{reverse('events:concat_login')}?next={quote(next_path)}")
        return redirect('events:concat_login')

    if settings.EVENTZILLA_ENABLED:
        messages.info(request, 'Sign in with Eventzilla using an organizer account to manage events.')
        next_path = request.GET.get('next', '')
        if next_path:
            return redirect(f"{reverse('events:eventzilla_login')}?next={quote(next_path)}")
        return redirect('events:eventzilla_login')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            messages.success(request, 'Welcome back! You have been successfully logged in.')
            next_path = request.POST.get('next') or request.GET.get('next')
            if next_path and next_path.startswith('/') and not next_path.startswith('//'):
                return redirect(next_path)
            return redirect('events:schedule')
        else:
            messages.error(request, 'Invalid username or password.')

    return render(request, 'events/login.html', {
        'current_convention_name': 'FurConnect',
        'next': request.GET.get('next', ''),
    })
