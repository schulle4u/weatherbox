"""Command-line interface for Weatherbox operations."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from weatherbox.config import load_config
from weatherbox.errors import ConfigurationError, WeatherboxError
from weatherbox.logging_setup import configure_logging
from weatherbox.models import AnnouncementKind
from weatherbox.service import WeatherboxService


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(prog="wb-announcer", description="Weatherbox audio asset generator")
    parser.add_argument("-c", "--config", type=Path, default=Path("config.yaml"))
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("run", help="Generate all currently due announcements")
    subparsers.add_parser("weather-update", help="Update weather cache for all locations")
    subparsers.add_parser("status", help="Output status as JSON")

    for command, help_text in (
        ("generate-half-hour", "Generate the next half-hourly announcement for all locations"),
        ("generate-full-hour", "Generate the next hourly announcement for all locations"),
        ("generate-all", "Generate both announcements for all locations"),
    ):
        child = subparsers.add_parser(command, help=help_text)
        child.add_argument("--at", help="Playback time as ISO-8601 value")

    location = subparsers.add_parser("generate-location", help="Generate both announcements for  a specific location")
    location.add_argument("location_id")
    location.add_argument("--at", help="Playback time as ISO-8601 value")

    time_parser = subparsers.add_parser("generate-time", help="Create a custom announcement")
    time_parser.add_argument("location_id")
    time_parser.add_argument("kind", choices=[kind.value for kind in AnnouncementKind])
    time_parser.add_argument("--at", help="Playback time as ISO-8601 value")
    return parser


def _parse_time(value: str | None) -> datetime | None:
    """Parse an optional ISO-8601 timestamp and ensure it is timezone-aware."""
    if value is None:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.astimezone()
    return parsed


def main(argv: list[str] | None = None) -> int:
    """Run the requested command and return its process exit status."""
    args = build_parser().parse_args(argv)
    try:
        config = load_config(args.config)
        configure_logging(config.application.log_level, config.application.json_logs)
        service = WeatherboxService(config)

        if args.command == "run":
            results = service.run_due()
        elif args.command == "weather-update":
            results = service.update_weather()
        elif args.command == "status":
            print(json.dumps(service.status(), ensure_ascii=False, indent=2))
            return 0
        else:
            at = _parse_time(args.at)
            if args.command == "generate-half-hour":
                locations = config.enabled_locations
                kinds = (AnnouncementKind.HALF_HOUR,)
            elif args.command == "generate-full-hour":
                locations = config.enabled_locations
                kinds = (AnnouncementKind.FULL_HOUR,)
            elif args.command == "generate-all":
                locations = config.enabled_locations
                kinds = tuple(AnnouncementKind)
            else:
                location_id = args.location_id
                if location_id not in config.locations:
                    raise ConfigurationError(f"Unknown location: {location_id}")
                locations = (config.locations[location_id],)
                if args.command == "generate-time":
                    kinds = (AnnouncementKind(args.kind),)
                else:
                    kinds = tuple(AnnouncementKind)
            results = service.generate_many(service.manual_items(locations, kinds, at))

        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 1 if any(value is False or str(value).startswith("ERROR:") for value in results.values()) else 0
    except (ConfigurationError, WeatherboxError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
