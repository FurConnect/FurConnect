from datetime import date, time, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction

from events.models import (
    Convention,
    ConventionDay,
    Panel,
    PanelHost,
    PanelHostOrder,
    PanelTag,
    Room,
    Tag,
)


TAG_DEFS = [
    ('Fursuit', '#e91e63'),
    ('Art', '#2196f3'),
    ('Music', '#ff9800'),
    ('Gaming', '#9c27b0'),
    ('Writing', '#009688'),
    ('Social', '#ffc107'),
]

ROOM_NAMES = [
    'Main Stage',
    'Panel Room A',
    'Panel Room B',
    'Workshop Lab',
    'Dealer Den Annex',
]

HOST_NAMES = [
    'Alex Fox',
    'Sam Wolf',
    'Riley Paws',
    'Jordan Stripe',
    'Casey Howl',
    'Morgan Whisker',
    'Quinn Ember',
    'Taylor Drift',
]


# (day_offset, title, start, end, room_index, tag_names, host_indices, featured?, cancelled?, description)
PANEL_DEFS = [
    (0, 'Opening Ceremony', time(10, 0), time(11, 0), 0, ['Social'], [0, 1], True, False,
     'Kick off the weekend with announcements, giveaways, and a look at what is coming.'),
    (0, 'Fursuit 101', time(10, 0), time(11, 30), 1, ['Fursuit'], [2], False, False,
     'Build tips, comfort tricks, and how to survive a busy con day in suit.'),
    (0, 'Watercolor Critters', time(10, 30), time(12, 0), 3, ['Art'], [3, 4], False, False,
     'A hands-on intro to painting fluffy characters. Materials provided.'),
    (0, 'Drum Circle Warmup', time(11, 0), time(12, 0), 2, ['Music'], [5], False, False,
     'Loose rhythms and call-and-response for all skill levels.'),
    (0, 'Indie Game Showcase', time(12, 0), time(13, 30), 0, ['Gaming'], [6, 0], True, False,
     'Creators demo short furry-themed games and share postmortems.'),
    (0, 'Character Backstories', time(12, 30), time(13, 30), 1, ['Writing'], [7], False, False,
     'Workshop prompts for writing memorable original characters.'),
    (0, 'Dealer Den Meetup', time(13, 0), time(14, 0), 4, ['Social', 'Art'], [1, 3], False, False,
     'Meet artists and makers before the evening rush.'),
    (0, 'Fursuit Photoshoot', time(14, 0), time(15, 30), 0, ['Fursuit'], [2, 5], False, False,
     'Group photos on the main stage with volunteer photographers.'),
    (0, 'Pixel Art Jam', time(14, 0), time(15, 0), 3, ['Art', 'Gaming'], [6], False, False,
     'Build a tiny sprite together. Bring a laptop if you can.'),
    (0, 'Cancelled: Rooftop Howl', time(16, 0), time(17, 0), 2, ['Social'], [0], False, True,
     'Moved indoors due to weather. See evening social instead.'),
    (0, 'Evening Social Mixer', time(19, 0), time(21, 0), 0, ['Social', 'Music'], [0, 1, 5], True, False,
     'Casual hangout with a DJ set and icebreaker games.'),

    (1, 'Morning Yoga Stretch', time(9, 0), time(10, 0), 3, ['Social'], [4], False, False,
     'Gentle movement to shake off yesterday. Mats available.'),
    (1, 'Headshot Critique', time(10, 0), time(11, 30), 1, ['Art'], [3, 7], False, False,
     'Bring prints or a tablet for friendly portfolio feedback.'),
    (1, 'Con Choir Rehearsal', time(10, 0), time(11, 0), 0, ['Music'], [5, 1], False, False,
     'Learn a short group number for the closing ceremony.'),
    (1, 'Tabletop One-Shots', time(11, 0), time(13, 0), 2, ['Gaming'], [6, 2], True, False,
     'Drop-in RPG tables. Characters provided for newcomers.'),
    (1, 'Suit Repair Clinic', time(12, 0), time(13, 30), 4, ['Fursuit'], [2], False, False,
     'Sew-on patches, foam fixes, and cooling hacks.'),
    (1, 'Flash Fiction Relay', time(13, 0), time(14, 0), 1, ['Writing'], [7, 0], False, False,
     'Pass a story around the room, one paragraph at a time.'),
    (1, 'Artist Alley Tips', time(14, 0), time(15, 0), 3, ['Art'], [3], False, False,
     'Pricing, displays, and surviving your first alley weekend.'),
    (1, 'Dance Practice', time(15, 0), time(16, 30), 0, ['Music', 'Fursuit'], [5, 2], False, False,
     'Simple choreography that works in and out of suit.'),
    (1, 'Late Night Board Games', time(20, 0), time(22, 0), 2, ['Gaming', 'Social'], [6, 4], False, False,
     'Party games and co-op classics until the venue closes.'),

    (2, 'Brunch & Badges', time(10, 0), time(11, 0), 4, ['Social'], [1], False, False,
     'Trade badges, stickers, and stories over coffee.'),
    (2, 'Charcoal Sketch Lab', time(10, 30), time(12, 0), 3, ['Art'], [3, 7], False, False,
     'Gesture drawing with live costumed models.'),
    (2, 'Speedrun Spotlight', time(11, 0), time(12, 30), 0, ['Gaming'], [6], True, False,
     'Watch runners chase PBs in classic animal mascot games.'),
    (2, 'Lyric Writing Circle', time(12, 0), time(13, 0), 1, ['Music', 'Writing'], [5, 7], False, False,
     'Turn a character idea into a verse.'),
    (2, 'Closing Ceremony', time(15, 0), time(16, 0), 0, ['Social', 'Music'], [0, 1, 5], True, False,
     'Highlights reel, choir performance, and thank-yous.'),
]


class Command(BaseCommand):
    help = 'Seed a sample convention with rooms, hosts, tags, and a full weekend schedule.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Replace the existing convention and related schedule data.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        existing = Convention.objects.first()
        if existing and not options['force']:
            self.stdout.write(
                self.style.WARNING(
                    f'Convention already exists: "{existing.name}" (id={existing.pk}). '
                    'Re-run with --force to replace it.'
                )
            )
            return

        if existing:
            self.stdout.write(f'Removing existing convention "{existing.name}"...')
            existing.delete()

        start = date(2026, 7, 10)
        convention = Convention(
            name='FurConnect Demo Con',
            description=(
                'A sample weekend schedule for trying list/grid views, filters, '
                'and PDF exports.'
            ),
            location='Riverfront Convention Center',
            start_date=start,
            end_date=start + timedelta(days=2),
        )
        # Bypass one-convention clean when we just cleared; save() still runs clean.
        convention.save()

        days = [
            ConventionDay.objects.create(
                convention=convention,
                date=start + timedelta(days=offset),
                description=['Friday', 'Saturday', 'Sunday'][offset],
            )
            for offset in range(3)
        ]

        rooms = [
            Room.objects.create(convention=convention, name=name, sort_order=idx)
            for idx, name in enumerate(ROOM_NAMES)
        ]

        tags = {}
        for name, color in TAG_DEFS:
            tag, _ = Tag.objects.update_or_create(
                name=name,
                defaults={'color': color},
            )
            tags[name] = tag

        hosts = [
            PanelHost.objects.create(name=name)
            for name in HOST_NAMES
        ]

        created = 0
        for (
            day_offset, title, start_t, end_t, room_idx,
            tag_names, host_idxs, featured, cancelled, description,
        ) in PANEL_DEFS:
            panel = Panel.objects.create(
                title=title,
                description=description,
                convention_day=days[day_offset],
                start_time=start_t,
                end_time=end_t,
                room=rooms[room_idx],
                is_featured=featured,
                cancelled=cancelled,
            )
            for priority, tag_name in enumerate(tag_names):
                PanelTag.objects.create(panel=panel, tag=tags[tag_name], priority=priority)
            for priority, host_idx in enumerate(host_idxs):
                PanelHostOrder.objects.create(
                    panel=panel,
                    host=hosts[host_idx],
                    priority=priority,
                )
            created += 1

        self.stdout.write(self.style.SUCCESS(
            f'Seeded "{convention.name}" (id={convention.pk}) with '
            f'{len(days)} days, {len(rooms)} rooms, {created} panels.'
        ))
        self.stdout.write(f'Open /convention/{convention.pk}/ to view the schedule.')
