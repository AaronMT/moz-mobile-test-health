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

from lib.treeherder import TreeherderHelper

ssl._create_default_https_context = ssl._create_unverified_context

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

    r = urlopen(url)

    match r.headers.get('Content-Type'):
        case 'application/json':
            return json.loads(gzip.decompress(r.read()))
        case 'application/xml':
            return JUnitXml.fromstring(gzip.decompress(r.read()))
        case _:
            SystemError('Unknown artifact type')


class _TestSuite(TestSuite):
    flakes = Attr()


class databuilder:

    def __init__(self):
        pass

    def build_complete_dataset(self, args):
        from urllib.parse import urlparse

        client = TreeherderHelper(args.project)
        github = Github(os.environ.get('GITHUB_TOKEN'))
        pushes = client.get_pushes()
        queue = Queue({'rootUrl': client.global_configuration['taskcluster']['host']})
        results, disabled_tests = ([] for i in range(2))

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
                    _matrix_general_details = {}
                    _test_details = []
                    _github_details = None

                    # Fetch the log URL for the current job
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
                            matrix_artifact = get_artifact(
                                queue.artifact(
                                    _job['task_id'],
                                    _job['retry_id'],
                                    client.global_configuration['artifacts']['matrix']
                                )['url']
                            )

                            if matrix_artifact is not None:
                                for key, value in matrix_artifact.items():
                                    _matrix_general_details = {
                                        "webLink": value['webLink'],
                                        "gcsPath": value['gcsPath']
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
                                    for key, value in shard_artifact.items():
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
                                for suite in report_artifact:
                                    cur_suite = _TestSuite.fromelem(suite)
                                    if cur_suite.flakes == '1':
                                        for case in suite:
                                            # TODO: Should I check for flaky=true?
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

                    except Exception as err:
                        print(f"Artifact(s) not available for {_job['task_id']}")
                        raise SystemExit(err)

                    # Github (pull request data)
                    repo = github.get_repo(
                        urlparse(queue.task(_job['task_id'])['payload']['env']['MOBILE_HEAD_REPOSITORY']).path.strip("/")
                    )
                    commit = repo.get_commit(queue.task(_job['task_id'])['payload']['env']['MOBILE_HEAD_REV'])

                    for pull in commit.get_pulls():
                        _github_details = {'html_url': pull.html_url, 'title': pull.title}

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
                            commit.sha,
                            _test_details,
                            _github_details['html_url'] if
                            _github_details else None,
                            _github_details['title'] if
                            _github_details else None
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
