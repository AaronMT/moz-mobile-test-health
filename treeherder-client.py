#! /usr/bin/env python
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
import ssl
import sys
import urllib.error
import urllib.request as request
import xmltodict
from statistics import mean
from datetime import datetime
from thclient import TreeherderClient


logging.basicConfig(filename='output.log', filemode='w', level=logging.INFO)
logger = logging.getLogger(__name__)

config = configparser.ConfigParser()
ssl._create_default_https_context = ssl._create_unverified_context


def parse_args(cmdln_args):
    parser = argparse.ArgumentParser(
        description='Fetch job and push data from TreeHerder instance'
    )
    parser.add_argument(
        '--config',
        default='config.ini',
        help='Configuration',
        required=True
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

    try:
        c = THClient()
        p = c.client.get_pushes(
            project=config['project']['repo'],
            count=int(config['pushes']['count'])
        )
    except requests.exceptions.HTTPError as err:
        raise SystemExit(err)

    print("Fetching push data from TreeHerder..\n")
    print(
        "Feching recent {0} in {1} ({2} pushes)\n".format(
            config['job']['result'],
            config['job']['symbol'],
            config['pushes']['count']
        )
    )

    try:
        open('output.json', 'w')
    except OSError as err:
        raise SystemExit(err)

    durations = []
    outcomes = []
    dataset = []

    for _push in sorted(p, key=lambda push: push['id']):
        jobs = c.client.get_jobs(
            config['project']['repo'],
            push_id=_push['id'],
            tier=config['job']['tier'],
            job_type_symbol=config['job']['symbol'],
            result=config['job']['result'],
            job_group_symbol=config['job']['group_symbol']
        )
        for _job in jobs:
            _outcome_details = None
            _test_details = []
            revSHA = None

            _log = c.client.get_job_log_url(
                project=config['project']['repo'],
                job_id=_job['id']
            )

            '''TaskCluster'''
            try:
                if 'ui-test-x86' in config['job']['symbol']:
                    '''Matrix'''
                    with request.urlopen("{0}/{1}/0/public/results/{2}".format(
                            config['taskcluster']['artifacts'],
                            _job['task_id'],
                            config['artifacts']['matrix']
                        )
                    ) as resp:
                        source = resp.read()
                        data = json.loads(source)
                        for key, value in data.items():
                            _outcome_details = value['testAxises'][0]

                    '''JUnitReport'''
                    with request.urlopen("{0}/{1}/0/public/results/{2}".format(
                            config['taskcluster']['artifacts'],
                            _job['task_id'],
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
                                        child['testcase']['@name']
                                    )
                else:
                    pass

                with request.urlopen("{0}/api/queue/v1/task/{1}/".format(
                        config['taskcluster']['host'],
                        _job['task_id']
                    )
                ) as resp:
                    source = resp.read()
                    data = json.loads(source)
                    revSHA = data['payload']['env']['MOBILE_HEAD_REV']
            except urllib.error.URLError as err:
                raise SystemExit(err)

            dt_obj_start = datetime.fromtimestamp(_job['start_timestamp'])
            dt_obj_end = datetime.fromtimestamp(_job['end_timestamp'])

            durations.append((dt_obj_end - dt_obj_start).total_seconds() / 60)
            outcomes.append(_job)

            '''Github'''
            try:
                with request.urlopen(
                    request.Request(
                        url="{0}{1}/commits/{2}/pulls".format(
                            config['project']['url'],
                            config['project']['repo'],
                            revSHA
                        ),
                        headers={
                            'Accept': 'application/vnd.github.groot-preview+json',
                            'Authorization': 'token %s' % os.environ['GITHUB_TOKEN']
                        }
                    )
                ) as resp:
                    source = resp.read()
                    data = json.loads(source)
            except urllib.error.URLError as err:
                raise SystemExit(err)

            dataset.append({
                'push_id': _push['id'],
                'task_id': _job['task_id'],
                'duration': "{0:.0f}".format((dt_obj_end - dt_obj_start).total_seconds() / 60),
                'author': _job['who'],
                'result': _job['result'],
                'task_html_url': config['taskcluster']['host'] + "/tasks/" + _job['task_id'],
                'last_modified': _job['last_modified'],
                'task_log': _log[0]['url'],
                'outcome_details': _outcome_details,
                'revision': revSHA,
                'pullreq_html_url': data[0]['html_url'],
                'pullreq_html_title': data[0]['title'],
                'test_details': _test_details
            })

            logger.info(
                "Duration: {0:.0f} min {1} - {2} - "
                "{3}/tasks/{4} - {5} - {6} - {7} - {8} - {9} - {10} - {11} - {12}\n".format(
                    (dt_obj_end - dt_obj_start).total_seconds() / 60,
                    _job['who'],
                    _job['result'],
                    config['taskcluster']['host'],
                    _job['task_id'],
                    _job['last_modified'],
                    _log[0]['url'],
                    _outcome_details['details'],
                    _outcome_details['outcome'],
                    revSHA,
                    _test_details,
                    data[0]['html_url'],
                    data[0]['title']
                )
            )

    if durations and outcomes and dataset:

        summary_set = {
            'datasetResults': dataset,
            'jobSymbol': config['job']['symbol'],
            'jobResult': config['job']['result'],
            'averageJobDuration': round(mean(durations), 2),
            'outcomeCount': len(outcomes),
        }
        logger.info("Summary")
        logger.info("Duration average: {0:.0f} minutes".format(summary_set["averageJobDuration"]))
        logger.info("Results: {0} ".format(summary_set['outcomeCount']))
        print("Output written to LOG file", end='\n')

        try: 
            with open('output.json', 'w') as outfile:
                json.dump(summary_set, outfile, indent=4)
                print("Output written to JSON file", end='\n')
        except OSError as err:
            raise SystemExit(err)
    else:
        print("No results found with provided config.")


if __name__ == "__main__":
    main()
