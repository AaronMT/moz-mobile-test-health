#! /usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import argparse
import json
import os
import requests
import sys
from datetime import datetime


def parse_args(cmdln_args):
    parser = argparse.ArgumentParser(
        description='Performs post operations on dataset'
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

    try:
        with open(args.input) as data_file:
            data = json.load(data_file)
            for dataset in data['dataset_results']:
                for problem in dataset['problem_test_details']:
                    payload = {
                        "blocks": [
                            {
                                "type": "header",
                                "text": {
                                    "type": "plain_text",
                                    "text": "Recent {} problems in {} {}"
                                    .format(
                                        data['job_symbol'],
                                        data['repo'],
                                        ':firefox-browser:'
                                        if data['repo'] == 'fenix'
                                        else ':refbrowser:'
                                        if data['repo'] == 'reference-browser'
                                        else ':android:'
                                    ),
                                }
                            },
                            {
                                "type": "context",
                                "elements": [
                                    {
                                        "type": "plain_text",
                                        "text": "Author: {}\nPull Request: {}"
                                        .format(
                                            dataset['author'], 
                                            dataset['pullreq_html_title']
                                        ),
                                    }
                                ]
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
                                        "text": "*Reason:*\n{} {}".format(
                                            problem['result'], ":x:"
                                            if problem['result'] == "failure"
                                            else ":warning:"
                                        )
                                    },
                                    {
                                        "type": "mrkdwn",
                                        "text": "*Date:*\n{}".format(
                                            datetime.fromisoformat(
                                                dataset['last_modified']
                                            ).date()
                                        )
                                    },
                                    {
                                        "type": "mrkdwn",
                                        "text": "*URL:*\n<{}|Firebase>".format(
                                            dataset['matrix_general_details']
                                            ['webLink']
                                        )
                                    },
                                ]
                            },
                            {
                                "type": "actions",
                                "elements": [
                                    {
                                        "type": "button",
                                        "text": {
                                            "type": "plain_text",
                                            "text": "View Task"
                                        },
                                        "value": "push_button_1",
                                        "action_id": "button-action-1",
                                        "url": dataset['task_html_url']
                                    },
                                    {
                                        "type": "button",
                                        "text": {
                                            "type": "plain_text",
                                            "text": "View Pull Request"
                                        },
                                        "value": "push_button_2",
                                        "action_id": "button-action-2",
                                        "url": dataset['pullreq_html_url']
                                    },
                                    {
                                        "type": "button",
                                        "text": {
                                            "type": "plain_text",
                                            "text": "View Task Log"
                                        },
                                        "value": "push_button_3",
                                        "action_id": "button-action-3",
                                        "url": dataset['task_log']
                                    }
                                ]
                            },
                            {
                                "type": "divider"
                            }
                        ]
                    }

                    post_to_slack(payload)

    except OSError as err:
        print(err)
        sys.exit(1)


if __name__ == '__main__':
    main()
