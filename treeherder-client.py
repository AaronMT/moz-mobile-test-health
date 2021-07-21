#! /usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

'''
Small TreeherderClient for fetching push and
job metadata from provided configuration and
building a sharable dataset:

Uses:
  - TreeHerder
  - TaskCluster
  - Github
'''

import argparse
import configparser
import json
import logging
import os
import requests
import re
import ssl
import sys
import urllib.error
import urllib.request as request
import xmltodict
from statistics import mean
from datetime import date, datetime, timedelta
from thclient import TreeherderClient


logging.basicConfig(filename='output.log', filemode='w', level=logging.INFO)
logger = logging.getLogger(__name__)

config = configparser.ConfigParser()
project_config = configparser.ConfigParser()

ssl._create_default_https_context = ssl._create_unverified_context


def parse_args(cmdln_args):
    parser = argparse.ArgumentParser(
        description='Fetch job and push data from TreeHerder instance'
    )
    parser.add_argument(
        '--project',
        required=True,
        help='Project configuration'
    )
    parser.add_argument(
        '--config',
        default='config.ini',
        help='Configuration',
        required=False
    )

    return parser.parse_args(args=cmdln_args)


class THClient:
    def __init__(self):
        self.set_config()

    def set_config(self):
        self.client = TreeherderClient(server_url=config['production']['host'])


def main():
    args = parse_args(sys.argv[1:])
    config.read(args.config)

    if os.path.isfile(args.project + '.ini'):
        project_config.read(args.project + '.ini')
    else:
        print('Project configuration not found')
        sys.exit(1)

    try:
        c = THClient()
        p = c.client.get_pushes(
            project=args.project,
            count=int(config['pushes']['maxcount']),
            enddate=date.today().isoformat(),
            startdate=date.today() - timedelta(
                days=int(config['pushes']['days'])
            )
        )
    except requests.exceptions.HTTPError as err:
        raise SystemExit(err)

    durations = []
    outcomes = []
    dataset = []

    for job in project_config.sections():     
        print('Fetched Push data from TreeHerder..')
        print('Fetching recent {0} in {1} ({2} pushes)\n'.format(
            project_config[job]['result'],
            project_config[job]['symbol'],
            config['pushes']['maxcount']
           )
        )

        for _push in sorted(p, key=lambda push: push['id']):
            jobs = c.client.get_jobs(
                project=args.project,
                push_id=_push['id'],
                tier=project_config[job]['tier'],
                job_type_symbol=project_config[job]['symbol'],
                result=project_config[job]['result'],
                job_group_symbol=project_config[job]['group_symbol'],
                who=config['filters']['author']
            )

            for _job in jobs:
                _matrix_outcome_details = None
                _test_details = []
                _revSHA = None

                _log = c.client.get_job_log_url(
                    project=args.project,
                    job_id=_job['id']
                )
                for _log_url in _log:
                    _log = _log_url['url']

                # TaskCluster
                try:
                    # Dependent on public artifact visibility
                    if (re.compile("^(ui-){1}.*")).search(
                        project_config[job]['symbol']
                    ):
                        # Matrix
                        with request.urlopen(
                            '{0}/{1}/{2}/public/results/{3}'.format(
                                config['taskcluster']['artifacts'],
                                _job['task_id'],
                                _job['retry_id'],
                                config['artifacts']['matrix']
                            )
                        ) as resp:
                            source = resp.read()
                            data = json.loads(source)
                            for key, value in data.items():
                                _matrix_general_details = {
                                    "webLink": value[
                                        'webLinkWithoutExecutionDetails'
                                    ]
                                }
                                _matrix_outcome_details = value['axes'][0]

                        # JUnitReport
                        with request.urlopen(
                            '{0}/{1}/{2}/public/results/{3}'.format(
                                config['taskcluster']['artifacts'],
                                _job['task_id'],
                                _job['retry_id'],
                                config['artifacts']['report']
                            )
                        ) as resp:
                            source = resp.read()
                            data = xmltodict.parse(source)
                            root = data['testsuites']
                            for child in root['testsuite']:
                                if child['@name'] != 'junit-ignored':
                                    if child['@failures'] == '1':
                                        _test_details.append(
                                            {
                                                'name': child['testcase']
                                                ['@name'],
                                                'result': 'failure'
                                            }
                                        )
                                    elif child['@flakes'] == '1':
                                        _test_details.append(
                                            {
                                                'name': child['testcase']
                                                ['@name'],
                                                'result': 'flaky'
                                            }
                                        )
                                    else:
                                        pass
                    else:
                        pass

                    # TaskCluster: payload mobile revision
                    with request.urlopen('{0}/api/queue/v1/task/{1}/'.format(
                            config['taskcluster']['host'],
                            _job['task_id']
                        )
                    ) as resp:
                        source = resp.read()
                        data = json.loads(source)
                        _revSHA = data['payload']['env']['MOBILE_HEAD_REV']
                except urllib.error.URLError as err:
                    raise SystemExit(err)

                # Github
                try:
                    with request.urlopen(
                        request.Request(
                            url='{0}{1}/commits/{2}/pulls'.format(
                                config['project']['url'],
                                args.project,
                                _revSHA
                            ),
                            headers={
                                'Accept':
                                'application/vnd.github.groot-preview+json',
                                'Authorization':
                                'token %s' % os.environ['GITHUB_TOKEN']
                            }
                        )
                    ) as resp:
                        source = resp.read()
                        _github_data = json.loads(source)
                        for _data in _github_data:
                            _github_data = _data

                except urllib.error.URLError as err:
                    raise SystemExit(err)

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
                    'task_html_url': '{0}'.format(
                        config['taskcluster']['host']
                        + '/tasks/' + _job['task_id']
                    ),
                    'last_modified': _job['last_modified'],
                    'task_log': _log,
                    'matrix_general_details': _matrix_general_details,
                    'matrix_outcome_details': _matrix_outcome_details,
                    'revision': _revSHA,
                    'pullreq_html_url': _github_data['html_url']
                    if _github_data else None,
                    'pullreq_html_title': _github_data['title']
                    if _github_data else None,
                    'problem_test_details': _test_details
                })

                logger.info(
                    'Duration: {0:.0f} min {1} - {2} - '
                    '{3}/tasks/{4} - {5} - {6} - {7} - '
                    '{8} - {9} - {10} - {11} - {12} - {13}\n'.format(
                        (dt_obj_end - dt_obj_start).total_seconds() / 60,
                        _job['who'],
                        _job['result'],
                        config['taskcluster']['host'],
                        _job['task_id'],
                        _job['last_modified'],
                        _log,
                        _matrix_outcome_details['details']
                        if _matrix_outcome_details else None,
                        _matrix_outcome_details['outcome']
                        if _matrix_outcome_details else None,
                        _matrix_general_details['webLink'],
                        _revSHA,
                        _test_details,
                        _github_data['html_url'] if _github_data else None,
                        _github_data['title'] if _github_data else None
                    )
                )

        if durations and outcomes and dataset:

            summary_set = {
                'dataset_results': dataset,
                'repo': args.project,
                'job_symbol': project_config[job]['symbol'],
                'job_result': project_config[job]['result'],
                'job_duration_avg': round(mean(durations), 2),
                'outcome_count': len(outcomes)
            }
            logger.info('Summary')
            logger.info('Duration average: {0:.0f} minutes'.format(
                    summary_set['job_duration_avg']
                )
            )
            logger.info('Results: {0} '.format(summary_set['outcome_count']))
            print('Output written to LOG file', end='\n')

            try:
                with open('output.json', 'w') as outfile:
                    json.dump(summary_set, outfile, indent=4)
                    print('Output written to JSON file\n', end='\n')
            except OSError as err:
                raise SystemExit(err)
        else:
            print('No results found with provided config.')


if __name__ == '__main__':
    main()
