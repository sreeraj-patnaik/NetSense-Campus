from random import choice, randint

from django.core.management.base import BaseCommand

from heatmap.models import Scan
from heatmap.utils import get_floor_dimensions, get_floor_registry, get_service_providers


class Command(BaseCommand):
    help = "Seed random scan data for all configured blocks/floors."

    def add_arguments(self, parser):
        parser.add_argument(
            "--per-floor",
            type=int,
            default=24,
            help="Number of random scan points to create per block/floor pair (default: 24).",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing scans before seeding new demo data.",
        )

    def handle(self, *args, **options):
        per_floor = max(1, options["per_floor"])

        if options["clear"]:
            deleted_count, _ = Scan.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Deleted {deleted_count} existing scans."))

        providers = get_service_providers()
        registry = get_floor_registry()
        blocks = registry["blocks"]
        block_floors = registry["block_floors"]

        to_create = []
        for block in blocks:
            for floor in block_floors.get(block, []):
                floor_dims = get_floor_dimensions(block, floor)
                rows = floor_dims["rows"]
                cols = floor_dims["cols"]
                for _ in range(per_floor):
                    mode = choice([Scan.WIFI, Scan.MOBILE])
                    mode_providers = providers.get(mode, [])
                    service_provider = choice(mode_providers) if mode_providers else "Unknown"
                    if mode == Scan.WIFI:
                        network_name = f"{block}-F{floor}-AP-{randint(1, 8):02d}"
                    else:
                        network_name = f"{service_provider or 'Carrier'}-Data"

                    to_create.append(
                        Scan(
                            block=block,
                            floor=floor,
                            cell_x=randint(0, cols - 1),
                            cell_y=randint(0, rows - 1),
                            mode=mode,
                            service_provider=service_provider,
                            network_name=network_name,
                            signal_strength=randint(-95, -35),
                        )
                    )

        Scan.objects.bulk_create(to_create)
        self.stdout.write(
            self.style.SUCCESS(
                f"Created {len(to_create)} demo scans "
                f"({per_floor} per block/floor across {len(blocks)} blocks)."
            )
        )
