from django.core.management.base import BaseCommand, CommandError

from events.eventzilla.normalize import normalize_email
from events.models import EventzillaAttendee

PLACEHOLDER_BARCODE = ''


class Command(BaseCommand):
    help = 'Grant Eventzilla site admin access to a registration email.'

    def add_arguments(self, parser):
        parser.add_argument('email', help='Registration email address')

    def handle(self, *args, **options):
        email = normalize_email(options['email'])
        if not email:
            raise CommandError('Email is required.')

        try:
            account, created = EventzillaAttendee.objects.get_or_create(
                email=email,
                defaults={
                    'barcode': PLACEHOLDER_BARCODE,
                    'display_name': email.split('@', 1)[0],
                    'is_site_admin': True,
                },
            )
        except Exception as exc:
            raise CommandError(
                'Eventzilla attendee table is unavailable. '
                'Run: python manage.py ensure_eventzilla_tables'
            ) from exc

        updated = False
        if not created and not account.is_site_admin:
            account.is_site_admin = True
            account.save(update_fields=['is_site_admin', 'updated_at'])
            updated = True

        if created:
            self.stdout.write(self.style.SUCCESS(
                f'Created admin account for {email}. '
                'They can sign in with their Eventzilla email and ticket barcode.'
            ))
        elif updated:
            self.stdout.write(self.style.SUCCESS(
                f'Granted site admin access to {email}. '
                'They must sign in again for it to take effect.'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'{email} already has site admin access.'
            ))
