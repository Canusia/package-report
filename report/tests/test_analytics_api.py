from django.test import Client, TestCase

from .factories import login, make_report, make_scheduler, make_user

SUMMARY = '/ce/reports/api/run_summary/'
ALL_RUNS = '/ce/reports/api/all_report_scheduler/'


class RunSummaryTests(TestCase):
    def setUp(self):
        self.client = Client()
        login(self.client, make_user('root', superuser=True))
        self.report = make_report(title='Counted Report')
        self.alice = make_user('alice')

    def test_one_month_window_excludes_older_runs(self):
        make_scheduler(self.report, self.alice, status='ran', days_ago=3)
        make_scheduler(self.report, self.alice, status='ran', days_ago=40)

        one_month = self.client.get(SUMMARY, {'window': '1m'}).json()
        three_month = self.client.get(SUMMARY, {'window': '3m'}).json()

        self.assertEqual(one_month['totals']['total'], 1)
        self.assertEqual(three_month['totals']['total'], 2)

    def test_totals_match_by_report_sum(self):
        make_scheduler(self.report, self.alice, status='ran')
        make_scheduler(self.report, self.alice, status='error')
        make_scheduler(self.report, self.alice, status='pending')

        body = self.client.get(SUMMARY, {'window': '1m'}).json()
        self.assertEqual(body['totals'],
                         {'pending': 1, 'ran': 1, 'error': 1, 'total': 3})
        self.assertEqual(sum(r['total'] for r in body['by_report']), 3)
        self.assertEqual(body['by_report'][0]['title'], 'Counted Report')
        self.assertEqual(body['by_report'][0]['ran'], 1)
        self.assertEqual(body['by_user'][0]['email'], 'alice@example.com')
        self.assertEqual(body['by_user'][0]['total'], 3)

    def test_six_and_twelve_month_windows(self):
        make_scheduler(self.report, self.alice, status='ran', days_ago=3)
        make_scheduler(self.report, self.alice, status='ran', days_ago=120)
        make_scheduler(self.report, self.alice, status='ran', days_ago=300)

        totals = {
            w: self.client.get(SUMMARY, {'window': w}).json()['totals']['total']
            for w in ('1m', '3m', '6m', '12m')
        }
        self.assertEqual(totals, {'1m': 1, '3m': 1, '6m': 2, '12m': 3})

    def test_invalid_window_rejected(self):
        self.assertEqual(
            self.client.get(SUMMARY, {'window': '99y'}).status_code, 400)

    def test_defaults_to_one_month(self):
        self.assertEqual(
            self.client.get(SUMMARY).json()['window'], '1m')

    def test_non_superuser_denied(self):
        client = Client()
        login(client, make_user('plain_ce'))
        self.assertEqual(client.get(SUMMARY).status_code, 403)


class AllReportSchedulerTests(TestCase):
    def setUp(self):
        self.report = make_report(title='Shared Report')
        self.alice = make_user('alice')
        self.bob = make_user('bob')
        make_scheduler(self.report, self.alice, status='pending')
        make_scheduler(self.report, self.bob, status='ran')

    def _as(self, user):
        client = Client()
        login(client, user)
        return client

    def test_superuser_sees_every_users_runs(self):
        # A bare GET (no datatables query params) falls back to DRF's plain
        # page shape ({'count', 'results'}) rather than the datatables
        # envelope ({'recordsTotal', 'recordsFiltered', 'data'}) — see
        # DatatablesPageNumberPagination. Request format=datatables
        # explicitly to get the 'data' envelope the brief's tests assume.
        resp = self._as(make_user('root', superuser=True)).get(
            ALL_RUNS, {'format': 'datatables'})
        self.assertEqual(resp.status_code, 200)
        emails = {row['requested_by'] for row in resp.json()['data']}
        self.assertEqual(emails, {'alice@example.com', 'bob@example.com'})

    def test_status_filter(self):
        resp = self._as(make_user('root', superuser=True)).get(
            ALL_RUNS, {'status': 'pending', 'format': 'datatables'})
        data = resp.json()['data']
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['status'], 'pending')

    def test_plain_ce_user_denied(self):
        self.assertEqual(self._as(self.alice).get(ALL_RUNS).status_code, 403)

    def test_existing_endpoint_still_scoped_to_caller(self):
        """The pre-existing report_scheduler endpoint must NOT be widened."""
        resp = self._as(self.alice).get(
            '/ce/reports/api/report_scheduler/', {'format': 'datatables'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()['data']), 1)

    def test_ordering_by_each_column_path_returns_200(self):
        client = self._as(make_user('root', superuser=True))
        paths = ['created_on', 'report__title', 'created_by__last_name',
                 'status']
        for index, path in enumerate(paths):
            params = {
                'draw': 1, 'start': 0, 'length': 10,
                'order[0][column]': index, 'order[0][dir]': 'asc',
                'format': 'datatables',
            }
            for col_index, col_path in enumerate(paths):
                params[f'columns[{col_index}][data]'] = col_path
                params[f'columns[{col_index}][name]'] = col_path
                params[f'columns[{col_index}][orderable]'] = 'true'
                params[f'columns[{col_index}][searchable]'] = 'true'
            with self.subTest(path=path):
                self.assertEqual(client.get(ALL_RUNS, params).status_code, 200)
