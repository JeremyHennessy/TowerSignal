from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class DailySourceRefreshWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.pages = (ROOT / '.github/workflows/pages.yml').read_text(encoding='utf-8')
        self.azure = (ROOT / '.github/workflows/azure-data-refresh.yml').read_text(encoding='utf-8')
        self.acris = (ROOT / '.github/workflows/acris-cache.yml').read_text(encoding='utf-8')
        self.checkbook = (ROOT / '.github/workflows/checkbook-cache.yml').read_text(encoding='utf-8')
        self.oath = (ROOT / '.github/workflows/oath-cache-refresh.yml').read_text(encoding='utf-8')

    def test_canonical_pages_release_runs_daily_after_durable_cache_windows(self):
        self.assertIn("cron: '17 10 * * *'", self.pages)
        self.assertIn("cron: '23 8 * * *'", self.acris)
        self.assertIn("cron: '41 8 * * *'", self.checkbook)
        self.assertIn("cron: '23 */6 * * *'", self.oath)

    def test_scheduled_acris_refresh_does_not_launch_competing_pages_release(self):
        self.assertIn(
            "if: ${{ github.event_name == 'workflow_dispatch' || github.event_name == 'push' }}",
            self.acris,
        )
        self.assertNotIn("if: ${{ github.event_name != 'pull_request' }}\n    needs: persist-cache\n    runs-on: ubuntu-latest\n    steps:\n      - name: Deploy product with last verified ACRIS cache", self.acris)

    def test_acris_pr_integration_builds_legacy_dob_before_source_health(self):
        build = 'python scripts/build_legacy_dob_project_cache.py --output public/data'
        validate = 'python scripts/validate_legacy_dob_project_cache.py --cache public/data/legacy-dob-projects.json --max-age-days 1 --require-production-volume'
        attach = 'python scripts/attach_legacy_dob_project_context.py --output public/data --cache public/data/legacy-dob-projects.json'
        source_health = 'python scripts/build_source_health.py --output public/data --previous-snapshot .history-store/data/history/latest.json'
        for command in (build, validate, attach, source_health):
            self.assertIn(command, self.acris)
        self.assertLess(self.acris.index(build), self.acris.index(validate))
        self.assertLess(self.acris.index(validate), self.acris.index(attach))
        self.assertLess(self.acris.index(attach), self.acris.index(source_health))

    def test_acris_pr_integration_validates_nys_history_without_full_product_audit(self):
        partial = "PYTHONPATH=scripts python -c \"from pathlib import Path; from validate_nys_history_store import validate_history_size; validate_history_size(Path('public/data/history/nys/latest.json'), Path('.history-store/data/history/nys/latest.json'))\""
        full = 'python scripts/validate_nys_history_store.py --current public/data/history/nys/latest.json --previous .history-store/data/history/nys/latest.json'
        self.assertIn(partial, self.acris)
        self.assertNotIn(full, self.acris)
        self.assertNotIn('python scripts/build_coverage_audit.py --output public/data', self.acris)

    def test_daily_pages_builds_and_attaches_historical_311_before_source_health(self):
        build = 'python scripts/build_historical_311_context.py --systems public/data/systems.json --output public/data/historical-311-context.json'
        validate = 'python scripts/validate_historical_311_context.py --cache public/data/historical-311-context.json --require-production-volume'
        attach = 'python scripts/attach_historical_311_context.py --output public/data --cache public/data/historical-311-context.json'
        source_health = 'python scripts/build_source_health.py --output public/data --previous-snapshot .history-store/data/history/latest.json'
        for command in (build, validate, attach, source_health):
            self.assertIn(command, self.pages)
        self.assertLess(self.pages.index(build), self.pages.index(validate))
        self.assertLess(self.pages.index(validate), self.pages.index(attach))
        self.assertLess(self.pages.index(attach), self.pages.index(source_health))

    def test_daily_pages_publishes_validated_coverage_audit_after_current_history(self):
        build = 'python scripts/build_coverage_audit.py --output public/data'
        validate = 'python scripts/validate_coverage_audit.py --report public/data/coverage-audit.json'
        history = 'python scripts/build_history.py --output public/data --previous-snapshot .history-store/data/history/latest.json --previous-events .history-store/data/history/events.json'
        history_validate = 'python scripts/validate_history_store.py --current public/data/history/latest.json --previous .history-store/data/history/latest.json'
        for command in (build, validate, history, history_validate):
            self.assertIn(command, self.pages)
        self.assertLess(self.pages.index(history), self.pages.index(history_validate))
        self.assertLess(self.pages.index(history_validate), self.pages.index(build))
        self.assertLess(self.pages.index(build), self.pages.index(validate))
        self.assertLess(self.pages.index('python scripts/attach_acris_health.py --output public/data'), self.pages.index(build))

    def test_blob_data_refresh_preserves_pages_critical_runtime_sources(self):
        commands = (
            'python scripts/build_property_enforcement_cache.py --systems public/data/systems.json --output public/data/property-enforcement.json',
            'python scripts/validate_property_enforcement_cache.py --cache public/data/property-enforcement.json --max-age-days 1 --require-production-universe',
            'python scripts/attach_property_enforcement.py --output public/data --cache public/data/property-enforcement.json',
            'python scripts/build_legionella_alert_cache.py --output public/data/legionella-alerts.json',
            'python scripts/validate_legionella_alert_cache.py --cache public/data/legionella-alerts.json --max-age-days 1 --require-clean-retrieval',
            'python scripts/build_historical_311_context.py --systems public/data/systems.json --output public/data/historical-311-context.json',
            'python scripts/validate_historical_311_context.py --cache public/data/historical-311-context.json --require-production-volume',
            'python scripts/attach_historical_311_context.py --output public/data --cache public/data/historical-311-context.json',
            'python scripts/build_coverage_audit.py --output public/data',
            'python scripts/validate_coverage_audit.py --report public/data/coverage-audit.json',
            'python scripts/build_legionella_matches.py --data public/data',
            'python scripts/attach_reviewed_intelligence.py --output public/data',
            'python scripts/validate_reviewed_intelligence.py --output public/data',
        )
        for command in commands:
            with self.subTest(command=command):
                self.assertIn(command, self.pages)
                self.assertIn(command, self.azure)

        source_health = 'python scripts/build_source_health.py --output public/data --previous-snapshot .history-store/data/history/latest.json'
        historical_311 = 'python scripts/attach_historical_311_context.py --output public/data --cache public/data/historical-311-context.json'
        coverage = 'python scripts/build_coverage_audit.py --output public/data'
        history_validate = 'python scripts/validate_history_store.py --current public/data/history/latest.json --previous .history-store/data/history/latest.json'
        legionella_matches = 'python scripts/build_legionella_matches.py --data public/data'
        reviewed = 'python scripts/attach_reviewed_intelligence.py --output public/data'
        for workflow in (self.pages, self.azure):
            self.assertLess(workflow.index(historical_311), workflow.index(source_health))
            self.assertLess(workflow.index(history_validate), workflow.index(coverage))
            self.assertLess(workflow.index(coverage), workflow.index(legionella_matches))
            self.assertLess(workflow.index(legionella_matches), workflow.index(reviewed))

    def test_daily_pages_uses_two_day_acris_freshness_guard(self):
        self.assertIn(
            'python scripts/validate_acris_cache.py --cache .acris-store/data/acris/cache.json --max-age-days 2 --require-production-volume',
            self.pages,
        )
        self.assertNotIn(
            'python scripts/validate_acris_cache.py --cache .acris-store/data/acris/cache.json --max-age-days 30 --require-production-volume',
            self.pages,
        )


if __name__ == '__main__':
    unittest.main()
