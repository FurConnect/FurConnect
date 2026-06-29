from unittest.mock import patch
import json

from django.test import RequestFactory, SimpleTestCase, TransactionTestCase, override_settings

from events.auth import can_manage_events
from events.eventzilla import (
    EventzillaError,
    authenticate_eventzilla_credentials,
    lookup_attendee_by_email_and_barcode,
    parse_attendee_profile,
)
from events.models import EventzillaAttendee
from events.rsvp import can_rsvp
from events.eventzilla.views import eventzilla_verify_email


class EventzillaApiTests(SimpleTestCase):
    @override_settings(
        EVENTZILLA_ENABLED=True,
        EVENTZILLA_API_KEY='test-key',
        EVENTZILLA_EVENT_ID='12345',
        EVENTZILLA_REQUIRE_PAID_REGISTRATION=True,
        EVENTZILLA_ALLOWED_TICKET_TYPES=[],
    )
    @patch('events.eventzilla.api.get_json')
    def test_lookup_attendee_matches_email_and_barcode(self, get_json):
        get_json.return_value = {
            'attendees': [{
                'id': 99,
                'email': 'Attendee@Example.com',
                'bar_code': '15986598635445',
                'first_name': 'Ada',
                'last_name': 'Lovelace',
                'transaction_status': 'Confirmed',
                'ticket_type': 'Weekend',
            }],
        }

        attendee = lookup_attendee_by_email_and_barcode('attendee@example.com', '15986598635445')

        get_json.assert_called_once_with(
            'events/12345/attendees',
            params={'email': 'attendee@example.com'},
        )
        self.assertEqual(attendee['id'], 99)

    @override_settings(
        EVENTZILLA_ENABLED=True,
        EVENTZILLA_API_KEY='test-key',
        EVENTZILLA_EVENT_ID='12345',
        EVENTZILLA_REQUIRE_PAID_REGISTRATION=True,
        EVENTZILLA_ALLOWED_TICKET_TYPES=['Weekend'],
    )
    @patch('events.eventzilla.api.get_json')
    def test_lookup_attendee_rejects_wrong_barcode(self, get_json):
        get_json.return_value = {
            'attendees': [{
                'id': 1,
                'email': 'guest@example.com',
                'bar_code': '111',
                'transaction_status': 'Confirmed',
                'ticket_type': 'Weekend',
            }],
        }

        self.assertIsNone(lookup_attendee_by_email_and_barcode('guest@example.com', '999'))

    def test_parse_attendee_profile_lowercases_email(self):
        profile = parse_attendee_profile({
            'id': 42,
            'email': 'Ada@Example.com',
            'bar_code': '12345',
            'first_name': 'Ada',
            'last_name': 'Lovelace',
        })
        self.assertEqual(profile['email'], 'ada@example.com')
        self.assertEqual(profile['barcode'], '12345')

    @override_settings(EVENTZILLA_ENABLED=False)
    def test_lookup_requires_enabled_integration(self):
        with self.assertRaises(EventzillaError):
            lookup_attendee_by_email_and_barcode('test@example.com', '123')


class EventzillaAccountTests(TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from django.db import connection

        table_names = connection.introspection.table_names()
        if EventzillaAttendee._meta.db_table not in table_names:
            with connection.schema_editor() as schema_editor:
                schema_editor.create_model(EventzillaAttendee)

    @override_settings(EVENTZILLA_ENABLED=True)
    @patch('events.eventzilla.accounts.lookup_attendee_by_email_and_barcode')
    def test_first_login_creates_account(self, lookup):
        lookup.return_value = {
            'id': 42,
            'email': 'guest@example.com',
            'bar_code': 'ABC123',
            'first_name': 'Guest',
            'last_name': 'User',
            'transaction_status': 'Confirmed',
        }
        request = RequestFactory().post('/eventzilla/verify/')
        request.session = {}

        account, error, created = authenticate_eventzilla_credentials(
            request,
            'Guest@Example.com',
            'ABC123',
        )

        self.assertTrue(created)
        self.assertIsNone(error)
        self.assertEqual(account.email, 'guest@example.com')
        self.assertEqual(account.barcode, 'ABC123')
        self.assertEqual(request.session['eventzilla_account_id'], account.pk)
        self.assertFalse(request.session.get('eventzilla_can_manage'))

    @override_settings(EVENTZILLA_ENABLED=True)
    @patch('events.eventzilla.accounts.lookup_attendee_by_email_and_barcode')
    def test_site_admin_flag_grants_manage_access(self, lookup):
        EventzillaAttendee.objects.create(
            email='organizer@example.com',
            barcode='ORG123',
            display_name='Organizer',
            is_site_admin=True,
        )
        lookup.return_value = {
            'id': 7,
            'email': 'organizer@example.com',
            'bar_code': 'ORG123',
            'first_name': 'Organizer',
            'last_name': 'User',
            'transaction_status': 'Confirmed',
        }
        request = RequestFactory().post('/eventzilla/verify/')
        request.session = {}

        account, error, created = authenticate_eventzilla_credentials(
            request,
            'organizer@example.com',
            'ORG123',
        )

        self.assertFalse(created)
        self.assertIsNone(error)
        self.assertTrue(account.is_site_admin)
        self.assertTrue(request.session['eventzilla_can_manage'])
        self.assertTrue(request.session['eventzilla_is_admin'])
        self.assertTrue(can_manage_events(request))

    @override_settings(EVENTZILLA_ENABLED=True)
    @patch('events.eventzilla.accounts.lookup_attendee_by_email_and_barcode')
    def test_returning_login_reuses_account(self, lookup):
        EventzillaAttendee.objects.create(
            email='guest@example.com',
            barcode='ABC123',
            display_name='Guest User',
        )
        lookup.return_value = {
            'id': 42,
            'email': 'guest@example.com',
            'bar_code': 'ABC123',
            'first_name': 'Guest',
            'last_name': 'User',
            'transaction_status': 'Confirmed',
        }
        request = RequestFactory().post('/eventzilla/verify/')
        request.session = {}

        account, error, created = authenticate_eventzilla_credentials(
            request,
            'guest@example.com',
            'ABC123',
        )

        self.assertFalse(created)
        self.assertIsNone(error)
        self.assertEqual(EventzillaAttendee.objects.count(), 1)
        self.assertTrue(can_rsvp(request))


class EventzillaVerifyEmailViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @override_settings(EVENTZILLA_ENABLED=True)
    @patch('events.eventzilla.views.authenticate_eventzilla_credentials')
    def test_verify_email_returns_profile_json(self, authenticate):
        account = EventzillaAttendee(
            email='guest@example.com',
            barcode='ABC123',
            display_name='Guest User',
        )
        authenticate.return_value = (account, None, True)
        request = self.factory.post('/eventzilla/verify/', {
            'email': 'guest@example.com',
            'barcode': 'ABC123',
        })
        request.session = {}

        response = eventzilla_verify_email(request)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertTrue(payload['success'])
        self.assertTrue(payload['created'])

    @override_settings(EVENTZILLA_ENABLED=True)
    def test_verify_email_requires_barcode(self):
        request = self.factory.post('/eventzilla/verify/', {'email': 'guest@example.com'})
        request.session = {}

        response = eventzilla_verify_email(request)

        self.assertEqual(response.status_code, 400)
