#! /usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import argparse
import configparser
import json
import os
import requests
import sys


config = configparser.ConfigParser()


def parse_args(cmdln_args):
    parser = argparse.ArgumentParser(
        description='Performs post operations on dataset'
    )
    parser.add_argument(
        '--config',
        default='config.ini',
        help='Configuration',
        required=True
    )
    parser.add_argument(
        '--input',
        default='output.json',
        help='Input (JSON)',
        required=True
    )

    return parser.parse_args(args=cmdln_args)


def post_to_slack(data):
    webhook_url = os.environ['SLACK_WEBHOOK']
    requests.post(webhook_url, json=data)


def main():
    args = parse_args(sys.argv[1:])
    config.read(args.config)

    try:
        with open(args.input) as data_file:
            data = json.load(data_file)
            for dataset in data['dataset_results']:
                for problem in dataset['problem_test_details']:
                    payload = {
                        "blocks": [
                            {
                                "type": "section",
                                "text": {
                                    "type": "mrkdwn",
                                    "text": "*Project*\n{}".format(
                                        config['project']['repo']
                                    )
                                }
                            },
                            {
                                "type": "section",
                                "fields": [
                                    {
                                        "type": "mrkdwn",
                                        "text": "*Test:*\n{}".format(
                                            problem['name']
                                        )
                                    },
                                    {
                                        "type": "mrkdwn",
                                        "text": "*Reason:*\n{}".format(
                                            problem['result']
                                        )
                                    },
                                    {
                                        "type": "mrkdwn",
                                        "text": "*Date:*\n{}".format(
                                            dataset['last_modified']
                                        )
                                    },
                                    {
                                        "type": "mrkdwn",
                                        "text": "*URL:*\n{}".format(
                                            dataset['matrix_general_details']
                                            ['webLink']
                                        )
                                    }
                                ]
                            }
                        ]
                    }

                    post_to_slack(payload)

    except OSError as err:
        print(err)
        sys.exit(1)


if __name__ == '__main__':
    main()
