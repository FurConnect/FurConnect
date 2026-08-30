from unittest.mock import patch
import io
import json

from django.core.management import call_command
from django.test import Client, RequestFactory, SimpleTestCase, TransactionTestCase, override_settings

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
                'refno': '15986598635445',
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
                'refno': '111',
                'transaction_status': 'Confirmed',
                'ticket_type': 'Weekend',
            }],
        }

        self.assertIsNone(lookup_attendee_by_email_and_barcode('guest@example.com', '999'))

    def test_parse_attendee_profile_lowercases_email(self):
        profile = parse_attendee_profile({
            'id': 42,
            'email': 'Ada@Example.com',
            'refno': '12345',
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
            'refno': 'ABC123',
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
            'refno': 'ORG123',
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
            'refno': 'ABC123',
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
        self.assertTrue(can_manage_events(request))


class GrantEventzillaAdminCommandTests(TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from django.db import connection

        table_names = connection.introspection.table_names()
        if EventzillaAttendee._meta.db_table not in table_names:
            with connection.schema_editor() as schema_editor:
                schema_editor.create_model(EventzillaAttendee)

    def test_grants_admin_to_existing_account(self):
        EventzillaAttendee.objects.create(
            email='organizer@example.com',
            barcode='ABC123',
            display_name='Organizer',
        )
        call_command('grant_eventzilla_admin', 'organizer@example.com', stdout=io.StringIO())
        account = EventzillaAttendee.objects.get(email='organizer@example.com')
        self.assertTrue(account.is_site_admin)

    def test_pre_provisions_new_admin_account(self):
        call_command('grant_eventzilla_admin', 'newadmin@example.com', stdout=io.StringIO())
        account = EventzillaAttendee.objects.get(email='newadmin@example.com')
        self.assertTrue(account.is_site_admin)
        self.assertEqual(account.barcode, '')


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

    @override_settings(EVENTZILLA_ENABLED=True)
    def test_verify_email_requires_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post('/eventzilla/verify/', {
            'email': 'guest@example.com',
            'barcode': 'ABC123',
        })
        self.assertEqual(response.status_code, 403)


class ConventionCatalogTests(TransactionTestCase):
    def setUp(self):
        from datetime import date, time as time_of_day

        from django.core.cache import cache

        from events.models import Convention, ConventionDay, Panel, PanelHost, PanelHostOrder, Room, Tag

        cache.clear()
        Convention.objects.all().delete()
        self.convention = Convention.objects.create(
            name='Catalog Con',
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 2),
            location='Test City',
        )
        self.day = ConventionDay.objects.create(convention=self.convention, date=date(2026, 8, 1))
        self.room = Room.objects.create(convention=self.convention, name='Main Hall', sort_order=0)
        self.host = PanelHost.objects.create(name='Ada Lovelace')
        self.tag = Tag.objects.create(name='Science', color='#112233')
        self.panel = Panel.objects.create(
            title='Computing',
            description='Talk about engines',
            convention_day=self.day,
            start_time=time_of_day(10, 0),
            end_time=time_of_day(11, 0),
            room=self.room,
        )
        PanelHostOrder.objects.create(panel=self.panel, host=self.host, priority=0)
        self.panel.tags.add(self.tag)

    def test_public_catalog_includes_hosts_rooms_and_tags(self):
        from events.catalog import build_public_host_catalog

        catalog = build_public_host_catalog(self.convention)

        self.assertEqual(catalog['convention_id'], self.convention.pk)
        self.assertTrue(catalog['version'])
        self.assertEqual(len(catalog['hosts']), 1)
        self.assertEqual(catalog['hosts'][0]['name'], 'Ada Lovelace')
        self.assertEqual(catalog['hosts'][0]['panels_count'], 1)
        self.assertEqual(catalog['hosts'][0]['panels'][0]['title'], 'Computing')
        self.assertEqual(catalog['rooms'][0]['name'], 'Main Hall')
        self.assertEqual(catalog['tags'][0]['name'], 'Science')

    def test_public_catalog_is_reused_until_invalidated(self):
        from events.catalog import build_public_host_catalog, invalidate_convention_catalogs

        first = build_public_host_catalog(self.convention)
        with self.assertNumQueries(0):
            second = build_public_host_catalog(self.convention)
        self.assertEqual(first['version'], second['version'])
        self.assertEqual(first['hosts'][0]['name'], second['hosts'][0]['name'])

        invalidate_convention_catalogs(self.convention.pk)
        rebuilt = build_public_host_catalog(self.convention)
        self.assertEqual(rebuilt['hosts'][0]['name'], 'Ada Lovelace')

    def test_convention_detail_embeds_catalog(self):
        client = Client()
        response = client.get(f'/convention/{self.convention.pk}/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="host-catalog"')
        self.assertContains(response, 'Ada Lovelace')
        self.assertContains(response, 'furconnect:host-catalog:')
        self.assertContains(response, 'loadHostImages')
        self.assertContains(response, 'id="convention-page-loader"')
        self.assertContains(response, f'{self.convention.name} is loading')
        self.assertContains(response, 'id="convention-page-data"')
        self.assertContains(response, 'id="googleCalendarSubscribeBtn"')
        self.assertContains(response, 'calendar.google.com/calendar/r?cid=')
        self.assertContains(response, 'Leave webcal:// unencoded')

    def test_catalog_ajax_returns_one_payload(self):
        client = Client()
        response = client.get(f'/ajax/convention/{self.convention.pk}/catalog/')

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertIn('hosts', payload)
        self.assertIn('rooms', payload)
        self.assertIn('tags', payload)
        self.assertEqual(payload['hosts'][0]['name'], 'Ada Lovelace')
        self.assertEqual(response['Cache-Control'], 'public, max-age=60')


class ConcatCacheTests(SimpleTestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()

    @override_settings(CONCAT_ENABLED=True)
    @patch('events.concat.profiles.get_user_by_id')
    def test_profile_pictures_are_stored_and_reused(self, get_user_by_id):
        from events.concat.profiles import get_concat_profile_pictures

        get_user_by_id.return_value = {'profilePictureUrl': 'https://cdn.example/ada.png'}

        first = get_concat_profile_pictures(['42'], token='tok')
        second = get_concat_profile_pictures(['42'], token='tok')

        self.assertEqual(first['42'], 'https://cdn.example/ada.png')
        self.assertEqual(second['42'], 'https://cdn.example/ada.png')
        get_user_by_id.assert_called_once_with('42', token='tok')

    @override_settings(CONCAT_ENABLED=True)
    @patch('events.concat.profiles.get_user_by_id')
    def test_profile_pictures_fetch_each_missing_id(self, get_user_by_id):
        from events.concat.profiles import get_concat_profile_pictures

        get_user_by_id.side_effect = [
            {'profilePictureUrl': 'https://cdn.example/ada.png'},
            {'profilePictureUrl': 'https://cdn.example/al.png'},
        ]

        pictures = get_concat_profile_pictures(['42', '7'], token='tok')

        self.assertEqual(pictures['42'], 'https://cdn.example/ada.png')
        self.assertEqual(pictures['7'], 'https://cdn.example/al.png')
        self.assertEqual(get_user_by_id.call_count, 2)

    @patch('events.concat.oauth.post_token')
    def test_service_token_is_stored_and_reused(self, post_token):
        from events.concat.oauth import get_service_token

        post_token.return_value = {'access_token': 'abc123', 'expires_in': 3600}

        first = get_service_token(scope='user:read')
        second = get_service_token(scope='user:read')

        self.assertEqual(first, 'abc123')
        self.assertEqual(second, 'abc123')
        post_token.assert_called_once()


class RsvpCalendarTokenTests(SimpleTestCase):
    def test_token_roundtrip_hides_email_and_avoids_colons(self):
        from events.rsvp.feed import make_rsvp_feed_token, user_id_from_rsvp_feed_token

        email = 'guest@example.com'
        token = make_rsvp_feed_token(email)

        self.assertNotIn(':', token)
        self.assertNotIn('@', token)
        self.assertNotIn(email, token)
        self.assertEqual(user_id_from_rsvp_feed_token(token), email)

    def test_legacy_colon_token_still_decodes(self):
        from django.core.signing import TimestampSigner
        from events.rsvp.feed import user_id_from_rsvp_feed_token

        legacy = TimestampSigner(salt='furconnect-rsvp-feed').sign('concat-user-99')
        self.assertEqual(user_id_from_rsvp_feed_token(legacy), 'concat-user-99')

    def test_feed_user_ids_include_eventzilla_and_concat_forms(self):
        from events.rsvp.feed import attendee_ids_for_feed_user

        ids = attendee_ids_for_feed_user('guest@example.com')
        self.assertIn('guest@example.com', ids)
        self.assertIn('eventzilla:guest@example.com', ids)


class RsvpCalendarFeedViewTests(TransactionTestCase):
    def setUp(self):
        from datetime import date, time as time_of_day

        from events.models import Convention, ConventionDay, Panel, PanelRSVP, Room

        Convention.objects.all().delete()
        self.convention = Convention.objects.create(
            name='RSVP Con',
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 2),
            location='Test City',
        )
        day = ConventionDay.objects.create(convention=self.convention, date=date(2026, 8, 1))
        room = Room.objects.create(convention=self.convention, name='Hall', sort_order=0)
        self.rsvped = Panel.objects.create(
            title='My Panel',
            description='Saved event',
            convention_day=day,
            start_time=time_of_day(10, 0),
            end_time=time_of_day(11, 0),
            room=room,
        )
        self.other = Panel.objects.create(
            title='Other Panel',
            description='Not saved',
            convention_day=day,
            start_time=time_of_day(12, 0),
            end_time=time_of_day(13, 0),
            room=room,
        )
        PanelRSVP.objects.create(
            panel=self.rsvped,
            attendee_id='guest@example.com',
            display_name='Guest',
        )

    def test_token_path_returns_only_rsvps_without_session(self):
        from events.rsvp.feed import make_rsvp_feed_token

        token = make_rsvp_feed_token('guest@example.com')
        client = Client()
        response = client.get(f'/convention/{self.convention.pk}/calendar/{token}.ics')

        self.assertEqual(response.status_code, 200)
        body = response.content.decode('utf-8', errors='ignore')
        self.assertIn('My Panel', body)
        self.assertIn('(RSVP)', body)
        self.assertIn('(My RSVPs)', body)
        self.assertNotIn('Other Panel', body)
        self.assertIn('text/calendar', response['Content-Type'])
        self.assertIn('charset=utf-8', response['Content-Type'])
        self.assertRegex(body, r'DTSTART:\d{8}T\d{6}Z')

    def test_query_token_returns_only_rsvps_without_session(self):
        from events.rsvp.feed import make_rsvp_feed_token

        token = make_rsvp_feed_token('guest@example.com')
        client = Client()
        response = client.get(f'/convention/{self.convention.pk}/calendar.ics', {'rsvp': token})

        self.assertEqual(response.status_code, 200)
        body = response.content.decode('utf-8', errors='ignore')
        self.assertIn('My Panel', body)
        self.assertNotIn('Other Panel', body)

    def test_invalid_token_returns_empty_calendar(self):
        client = Client()
        response = client.get(
            f'/convention/{self.convention.pk}/calendar.ics',
            {'rsvp': 'not-a-valid-token'},
        )

        self.assertEqual(response.status_code, 200)
        body = response.content.decode('utf-8', errors='ignore')
        self.assertNotIn('My Panel', body)
        self.assertNotIn('Other Panel', body)

    def test_full_feed_is_not_labeled_as_rsvps(self):
        client = Client()
        response = client.get(f'/convention/{self.convention.pk}/calendar.ics')

        self.assertEqual(response.status_code, 200)
        body = response.content.decode('utf-8', errors='ignore')
        self.assertIn('My Panel', body)
        self.assertIn('Other Panel', body)
        self.assertNotIn('(My RSVPs)', body)
        self.assertNotIn('(RSVP)', body)
        self.assertIn('X-WR-CALNAME:RSVP Con', body)


class PanelTagOrderTests(TransactionTestCase):
    def setUp(self):
        from datetime import date, time as time_of_day

        from events.models import Convention, ConventionDay, Panel, PanelTag, Room, Tag

        Convention.objects.all().delete()
        self.convention = Convention.objects.create(
            name='Tag Order Con',
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 2),
            location='Test City',
        )
        day = ConventionDay.objects.create(convention=self.convention, date=date(2026, 8, 1))
        room = Room.objects.create(convention=self.convention, name='Hall', sort_order=0)
        self.tag_a = Tag.objects.create(name='Alpha', color='#111111')
        self.tag_b = Tag.objects.create(name='Beta', color='#222222')
        self.panel = Panel.objects.create(
            title='Tagged Panel',
            description='Has tags',
            convention_day=day,
            start_time=time_of_day(10, 0),
            end_time=time_of_day(11, 0),
            room=room,
        )
        PanelTag.objects.create(panel=self.panel, tag=self.tag_a, priority=0)
        PanelTag.objects.create(panel=self.panel, tag=self.tag_b, priority=1)

    def test_form_save_keeps_posted_tag_order(self):
        from events.forms import PanelForm
        from events.models import PanelTag

        form = PanelForm(
            {
                'title': self.panel.title,
                'description': self.panel.description,
                'convention_day': str(self.panel.convention_day_id),
                'start_time': '10:00',
                'end_time': '11:00',
                'room': str(self.panel.room_id),
                'tags': [str(self.tag_b.pk), str(self.tag_a.pk)],
            },
            instance=self.panel,
            convention=self.convention,
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()

        ordered = list(
            PanelTag.objects.filter(panel=self.panel).order_by('priority').values_list('tag_id', flat=True)
        )
        self.assertEqual(ordered, [self.tag_b.pk, self.tag_a.pk])

    def test_form_initial_tags_follow_priority(self):
        from events.forms import PanelForm
        from events.models import PanelTag

        PanelTag.objects.filter(panel=self.panel, tag=self.tag_b).update(priority=0)
        PanelTag.objects.filter(panel=self.panel, tag=self.tag_a).update(priority=1)

        form = PanelForm(instance=self.panel, convention=self.convention)
        self.assertEqual(list(form.initial['tags']), [self.tag_b.pk, self.tag_a.pk])

    @override_settings(CONCAT_ENABLED=False, EVENTZILLA_ENABLED=False)
    def test_edit_page_shows_loading_state(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.create_user(username='staff', password='pass', is_staff=True)
        client = Client()
        client.force_login(user)
        response = client.get(f'/panel/{self.panel.pk}/edit/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="panel-form-loader"')
        self.assertContains(response, f'{self.panel.title} is loading')
        self.assertContains(response, 'id="panel-form-data"')
        self.assertContains(response, 'finishPanelFormLoading')



