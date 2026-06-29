from django.conf import settings
from django.contrib import messages
from django.db import OperationalError
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST
from urllib.parse import quote

from ..models import Convention
from ..navigation import sanitize_next_url
from .accounts import (
    authenticate_eventzilla_credentials,
    clear_eventzilla_session,
    get_eventzilla_account,
    update_eventzilla_profile,
)
from .exceptions import EventzillaError
from .rsvp_sync import sync_rsvp_metadata


def _convention_name():
    convention = Convention.objects.first()
    return convention.name if convention else 'FurConnect'


@ensure_csrf_cookie
def eventzilla_login(request):
    if not settings.EVENTZILLA_ENABLED:
        messages.error(request, 'Eventzilla sign-in is not enabled.')
        return redirect('events:schedule')

    next_url = sanitize_next_url(
        request.GET.get('next') or request.META.get('HTTP_REFERER') or '/'
    )

    if request.method == 'POST':
        email = (request.POST.get('email') or '').strip().lower()
        barcode = (request.POST.get('barcode') or '').strip()
        next_url = sanitize_next_url(request.POST.get('next') or next_url)
        try:
            account, error, _created = authenticate_eventzilla_credentials(request, email, barcode)
            if error:
                messages.error(request, error)
            else:
                messages.success(
                    request,
                    f'Signed in as {account.display_name}. You can RSVP to panels.',
                )
                return redirect(next_url)
        except EventzillaError as exc:
            messages.error(request, str(exc))

    return render(request, 'events/eventzilla_login.html', {
        'current_convention_name': _convention_name(),
        'next': next_url,
    })


@require_POST
def eventzilla_verify_email(request):
    if not settings.EVENTZILLA_ENABLED:
        return JsonResponse(
            {'success': False, 'error': 'Eventzilla sign-in is not enabled.'},
            status=400,
        )

    email = (request.POST.get('email') or '').strip().lower()
    barcode = (request.POST.get('barcode') or '').strip()
    if not email or not barcode:
        return JsonResponse(
            {'success': False, 'error': 'Email and ticket barcode are required.'},
            status=400,
        )

    try:
        account, error, created = authenticate_eventzilla_credentials(request, email, barcode)
        if error:
            return JsonResponse({'success': False, 'error': error}, status=404)
        return JsonResponse({
            'success': True,
            'email': account.email,
            'display_name': account.display_name,
            'avatar_url': account.get_avatar_display(),
            'profile_url': reverse('events:eventzilla_profile'),
            'created': created,
        })
    except EventzillaError as exc:
        return JsonResponse({'success': False, 'error': str(exc)}, status=502)
    except OperationalError:
        return JsonResponse({
            'success': False,
            'error': (
                'Database is missing Eventzilla tables. '
                'Run: python manage.py ensure_eventzilla_tables'
            ),
        }, status=500)
    except Exception as exc:
        return JsonResponse({
            'success': False,
            'error': str(exc) if settings.DEBUG else 'Sign-in failed. Please try again.',
        }, status=500)


def eventzilla_profile(request):
    if not settings.EVENTZILLA_ENABLED:
        messages.error(request, 'Eventzilla sign-in is not enabled.')
        return redirect('events:schedule')

    account = get_eventzilla_account(request)
    if not account:
        messages.info(request, 'Sign in with your registration email and ticket barcode first.')
        return redirect(f"{reverse('events:eventzilla_login')}?next={quote(request.get_full_path())}")

    return render(request, 'events/eventzilla_profile.html', {
        'account': account,
        'current_convention_name': _convention_name(),
    })


@require_POST
def eventzilla_update_profile(request):
    if not settings.EVENTZILLA_ENABLED:
        return JsonResponse({'success': False, 'error': 'Eventzilla sign-in is not enabled.'}, status=400)

    account = get_eventzilla_account(request)
    if not account:
        return JsonResponse({'success': False, 'error': 'Sign in required.'}, status=401)

    display_name = (request.POST.get('display_name') or '').strip()
    if not display_name:
        return JsonResponse({'success': False, 'error': 'Display name is required.'}, status=400)

    avatar = request.POST.get('avatar')
    if avatar == '':
        avatar = ''
    elif avatar is None:
        avatar = account.avatar

    update_eventzilla_profile(account, display_name=display_name, avatar=avatar)
    request.session['eventzilla_user_name'] = account.display_name
    request.session['eventzilla_user_avatar'] = account.get_avatar_display()
    sync_rsvp_metadata(account)

    return JsonResponse({
        'success': True,
        'display_name': account.display_name,
        'avatar_url': account.get_avatar_display(),
    })


def eventzilla_logout(request):
    clear_eventzilla_session(request)
    messages.success(request, 'Signed out of Eventzilla.')
    return redirect(request.META.get('HTTP_REFERER', '/'))
