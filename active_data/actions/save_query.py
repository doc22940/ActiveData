# encoding: utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Author: Kyle Lahnakoski (kyle@lahnakoski.com)
#
from __future__ import absolute_import, division, unicode_literals

import hashlib

from flask import Response

import jx_elasticsearch
from jx_python.containers.cube import Cube
from mo_dots import wrap
from mo_future import first
from mo_json import json2value
from mo_kwargs import override
from mo_logs import Log
from mo_logs.exceptions import Except
from mo_logs.strings import unicode2utf8
from mo_threads import Thread
from mo_threads.threads import register_thread
from mo_times.dates import Date
from pyLibrary import convert
from pyLibrary.env.elasticsearch import Cluster
from pyLibrary.env.flask_wrappers import cors_wrapper

HASH_BLOCK_SIZE = 100
DATA_TYPE = "query"

query_finder = None


@cors_wrapper
@register_thread
def find_query(hash):
    """
    FIND QUERY BY HASH, RETURN Response OBJECT
    :param hash:
    :return: Response OBJECT
    """
    try:
        hash = hash.split("/")[0]
        query = query_finder.find(hash)

        if not query:
            return Response(
                b'{"type": "ERROR", "template": "not found"}',
                status=404
            )
        else:
            return Response(
                unicode2utf8(query),
                status=200
            )
    except Exception as e:
        e = Except.wrap(e)
        Log.warning("problem finding query with hash={{hash}}", hash=hash, cause=e)
        return Response(
            unicode2utf8(convert.value2json(e)),
            status=400
        )


class SaveQueries(object):
    @override
    def __init__(self, host, index, type=DATA_TYPE, max_size=10, batch_size=10, kwargs=None):
        """
        settings ARE FOR THE ELASTICSEARCH INDEX
        """
        es = Cluster(kwargs).get_or_create_index(
            schema=json2value(convert.value2json(SCHEMA), leaves=True),
            limit_replicas=True,
            typed=False,
            kwargs=kwargs
        )
        es.add_alias(index)
        self.queue = es.threaded_queue(max_size=max_size, batch_size=batch_size, period=1)
        self.es = jx_elasticsearch.new_instance(es.settings)

    def find(self, hash):
        result = self.es.query({
            "select": ["hash", "query"],
            "from": "saved_queries",
            "where": {"prefix": {"hash": hash}},
            "format": "list"
        })

        try:
            hash = result.data[0].hash
            query = wrap(result.data[0]).query
            if len(query) == 0:
                return None
        except Exception:
            return None

        self.es.update({
            "update": self.es.name,
            "set": {"last_used": Date.now()},
            "where": {"eq": {"hash": hash}}
        })

        return query

    def save(self, query):
        """
        SAVE query TO ES FOR LATER RECOVERY
        :param query:
        :return: HAS TO USE FOR RECOVERY
        """
        query.meta = None
        json = convert.value2json(query)
        hash = unicode2utf8(json)

        # TRY MANY HASHES AT ONCE
        hashes = [None] * HASH_BLOCK_SIZE
        for i in range(HASH_BLOCK_SIZE):
            hash = hashlib.sha1(hash).digest()
            hashes[i] = hash

        short_hashes = [convert.bytes2base64(h[0:6]).replace("/", "_") for h in hashes]
        available = {h: True for h in short_hashes}

        existing = self.es.query({
            "from": "saved_queries",
            "where": {"terms": {"hash": short_hashes}},
            "meta": {"timeout": "2second"}
        })

        for e in Cube(select=existing.select, edges=existing.edges, data=existing.data).values():
            if e.query == json:
                return e.hash
            available[e.hash] = False

        # THIS WILL THROW AN ERROR IF THERE ARE NONE, HOW UNLUCKY!
        best = first(h for h in short_hashes if available[h])

        self.queue.add({
            "id": best,
            "value": {
                "hash": best,
                "create_time": Date.now(),
                "last_used": Date.now(),
                "query": json
            }
        })

        Log.note("Saved {{json}} query as {{hash}}", json=json, hash=best)

        return best

    def stop(self):
        try:
            self.queue.add(Thread.STOP)  # BE PATIENT, LET REST OF MESSAGE BE SENT
        except Exception as e:
            pass

        try:
            self.queue.close()
        except Exception as f:
            pass


SCHEMA = {
    "settings": {
        "index.number_of_shards": 3,
        "index.number_of_replicas": 2
    },
    "mappings": {
        "_default_": {
            "dynamic_templates": [
                {
                    "values_strings": {
                        "match": "*",
                        "match_mapping_type": "string",
                        "mapping": {
                            "type": "keyword"
                        }
                    }
                }
            ],
            "_all": {
                "enabled": False
            },
            "_source": {
                "enabled": True
            },
            "properties": {
                "create_time": {
                    "type": "double",
                    "store": True
                },
                "last_used": {
                    "type": "double",
                    "store": True
                },
                "hash": {
                    "type": "keyword",
                    "store": True
                },
                "query": {
                    "type": "text",
                    "store": True
                }
            }
        }
    }
}
