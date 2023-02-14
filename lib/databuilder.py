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
from datetime import datetime
from statistics import mean

from github import Github
from junitparser import Attr, Failure, JUnitXml, TestSuite
from taskcluster import Queue
from taskcluster.exceptions import TaskclusterRestFailure

from lib.treeherder import TreeherderHelper

logging.basicConfig(filename='output.log', filemode='w', level=logging.INFO)
logger = logging.getLogger(__name__)


def serialize_sets(obj):
    if isinstance(obj, set):
        return list(obj)

    return obj


def get_artifact(url, params=None):
    from urllib.parse import urlencode
    from urllib.request import urlopen

    if params is not None:
        url += "?" + urlencode(params)

    response = urlopen(url=url, context=ssl._create_unverified_context())

    match response.headers.get('Content-Type'):
        case 'application/json':
            return json.loads(gzip.decompress(response.read()))
        case 'application/xml':
            return JUnitXml.fromstring(gzip.decompress(response.read()))
        case _:
            SystemError('Unknown artifact type')


class _TestSuite(TestSuite):
    flakes = Attr()


class data_builder:

    def __init__(self):
        pass

    def build_complete_dataset(self, args):
        from collections import defaultdict
        from urllib.parse import urlparse

        client = TreeherderHelper(args.project)
        github = Github(os.environ.get('GITHUB_TOKEN'))
        pushes = client.get_pushes()
        queue = Queue({'rootUrl': client.global_configuration['taskcluster']['host']})
        results, disabled_tests = ([] for i in range(2))

        print(f"\nFetching [{len(client.project_configuration.sections())}] in [{args.project}] {client.project_configuration.sections()}", end='\n\n')

        for job in client.project_configuration.sections():
            durations, outcomes, dataset = ([] for i in range(3))

            print('Fetching result [{0}] in [{1}] [{2}] ({3} max pushes) from'
                  ' the past [{4}] day(s) ...'.format(
                      client.project_configuration[job]['result'],
                      client.project_configuration[job]['symbol'],
                      client.project_configuration[job]['project'],
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
                retries = defaultdict(int)
                for _job in jobs:
                    _matrix_outcome_details = None
                    _matrix_general_details = {}
                    _test_details = []
                    _pull_request = None

                    # Fetch the log URL for the current job
                    _log = client.get_client().get_job_log_url(
                        project=args.project,
                        job_id=_job['id']
                    )
                    _log = ' '.join([str(_log_url['url']) for _log_url in _log])

                    if _job['retry_id'] < retries[_job['task_id']]:
                        print(f"Skipping {_job['task_id']} run: {_job['retry_id']} because there is a newer run of it.")
                        continue

                    retries[_job['task_id']] = _job['retry_id']
                    # print(f"{_job['task_id']} run: {_job['retry_id']}")

                    # TaskCluster
                    try:
                        # Dependent on public artifact visibility
                        if (re.compile("^(ui-|legacy){1}.*")).search(
                            client.project_configuration[job]['symbol']
                        ):
                            # Matrix (i.e, matrix_ids.json) generated from Flank
                            matrix_artifact = get_artifact(
                                queue.artifact(
                                    _job['task_id'],
                                    _job['retry_id'],
                                    client.global_configuration['artifacts']['matrix']
                                )['url']
                            )

                            if matrix_artifact is not None:
                                for value in matrix_artifact.values():
                                    _matrix_general_details = {
                                        "webLink": value['webLink'],
                                        "gcsPath": value['gcsPath'],
                                        "matrixId": value['matrixId']
                                    }
                                    _matrix_outcome_details = value['axes']

                            # Disabled tests (if requested) [TODO: append to dataset or output to file]
                            if args.disabled_tests:
                                shard_artifact = get_artifact(
                                    queue.artifact(
                                        _job['task_id'],
                                        _job['retry_id'],
                                        client.global_configuration['artifacts']['shards']
                                    )['url']
                                )

                                if shard_artifact is not None:
                                    for value in shard_artifact.values():
                                        if (value['junit-ignored'] not in
                                                disabled_tests):
                                            disabled_tests.append(
                                                value['junit-ignored'])
                            else:
                                pass

                            # JUnitReport (i.e, FullJUnitReport.xml)
                            report_artifact = get_artifact(
                                queue.artifact(
                                    _job['task_id'],
                                    _job['retry_id'],
                                    client.global_configuration['artifacts']['report']
                                )['url']
                            )

                            # Extract the test details from the FullJUnitReport
                            if report_artifact is not None:
                                for suite in report_artifact:  # pylint: disable=not-an-iterable
                                    cur_suite = _TestSuite.fromelem(suite)
                                    if cur_suite.flakes == '1':
                                        for case in suite:
                                            # Should I check for flaky=true?
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

                    except TaskclusterRestFailure:
                        # Abort iteration on current job, continue to next job
                        print(f"Artifact(s) not available for {_job['task_id']}")
                        continue

                    # Github (pull request data)
                    repo = github.get_repo(
                        urlparse(queue.task(_job['task_id'])['payload']['env']['MOBILE_HEAD_REPOSITORY']).path.strip("/")
                    )
                    commit = repo.get_commit(
                        queue.task(_job['task_id'])['payload']['env']['MOBILE_HEAD_REV']
                    )
                    pulls = commit.get_pulls()

                    _pull_request = pulls[0] if pulls is not None and pulls.totalCount > 0 else None

                    # Stitch together dataset from TaskCluster and Github results
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
                        'revision': commit.sha,
                        'pullreq_html_url': _pull_request.html_url
                        if _pull_request else commit.commit.html_url,
                        'pullreq_html_title': _pull_request.title
                        if _pull_request else commit.commit.message,
                        'problem_test_details': _test_details
                    })

                    logger.info(
                        'Duration: {0:.0f} min {1} - {2} - '
                        '{3}/tasks/{4} - {5} - {6} - [{7}] - '
                        '[{8}] - {9} - {10} - {11} - {12} - {13} - {14}'.format(
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
                            _matrix_general_details['matrixId'],
                            commit.sha,
                            _test_details,
                            _pull_request.html_url if
                            _pull_request else commit.commit.html_url,
                            _pull_request.title if
                            _pull_request else commit.commit.message,
                        )
                    )

            if durations and outcomes and dataset:

                tests = [problem['name'] for push in dataset for problem in push['problem_test_details']]

                results.append(
                    {
                        str(client.project_configuration[job].name): dataset,
                        'summary': {
                            'repo': args.project,
                            'project': client.project_configuration[job]['project'],
                            'job_symbol': client.project_configuration[job]['symbol'],
                            'job_result': client.project_configuration[job]['result'],
                            'job_duration_avg': round(mean(durations), 2),
                            'outcome_count': len(outcomes),
                            'duplicates':
                            json.dumps(set([x for x in tests if tests.count(x) > 1]), default=serialize_sets)
                        }
                    }
                )

                logger.info('Summary: [%s]', client.project_configuration[job]['symbol'])
                logger.info('Project: %s', client.project_configuration[job]['project'])
                logger.info('Duration average: {0:.0f} minutes'.format(results[-1]['summary']['job_duration_avg']))
                logger.info('Results: %s \n', results[-1]['summary']['outcome_count'])
                print('Output written to LOG file', end='\n\n')
            else:
                print('No results found with provided project config.', end='\n\n')

        if results:
            try:
                with open('output.json', 'w', encoding='utf-8') as outfile:
                    json.dump(results, outfile, indent=4)
                    print(f'Output written to [{outfile.name}] \n')
            except OSError as err:
                raise SystemExit(err) from err
        else:
            print('No results found with provided project config.', end='\n\n')
