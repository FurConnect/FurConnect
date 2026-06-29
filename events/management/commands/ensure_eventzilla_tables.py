from django.core.management.base import BaseCommand
from django.db import connection, OperationalError
from django.db.migrations.recorder import MigrationRecorder

from events.models import EventzillaAttendee, PanelRSVP


class Command(BaseCommand):
    help = 'Create Eventzilla attendee tables when migrations cannot be written (e.g. root-owned migrations/).'

    def handle(self, *args, **options):
        table_names = connection.introspection.table_names()
        created = False

        with connection.schema_editor() as schema_editor:
            if EventzillaAttendee._meta.db_table not in table_names:
                schema_editor.create_model(EventzillaAttendee)
                created = True
                self.stdout.write(self.style.SUCCESS('Created events_eventzillaattendee table.'))
            else:
                existing_columns = {
                    column.name
                    for column in connection.introspection.get_table_description(
                        connection.cursor(),
                        EventzillaAttendee._meta.db_table,
                    )
                }
                if 'is_site_admin' not in existing_columns:
                    schema_editor.add_field(
                        EventzillaAttendee,
                        EventzillaAttendee._meta.get_field('is_site_admin'),
                    )
                    self.stdout.write(self.style.SUCCESS('Added is_site_admin to events_eventzillaattendee.'))

            if PanelRSVP._meta.db_table in table_names:
                try:
                    schema_editor.alter_field(
                        PanelRSVP,
                        PanelRSVP._meta.get_field('avatar_url'),
                        PanelRSVP._meta.get_field('avatar_url'),
                    )
                except (OperationalError, NotImplementedError):
                    pass

        recorder = MigrationRecorder(connection)
        if not recorder.migration_qs.filter(app='events', name='0002_eventzilla_attendee_profile').exists():
            recorder.record_applied('events', '0002_eventzilla_attendee_profile')
            self.stdout.write(self.style.SUCCESS('Recorded events.0002_eventzilla_attendee_profile as applied.'))
        if not recorder.migration_qs.filter(app='events', name='0003_eventzillaattendee_is_site_admin').exists():
            recorder.record_applied('events', '0003_eventzillaattendee_is_site_admin')
            self.stdout.write(self.style.SUCCESS('Recorded events.0003_eventzillaattendee_is_site_admin as applied.'))

        if not created:
            self.stdout.write('Eventzilla tables already present.')
