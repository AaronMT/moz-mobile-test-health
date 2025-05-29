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
from junitparser import (Attr, Failure, JUnitXml, JUnitXmlError, TestCase,
                         TestSuite, Skipped)
from taskcluster import Queue
from taskcluster.exceptions import TaskclusterRestFailure

from lib.treeherder import TreeherderHelper

logging.basicConfig(filename='output.log', filemode='w', level=logging.INFO)
logger = logging.getLogger(__name__)


def serialize_sets(obj):
    '''Serialize sets to lists.'''
    if isinstance(obj, set):
        return list(obj)

    return obj


def get_artifact(url, params=None):
    '''Fetch artifact from Taskcluster.'''
    from urllib.error import HTTPError, URLError
    from urllib.parse import urlencode
    from urllib.request import Request, urlopen

    if params is not None:
        url += "?" + urlencode(params)

    try:
        request = Request(url=url, headers={'Accept-Encoding': 'gzip'})
        response = urlopen(request, context=ssl._create_unverified_context())
    except HTTPError as e:
        return f'HTTPError: {e.code}'
    except URLError as e:
        return f'URLError: {e.reason}'

    try:
        if response.headers.get('Content-Type') == 'application/json':
            return json.loads(gzip.decompress(response.read()))
        elif response.headers.get('Content-Type') == 'application/xml':
            return JUnitXml.fromstring(gzip.decompress(response.read()))
        else:
            return SystemError('Unknown artifact type')
    except OSError:
        return 'Error decompressing data'
    except json.JSONDecodeError:
        return 'Error decoding JSON data'
    except JUnitXmlError:
        return 'Error parsing XML data'


class _TestSuite(TestSuite):
    '''Extend TestSuite class to add flakes attribute.'''
    flakes = Attr()


class _TestCase(TestCase):
    '''Extend Testcase class to add flaky attribute.'''
    flaky = Attr()


class data_builder:
    '''Build the dataset.'''
    def __init__(self):
        self.github = Github(os.environ['GITHUB_TOKEN']) \
            if 'GITHUB_TOKEN' in os.environ else exit("GITHUB_TOKEN environment variable is not set")

    def fetch_pushes(self, client):
        """Fetch pushes from Treeherder API."""
        return client.get_pushes()

    def fetch_jobs(self, client, args, push, job):
        """Fetch jobs from Treeherder API."""
        return client.get_client().get_jobs(
            project=args.project,
            push_id=push['id'],
            tier=client.project_configuration[job]['tier'],
            job_type_symbol=client.project_configuration[job]['symbol'],
            result=client.project_configuration[job]['result'],
            job_group_symbol=client.project_configuration[job]['group_symbol'],
            who=client.global_configuration['filters']['author']
        )

    def fetch_github(self, current_job, queue):
        """Fetch Github data."""
        from urllib.parse import urlparse

        try:
            task_payload = queue.task(current_job['task_id'])['payload']
            repo = self.github.get_repo(
                urlparse(task_payload['env']['MOBILE_HEAD_REPOSITORY']).path.strip("/")
            )
            commit = repo.get_commit(task_payload['env']['MOBILE_HEAD_REV'])
            pulls = commit.get_pulls()
            pull_request = pulls[0] if pulls is not None and pulls.totalCount > 0 else None
        except KeyError:
            logger.error(f"Error fetching Github data for {current_job['task_id']}")
            pull_request, commit = None, None

        return pull_request, commit

    def fetch_hg(self, current_job, queue):
        """Fetch Mercurial data."""
        from urllib.parse import urlparse

        try:
            task_payload = queue.task(current_job['task_id'])['payload']
            repo = urlparse(task_payload['env']['GECKO_HEAD_REPOSITORY'])
            commit = task_payload['env']['GECKO_HEAD_REV']
        except KeyError:
            logger.error(f"Error fetching Mercurial data for {current_job['task_id']}: Key not found.")
            repo, commit = None, None
        except TypeError:
            logger.error(f"Error fetching Mercurial data for {current_job['task_id']}: Unexpected data type.")
            repo, commit = None, None
        except AttributeError:
            logger.error(f"Error fetching Mercurial data for {current_job['task_id']}: Missing attribute.")
            repo, commit = None, None
        except ValueError:
            logger.error(f"Error fetching Mercurial data for {current_job['task_id']}: Invalid task ID.")
            repo, commit = None, None

        return repo, commit

    def fetch_phabricator(self, current_job, queue):
        """Fetch Phabricator data."""
        pass

    def fetch_comments_for_revision(self, current_push, commit):
        """Fetch comments for a matching revision."""
        for revision in current_push['revisions']:
            if revision['revision'] == commit:
                return revision['comments']

    def construct_pushlog(self, client, project, commit):
        return f"{client.global_configuration['treeherder']['host']}/jobs?repo={project}&revision={getattr(commit, 'sha', commit) if commit else commit}"

    def build_complete_dataset(self, args):
        """Build the complete dataset."""
        from collections import defaultdict

        client = TreeherderHelper(args.project)
        pushes = self.fetch_pushes(client)
        queue = Queue({'rootUrl': client.global_configuration['taskcluster']['host']})

        results = []
        disabled_tests = set()

        print(f"\nFetching [{len(client.project_configuration.sections())}] in [{args.project}] {client.project_configuration.sections()}", end='\n\n')

        for job in client.project_configuration.sections():

            durations, outcomes, dataset = [], [], []

            print(f"Fetching result [{client.project_configuration[job]['result']}] in "
                  f"[{client.project_configuration[job]['symbol']}] "
                  f"[{client.project_configuration[job]['project']}] "
                  f"({client.global_configuration['pushes']['maxcount']} max pushes) "
                  f"from the past [{client.global_configuration['pushes']['days']}] day(s) ...",
                  end='\n')

            for current_push in sorted(pushes, key=lambda push: push['id']):

                jobs = self.fetch_jobs(client, args, current_push, job)
                retries = defaultdict(int)

                for current_job in jobs:

                    matrix_outcome_details, pull_request = None, None
                    matrix_general_details = {}
                    test_details = []

                    # Fetch the log URL for the current job
                    current_job_log = ' '.join([str(_log_url['url']) for _log_url in client.get_client().get_job_log_url(
                        project=args.project,
                        job_id=current_job['id']
                    )])

                    if current_job['retry_id'] < retries[current_job['task_id']]:
                        print(f"Skipping {current_job['task_id']} run: {current_job['retry_id']} because there is a newer run of it.")
                        continue

                    retries[current_job['task_id']] = current_job['retry_id']
                    # print(f"{current_job['task_id']} run: {current_job['retry_id']}")

                    # TaskCluster
                    try:
                        # Dependent on public artifact visibility
                        if (re.compile("^(ui-|robo|legacy|experimental|smoke){1}.*")).search(
                            client.project_configuration[job]['symbol']
                        ):
                            # Matrix (i.e, matrix_ids.json) generated from Flank
                            matrix_artifact = get_artifact(
                                queue.artifact(
                                    current_job['task_id'],
                                    current_job['retry_id'],
                                    client.global_configuration['artifacts']['matrix']
                                )['url']
                            )

                            if matrix_artifact is not None:
                                for value in matrix_artifact.values():
                                    matrix_general_details = {
                                        "webLink": value['webLink'],
                                        "gcsPath": value['gcsPath'],
                                        "matrixId": value['matrixId'],
                                        "isRoboTest": value['isRoboTest'],
                                    }
                                    matrix_outcome_details = value['axes']

                            # Disabled tests (if requested) [TODO: append to dataset or output to file]
                            if args.disabled_tests:
                                shard_artifact = get_artifact(
                                    queue.artifact(
                                        current_job['task_id'],
                                        current_job['retry_id'],
                                        client.global_configuration['artifacts']['shards']
                                    )['url']
                                )

                                if shard_artifact is not None:
                                    for value in shard_artifact.values():
                                        disabled_tests.update(value['junit-ignored'])
                            else:
                                pass

                            # JUnitReport (i.e, FullJUnitReport.xml)
                            report_artifact = get_artifact(
                                queue.artifact(
                                    current_job['task_id'],
                                    current_job['retry_id'],
                                    client.global_configuration['artifacts']['report']
                                )['url']
                            )

                            # Extract the test details from the FullJUnitReport
                            if report_artifact is not None:
                                # Dictionary to store the last seen failure details for each test case
                                last_seen_failures = {}

                                for suite in report_artifact:  # pylint: disable=not-an-iterable
                                    cur_suite = _TestSuite.fromelem(suite)
                                    for case in cur_suite:
                                        case = _TestCase.fromelem(case)
                                        
                                        result_type = None
                                        
                                        if case.result:
                                            for entry in case.result:
                                                if isinstance(entry, Skipped):
                                                    continue  # ignore skipped tests
                                                if isinstance(entry, Failure):
                                                    result_type = (
                                                        "flaky"
                                                        if getattr(case, "flaky", "false") == "true"
                                                        else "failure"
                                                    )
                                                    test_id = "%s#%s" % (case.classname, case.name)
                                                    if entry.text != last_seen_failures.get(test_id, ""):
                                                        test_details.append(
                                                            {
                                                                "name": case.name,
                                                                "result": result_type,
                                                                "details": entry.text,
                                                            }
                                                        )
                                                    last_seen_failures[test_id] = entry.text

                                # For Robo Tests, as of now, there are no artifacts exposing details
                                # about the outcome (e.g, crash details), so we have to write a custom outcome
                                if matrix_general_details['isRoboTest'] is True:
                                    if matrix_outcome_details is not None:
                                        for axis in matrix_outcome_details:
                                            if axis['outcome'] == 'failure':
                                                test_details.append({
                                                    'name': axis['device'],
                                                    'result': 'failure',
                                                    'details': axis['details']
                                                })
                        else:
                            pass

                    except TaskclusterRestFailure:
                        # Abort iteration on current job, continue to next job
                        print(f"Artifact(s) not available for {current_job['task_id']}")
                        continue

                    # Fetch Github or Mercurial associative data from the TaskCluster task
                    # Mercurial (i.e, commit details)
                    hg_projects = [project.strip() for project in client.global_configuration['hg']['projects'].split(',')]

                    if args.project in hg_projects:
                        repo, commit = self.fetch_hg(current_job, queue)
                    else:
                        # Github (i.e, pull request details)
                        pull_request, commit = self.fetch_github(current_job, queue)

                    # Stitch together dataset from TaskCluster and Github results
                    dt_obj_start = datetime.fromtimestamp(current_job['start_timestamp'])
                    dt_obj_end = datetime.fromtimestamp(current_job['end_timestamp'])

                    durations.append(
                        (dt_obj_end - dt_obj_start).total_seconds() / 60)
                    outcomes.append(current_job)
                    dataset.append({
                        'push_id': current_push['id'],
                        'task_id': current_job['task_id'],
                        'duration': '{0:.0f}'.format(
                            (dt_obj_end - dt_obj_start).total_seconds() / 60
                        ),
                        'author': current_job['who'],
                        'result': current_job['result'],
                        'task_html_url': '{0}'.format(''.join(
                            [client.global_configuration['taskcluster']['host'], '/tasks/',
                                current_job['task_id']]
                        )),
                        'last_modified': current_job['last_modified'],
                        'task_log': current_job_log,
                        'matrix_general_details': matrix_general_details,
                        'matrix_outcome_details': matrix_outcome_details,
                        'revision': getattr(commit, 'sha', commit) if commit else None,
                        'pullreq_html_url': pull_request.html_url if pull_request else getattr(commit, 'html_url', None) if hasattr(commit, 'commit') else f"{repo.scheme}://{repo.netloc}/{repo.path}/rev/{commit}" if repo else None,
                        'pullreq_html_title': pull_request.title if pull_request else getattr(getattr(commit, 'commit', None), 'message', self.fetch_comments_for_revision(current_push, commit)) if commit else None,
                        'problem_test_details': test_details,
                        'pushlog': self.construct_pushlog(client, args.project, commit)
                    })

                    logger.info(
                        'Duration: {0:.0f} min {1} - {2} - '
                        '{3}/tasks/{4} - {5} - {6} - [{7}] - '
                        '[{8}] - {9} - {10} - {11} - {12} - {13} - {14} - {15}'.format(
                            (dt_obj_end - dt_obj_start).total_seconds() / 60,
                            current_job['who'],
                            current_job['result'],
                            client.global_configuration['taskcluster']['host'],
                            current_job['task_id'],
                            current_job['last_modified'],
                            current_job_log,
                            ', '.join(map(str, [x['details'] for x in
                                                matrix_outcome_details]))
                            if matrix_outcome_details else None,
                            ', '.join(map(str, [x['outcome'] for x in
                                                matrix_outcome_details]))
                            if matrix_outcome_details else None,
                            matrix_general_details['webLink'],
                            matrix_general_details['matrixId'],
                            getattr(commit, 'sha', commit) if commit else None,
                            test_details,
                            pull_request.html_url if pull_request else getattr(commit, 'html_url', None) if hasattr(commit, 'commit') else f"{repo.scheme}://{repo.netloc}/{repo.path}/rev/{commit}" if repo else None,
                            pull_request.title if pull_request else getattr(getattr(commit, 'commit', None), 'message', self.fetch_comments_for_revision(current_push, commit)) if commit else None,
                            self.construct_pushlog(client, args.project, getattr(commit, 'sha', commit) if commit else None)
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
                raise SystemExit(f"Error: Failed to write output to file. {err}") from err
        else:
            print('No results found with provided project config.', end='\n\n')
