#! /usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import argparse
import json
import os
import requests
import sys


def parse_args(cmdln_args):
    parser = argparse.ArgumentParser(
        description='Performs post operations on dataset'
    )

    parser.add_argument(
        '--input',
        default='output.json',
        help='Input (JSON)',
        required=False
    )

    return parser.parse_args(args=cmdln_args)


def post_to_slack(data):
    webhook_url = os.environ['SLACK_WEBHOOK']
    requests.post(webhook_url, json=data)


def main():
    args = parse_args(sys.argv[1:])

    try:
        with open(args.input) as data_file:
            data = json.load(data_file)
            content = []
            header = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "{}: daily {} failures/intermittents {}"
                        .format(
                            data['repo'],
                            data['job_symbol'],
                            ':firefox-browser:' if data['repo'] == 'fenix'
                            else ':refbrowser:'
                            if data['repo'] == 'reference-browser'
                            else ':android:'
                        )
                    }
                }
            ]

            for dataset in data['dataset_results']:
                for problem in dataset['problem_test_details']:
                    content.append(
                            [
                                problem['name'],

                                {
                                    "type": "section",
                                    "text": {
                                        "type": "mrkdwn",
                                        "text":
                                        "*{}* (#<{}|{}>) (<{}|task log>)"
                                        .format(
                                            problem['name'],
                                            dataset['pullreq_html_url'],
                                            dataset['pullreq_html_url']
                                            .rsplit('/', 1)[-1],
                                            dataset['task_log']
                                        )
                                    },
                                    "accessory": {
                                        "type": "button",
                                        "text": {
                                            "type": "plain_text",
                                            "text": "{} {}".format(
                                                problem['result'], ":x:"
                                                if problem['result']
                                                == "failure"
                                                else ":warning:"
                                            )
                                        },
                                        "value": "firebase",
                                        "url":
                                        dataset['matrix_general_details']
                                        ['webLink'],
                                        "action_id": "button-action"
                                    }
                                }
                            ]
                    )

            if content:
                content = sorted(content, key=lambda x: x[0])
                [x.__delitem__(0) for x in content]
                content = [item for sublist in content for item in sublist]
                post_to_slack({'blocks': header + content})
            else:
                print("No problems in {}. Nothing posted to Slack".format(
                        args.input
                    )
                )

    except OSError as err:
        print(err)
        sys.exit(1)


if __name__ == '__main__':
    main()
