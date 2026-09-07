from pathlib import Path

path = Path('scripts/attach_nyc_water_signals.py')
text = path.read_text()
old = '''    args = parser.parse_args()\n    print(json.dumps(attach(args.output, args.cache), indent=2, sort_keys=True))\n'''
new = '''    args = parser.parse_args()\n    print(json.dumps(attach(args.output, args.cache), indent=2, sort_keys=True))\n\n    # The production CLI also emits bounded 2010-2024 DEP building-water context.\n    # The attach() function above remains current-signal-only so fixture/unit callers never trigger live history fetches.\n    from attach_historical_311_context import attach as attach_historical_context\n    from build_historical_311_context import load_current_bbls\n    from towersignal.historical_311_context import build_historical_context\n    from validate_historical_311_context import validate as validate_historical_context\n\n    historical_cache = args.output / "historical-311-context.json"\n    bbls = load_current_bbls(args.output / "systems.json")\n    historical_payload = build_historical_context(bbls, batch_size=200, page_size=5000)\n    historical_cache.write_text(json.dumps(historical_payload, separators=(",", ":")), encoding="utf-8")\n    print(json.dumps(validate_historical_context(historical_cache, require_production_volume=True), indent=2, sort_keys=True))\n    print(json.dumps(attach_historical_context(args.output, historical_cache), indent=2, sort_keys=True))\n'''
if old not in text:
    raise SystemExit('attach_nyc_water_signals.py main target not found')
path.write_text(text.replace(old, new, 1))
