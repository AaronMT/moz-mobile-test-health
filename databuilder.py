#! /usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

'''
Small treeherder-client script for fetching push and
job metadata from provided configuration and
building a sharable JSON dataset from the Treeherder API
through the existing API client:

This script is heavily tailored to the needs of the
Mozilla Mobile Test Engineering team, and is not intended
to be a general purpose TreeHerder client.

Uses:
  - TreeHerder
  - Taskcluster
  - Github
'''

import gzip
import json
import logging
import os
import re
import ssl
import urllib.error
import urllib.request as request
from datetime import datetime
from statistics import mean

from junitparser import Attr, Failure, JUnitXml, TestSuite

from lib.treeherder import TreeherderHelper

ssl._create_default_https_context = ssl._create_unverified_context

logging.basicConfig(filename='output.log', filemode='w', level=logging.INFO)
logger = logging.getLogger(__name__)


def serialize_sets(obj):
    if isinstance(obj, set):
        return list(obj)

    return obj


class _TestSuite(TestSuite):
    flakes = Attr()


class databuilder:

    def __init__(self):
        pass

    def build_complete_dataset(self, args):

        client = TreeherderHelper(args.project)
        pushes = client.get_pushes()
        results, disabled_tests = ([] for i in range(2))
        global _github_details

        print(f"\nFetching [{len(client.global_configuration.sections())}] in [{args.project}] {client.project_configuration.sections()}", end='\n\n')

        for job in client.project_configuration.sections():
            durations, outcomes, dataset = ([] for i in range(3))

            print('Fetching result [{0}] in [{1}] ({2} max pushes) from'
                  ' the past [{3}] day(s) ...'.format(
                      client.project_configuration[job]['result'],
                      client.project_configuration[job]['symbol'],
                      client.global_configuration['pushes']['maxcount'],
                      client.global_configuration['pushes']['days']), end='\n')

            for _push in sorted(pushes, key=lambda push: push['id']):
                jobs = client.get_client().get_jobs(
                    project=args.project,
                    push_id=_push['id'],
                    tier=client.project_configuration[job]['tier'],
                    job_type_symbol=client.project_configuration[job]['symbol'],
                    result=client.project_configuration[job]['result'],
                    job_group_symbol=client.project_configuration[job]['group_symbol'],
                    who=client.global_configuration['filters']['author']

                )
                for _job in jobs:
                    _matrix_outcome_details = None
                    _test_details = []
                    _revSHA = None

                    _log = client.get_client().get_job_log_url(
                        project=args.project,
                        job_id=_job['id']
                    )
                    _log = ' '.join([str(_log_url['url']) for _log_url in _log])

                    # TaskCluster
                    try:
                        # Dependent on public artifact visibility
                        if (re.compile("^(ui-|legacy){1}.*")).search(
                            client.project_configuration[job]['symbol']
                        ):
                            # Matrix (i.e, matrix_ids.json) generated from Flank
                            with request.urlopen(
                                '{0}/{1}/{2}/public/results/{3}'.format(
                                    client.global_configuration['taskcluster']['artifacts'],
                                    _job['task_id'],
                                    _job['retry_id'],
                                    client.global_configuration['artifacts']['matrix']
                                )
                            ) as resp:
                                data = json.loads(
                                    gzip.decompress(resp.read()) if resp.headers.get('Content-Encoding') == 'gzip' else resp.read()
                                )
                                for key, value in data.items():
                                    _matrix_general_details = {
                                        "webLink": value['webLink'],
                                        "gcsPath": value['gcsPath']
                                    }
                                    _matrix_outcome_details = value['axes']

                            # Disabled tests (if requested) [TODO: output to file]
                            if args.disabled_tests:
                                with request.urlopen(
                                    '{0}/{1}/{2}/public/results/{3}'.format(
                                        client.global_configuration
                                        ['taskcluster']['artifacts'],
                                        _job['task_id'],
                                        _job['retry_id'],
                                        client.global_configuration
                                        ['artifacts']['shards']
                                    )
                                ) as resp:
                                    data = json.loads(
                                        gzip.decompress(resp.read()) if resp.headers.get('Content-Encoding') == 'gzip' else resp.read()
                                    )
                                    for key, value in data.items():
                                        if (value['junit-ignored'] not in
                                                disabled_tests):
                                            disabled_tests.append(
                                                value['junit-ignored'])

                            # JUnitReport (i.e, FullJUnitReport.xml)
                            with request.urlopen(
                                '{0}/{1}/{2}/public/results/{3}'.format(
                                    client.global_configuration['taskcluster']
                                    ['artifacts'],
                                    _job['task_id'],
                                    _job['retry_id'],
                                    client.global_configuration['artifacts']
                                    ['report']
                                )
                            ) as resp:
                                data = JUnitXml.fromstring(
                                    gzip.decompress(resp.read()) if resp.headers.get('Content-Encoding') == 'gzip' else resp.read()
                                )
                                for suite in data:
                                    cur_suite = _TestSuite.fromelem(suite)
                                    if cur_suite.flakes == '1':
                                        for case in suite:
                                            # TOOD: Should I check for flaky=true?
                                            if case.result:
                                                _test_details.append({
                                                    'name': case.name,
                                                    'result': 'flaky',
                                                })
                                    else:
                                        for case in suite:
                                            for entry in case.result:
                                                if isinstance(entry, Failure):
                                                    _test_details.append({
                                                        'name': case.name,
                                                        'result': 'failure',
                                                    })
                                                break
                        else:
                            pass

                        # TaskCluster: payload mobile revision
                        with request.urlopen('{0}/api/queue/v1/task/{1}/'.format(
                            client.global_configuration['taskcluster']['host'],
                            _job['task_id'])
                        ) as resp:
                            data = json.loads(
                                gzip.decompress(resp.read()) if resp.headers.get('Content-Encoding') == 'gzip' else resp.read()
                            )
                            _revSHA = data['payload']['env']['MOBILE_HEAD_REV']
                    except urllib.error.URLError as err:
                        print(f"Artifact(s) not available for {_job['task_id']}")
                        raise SystemExit(err)

                    # Github
                    try:
                        with request.urlopen(
                            request.Request(
                                url='{0}/commits/{1}/pulls'.format(
                                    client.global_configuration['project']['url'],
                                    _revSHA
                                ),
                                headers={
                                    'Accept':
                                    'application/vnd.github+json',
                                    'Authorization':
                                    'token %s' % os.environ.get('GITHUB_TOKEN')
                                }
                            )
                        ) as resp:
                            source = resp.read()
                            _github_data = json.loads(source)
                            for _data in _github_data:
                                _github_details = _data
                    except urllib.error.URLError as err:
                        print(f"Github API error: {err}")
                        raise SystemExit(err)

                    # Stitch together dataset from TaskCluster and Github
                    dt_obj_start = datetime.fromtimestamp(_job['start_timestamp'])
                    dt_obj_end = datetime.fromtimestamp(_job['end_timestamp'])

                    durations.append(
                        (dt_obj_end - dt_obj_start).total_seconds() / 60)
                    outcomes.append(_job)
                    dataset.append({
                        'push_id': _push['id'],
                        'task_id': _job['task_id'],
                        'duration': '{0:.0f}'.format(
                            (dt_obj_end - dt_obj_start).total_seconds() / 60
                        ),
                        'author': _job['who'],
                        'result': _job['result'],
                        'task_html_url': '{0}'.format(''.join(
                            [client.global_configuration['taskcluster']['host'], '/tasks/',
                                _job['task_id']]
                        )),
                        'last_modified': _job['last_modified'],
                        'task_log': _log,
                        'matrix_general_details': _matrix_general_details,
                        'matrix_outcome_details': _matrix_outcome_details,
                        'revision': _revSHA,
                        'pullreq_html_url': _github_details['html_url']
                        if _github_details else None,
                        'pullreq_html_title': _github_details['title']
                        if _github_details else None,
                        'problem_test_details': _test_details
                    })

                    logger.info(
                        'Duration: {0:.0f} min {1} - {2} - '
                        '{3}/tasks/{4} - {5} - {6} - [{7}] - '
                        '[{8}] - {9} - {10} - {11} - {12} - {13}'.format(
                            (dt_obj_end - dt_obj_start).total_seconds() / 60,
                            _job['who'],
                            _job['result'],
                            client.global_configuration['taskcluster']['host'],
                            _job['task_id'],
                            _job['last_modified'],
                            _log,
                            ', '.join(map(str, [x['details'] for x in
                                                _matrix_outcome_details]))
                            if _matrix_outcome_details else None,
                            ', '.join(map(str, [x['outcome'] for x in
                                                _matrix_outcome_details]))
                            if _matrix_outcome_details else None,
                            _matrix_general_details['webLink'],
                            _revSHA,
                            _test_details,
                            _github_details['html_url'] if _github_details else None,
                            _github_details['title'] if _github_details else None
                        )
                    )

            if durations and outcomes and dataset:

                tests = [problem['name'] for push in dataset for problem in push['problem_test_details']]

                results.append(
                    {
                        str(client.project_configuration[job].name): dataset,
                        'summary': {
                            'repo': args.project,
                            'job_symbol': client.project_configuration[job]['symbol'],
                            'job_result': client.project_configuration[job]['result'],
                            'job_duration_avg': round(mean(durations), 2),
                            'outcome_count': len(outcomes),
                            'duplicates':
                            json.dumps(set([x for x in tests if tests.count(x) > 1]), default=serialize_sets)
                        }
                    }
                )

                logger.info('Summary: [{}]'.format(client.project_configuration[job]['symbol']))
                logger.info('Duration average: {0:.0f} minutes'.format(results[-1]['summary']['job_duration_avg']))
                logger.info('Results: {0} \n'.format(results[-1]['summary']['outcome_count']))
                print('Output written to LOG file', end='\n\n')
        else:
            print('No results found with provided config.', end='\n\n')

        if results:
            try:
                with open('output.json', 'w') as outfile:
                    json.dump(results, outfile, indent=4)
                    print('Output written to [{}]'.format(
                        outfile.name), end='\n\n')
            except OSError as err:
                raise SystemExit(err)
