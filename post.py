#! /usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

'''
Sends a message to Slack with a formatted list of intermittents
and failures from a JSON file generated by `treeherder-client.py`
'''

import argparse
import json
import os
import sys

import requests


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
            dataset = json.load(data_file)

            for section in dataset:
                content, header, footer = ([] for i in range(3))
                divider = [{"type": "divider"}]
                footer = [
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": ":testops-notify: created by [<{}|{}>]"
                                .format(
                                    "https://mana.mozilla.org/wiki/x/P_zNBw",
                                    "Mobile Test Engineering")
                            }
                        ]
                    }
                ]
                header = [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": "Daily UI Test Jobs {}\n"
                                    "{}: {} (result: {}) with {}"
                            .format(
                                ':firefox-browser:' if section['summary']
                                ['repo'] == 'fenix'
                                else ':refbrowser:'
                                if section['summary']['repo']
                                == 'reference-browser'
                                else ':focusandroid:' if section['summary']
                                ['repo'] == 'focus-android'
                                else ':android:',
                                section['summary']['repo'],
                                section['summary']['job_symbol'],
                                ":x:" if section['summary']['job_result'] ==
                                "testfailed" else ":white_check_mark:",
                                "flaky and or failed tests" if
                                section['summary']['job_result']
                                == "testfailed" else "flaky tests"
                            )
                        }
                    }
                ]

                job = (next(iter(section.values())))
                for problem in job:
                    if problem['problem_test_details']:
                        for test in problem['problem_test_details']:
                            content.append([
                                test['name'],
                                {
                                    "type": "section",
                                    "text": {
                                        "type": "mrkdwn",
                                        "text":
                                        "*{}* [#<{}|{}>] [<{}|task log>]"
                                        .format(
                                            test['name'],
                                            problem['pullreq_html_url'],
                                            problem['pullreq_html_url']
                                            .rsplit('/', 1)[-1],
                                            problem['task_log']
                                        )
                                    },
                                    "accessory": {
                                        "type": "button",
                                        "text": {
                                            "type": "plain_text",
                                            "text": "{} {}".format(
                                                test
                                                ['result'], ":x:"
                                                if test['result']
                                                == "failure"
                                                else ":warning:"
                                            )
                                        },
                                        "value": "firebase",
                                        "url":
                                        problem['matrix_general_details']
                                        ['webLink'],
                                        "action_id": "button-action"
                                    }
                                }
                            ])
                if content:
                    content = sorted(content, key=lambda x: x[0])
                    [x.__delitem__(0) for x in content]
                    content = [item for sublist in content for item in sublist]

                    post_to_slack(
                        {'blocks': header + divider + content + divider +
                         footer})
                    print("Slack message posted for [{}] results".format(
                        ''.join(
                            [section['summary']['job_symbol'], '.',
                             section['summary']['job_result']])), end="\n")

                else:
                    print("No failures or intermittents in ({}) in [{}]. "
                          "No Slack message posted.".
                          format(
                            next(iter(section)),
                            section['summary']['job_symbol']
                          ), end='\n')
    except OSError as e:
        print(e)
        sys.exit(1)


if __name__ == '__main__':
    main()
