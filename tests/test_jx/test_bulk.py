# encoding: utf-8
#
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
#

from __future__ import absolute_import, division, unicode_literals

from unittest import skipIf, skip

from jx_elasticsearch.es52 import agg_bulk
from jx_python import jx
from mo_dots import wrap, set_default
from mo_future import text, sort_using_key
from mo_logs import Log
from mo_threads import Till
from mo_times import MINUTE, Timer
from pyLibrary.env import http
from tests.test_jx import BaseTestCase, TEST_TABLE


class TestBulk(BaseTestCase):

    @skipIf(not agg_bulk.S3_CONFIG, "can not test S3")
    def test_bulk_query_list(self):
        data = wrap([{"a": "test" + text(i)} for i in range(1001)])
        expected = [{"a": r.a, "count": 1} for r in data]

        test = wrap({
            "data": data,
            "query": {
                "from": TEST_TABLE,
                "groupby": "a",
                "limit": len(data),
                "chunk_size": 100,
            },
            "expecting_list": {"data": expected},  # DUMMY, TO ENSURE LOADED
        })
        self.utils.execute_tests(test)

        test.query.format = "list"
        test.query.destination = "url"
        result = http.post_json(
            url=self.utils.testing.query,
            json=test.query,
        )

        timeout = Till(seconds=MINUTE.seconds)
        while not timeout:
            try:
                content = http.get_json(result.url)
                with Timer("compare results"):
                    sorted_content = jx.sort(content.data, "a")
                    sorted_expected = jx.sort(expected, "a")
                    self.assertEqual(sorted_content, sorted_expected)
                break
            except Exception as e:
                if "does not match expected" in e:
                    Log.error("failed", cause=e)
                Log.note("waiting for {{url}}", url=result.url)
                Till(seconds=2).wait()

        self.assertFalse(timeout, "timeout")

    @skipIf(not agg_bulk.S3_CONFIG, "can not test S3")
    def test_scroll_query_list(self):
        data = wrap([{"a": "test" + text(i)} for i in range(1001)])
        expected = data

        test = wrap({
            "data": data,
            "query": {
                "from": TEST_TABLE,
                "limit": len(data),
                "chunk_size": 100,
            },
            "expecting_list": {"data": expected},  # DUMMY, TO ENSURE LOADED
        })
        self.utils.execute_tests(test)

        test.query.format = "list"
        test.query.destination = "url"
        result = http.post_json(
            url=self.utils.testing.query,
            json=test.query,
        )

        timeout = Till(seconds=MINUTE.seconds)
        while not timeout:
            try:
                content = http.get_json(result.url)
                with Timer("compare results"):
                    sorted_content = jx.sort(content.data, "a")
                    sorted_expected = jx.sort(expected, "a")
                    self.assertEqual(sorted_content, sorted_expected)
                break
            except Exception as e:
                if "does not match expected" in e:
                    Log.error("failed", cause=e)
                Log.note("waiting for {{url}}", url=result.url)
                Till(seconds=2).wait()

        self.assertFalse(timeout, "timeout")

    @skipIf(not agg_bulk.S3_CONFIG, "can not test S3")
    def test_bulk_query_table(self):
        data = wrap([{"a": "test" + text(i)} for i in range(1001)])
        expected = [{"a": r.a, "count": 1} for r in data]

        test = wrap({
            "data": data,
            "query": {
                "from": TEST_TABLE,
                "groupby": "a",
                "limit": len(data),
                "chunk_size": 100,
            },
            "expecting_list": {"data": expected},  # DUMMY, TO ENSURE LOADED
        })
        self.utils.execute_tests(test)

        test.query.format = "table"
        test.query.destination = "url"
        result = http.post_json(
            url=self.utils.testing.query,
            json=test.query,
        )

        timeout = Till(seconds=MINUTE.seconds)
        while not timeout:
            try:
                content = http.get_json(result.url)
                with Timer("compare results"):
                    self.assertEqual(content.header, ["a", "count"])
                    sorted_content = jx.sort(content.data, 0)
                    sorted_expected = [(row.a, row.c) for row in jx.sort(expected, "a")]
                    self.assertEqual(sorted_content, sorted_expected)
                break
            except Exception as e:
                if "does not match expected" in e:
                    Log.error("failed", cause=e)
                Log.note("waiting for {{url}}", url=result.url)
                Till(seconds=2).wait()

        self.assertFalse(timeout, "timeout")

    @skipIf(not agg_bulk.S3_CONFIG, "can not test S3")
    def test_scroll_query_table(self):
        data = wrap([{"a": "test" + text(i)} for i in range(1001)])
        expected = jx.sort(data, "a")

        test = wrap({
            "data": data,
            "query": {
                "from": TEST_TABLE,
                "select": ["a"],
                "limit": len(data),
                "chunk_size": 100,
                "sort": "a"
            },
            "expecting_list": {"data": expected},  # DUMMY, TO ENSURE LOADED
        })
        self.utils.execute_tests(test)

        test.query.format = "table"
        test.query.sort = None
        test.query.destination = "url"
        result = http.post_json(
            url=self.utils.testing.query,
            json=test.query,
        )

        timeout = Till(seconds=MINUTE.seconds)
        while not timeout:
            try:
                content = http.get_json(result.url)
                with Timer("compare results"):
                    self.assertEqual(content.header, ["a"])
                    sorted_content = jx.sort(content.data, 0)
                    sorted_expected = [(row.a,) for row in expected]
                    self.assertEqual(sorted_content, sorted_expected)
                break
            except Exception as e:
                if "does not match expected" in e:
                    Log.error("failed", cause=e)
                Log.note("waiting for {{url}}", url=result.url)
                Till(seconds=2).wait()

        self.assertFalse(timeout, "timeout")
