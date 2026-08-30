from django.core.management.base import BaseCommand
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder

from events.models import Room


class Command(BaseCommand):
    help = 'Add events_room.sort_order when the column is missing (e.g. deploy before migrate).'

    def handle(self, *args, **options):
        table_names = connection.introspection.table_names()
        table = Room._meta.db_table
        if table not in table_names:
            self.stdout.write(f'{table} does not exist yet; run migrate first.')
            return

        existing_columns = {
            column.name
            for column in connection.introspection.get_table_description(
                connection.cursor(),
                table,
            )
        }

        if 'sort_order' not in existing_columns:
            with connection.schema_editor() as schema_editor:
                schema_editor.add_field(Room, Room._meta.get_field('sort_order'))
            self._backfill_sort_order()
            self.stdout.write(self.style.SUCCESS(f'Added sort_order to {table}.'))
        else:
            self.stdout.write(f'{table}.sort_order already present.')

        recorder = MigrationRecorder(connection)
        for name in ('0002_room_sort_order',):
            if not recorder.migration_qs.filter(app='events', name=name).exists():
                recorder.record_applied('events', name)
                self.stdout.write(self.style.SUCCESS(f'Recorded events.{name} as applied.'))

    def _backfill_sort_order(self):
        convention_ids = (
            Room.objects.order_by('convention_id')
            .values_list('convention_id', flat=True)
            .distinct()
        )
        for convention_id in convention_ids:
            rooms = list(
                Room.objects.filter(convention_id=convention_id).order_by('name', 'id')
            )
            for index, room in enumerate(rooms):
                room.sort_order = index
            if rooms:
                Room.objects.bulk_update(rooms, ['sort_order'])
