from pathlib import Path

path = Path('.github/workflows/pages.yml')
text = path.read_text()
old = """      - name: Attach exact-BBL/BIN NYC building-water signals
        run: python scripts/attach_nyc_water_signals.py --output public/data --cache public/data/nyc-water-signals.json
      - name: Build exact-count NYC lead service-line cache
"""
new = """      - name: Attach exact-BBL/BIN NYC building-water signals
        run: python scripts/attach_nyc_water_signals.py --output public/data --cache public/data/nyc-water-signals.json
      - name: Build exact-BBL CMS institutional facility context
        timeout-minutes: 15
        run: python scripts/build_cms_institutional_context.py --systems public/data/systems.json --output public/data/cms-institutional-context.json --geosearch-workers 4
      - name: Validate CMS institutional facility context
        run: python scripts/validate_cms_institutional_context.py --cache public/data/cms-institutional-context.json --require-production-volume
      - name: Attach exact-BBL CMS institutional facility context
        run: python scripts/attach_cms_institutional_context.py --output public/data --cache public/data/cms-institutional-context.json
      - name: Build exact-count NYC lead service-line cache
"""
if old not in text:
    raise SystemExit('CMS Pages insertion target not found')
path.write_text(text.replace(old, new, 1))
