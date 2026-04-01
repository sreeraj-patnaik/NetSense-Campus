from django.core.management.base import BaseCommand

from heatmap.aggregation import rebuild_aggregates_for_floor
from heatmap.utils import ensure_floor_plan, get_floor_registry


class Command(BaseCommand):
    help = "Rebuild CellAggregate rows for all configured blocks and floors."

    def handle(self, *args, **options):
        registry = get_floor_registry()
        blocks = registry["blocks"]
        block_floors = registry["block_floors"]
        total = 0

        for block in blocks:
            for floor in block_floors.get(block, []):
                floor_plan = ensure_floor_plan(block, floor)
                rebuild_aggregates_for_floor(floor_plan)
                total += 1

        self.stdout.write(self.style.SUCCESS(f"Rebuilt aggregates for {total} block/floor pairs."))
