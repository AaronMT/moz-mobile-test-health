#! /usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

'''
Sends a message to Slack with a formatted list of intermittents
and failures from a JSON file generated by `client.py`
'''

import argparse
import json
import logging
import os
import re
import sys

import requests


def parse_args(cmdln_args):
    '''Parse command line arguments'''
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
    '''Post data to Slack'''
    webhook_url = os.environ.get('SLACK_WEBHOOK')

    try:
        requests.post(url=str(webhook_url), json=data, timeout=15)
    except requests.Timeout:
        logging.error("Request to Slack timed out.")
        raise
    except requests.ConnectionError:
        logging.error("A network problem occurred.")
        raise


def get_slack_emoji(query):
    '''Return Slack emoji based on query'''
    logging.info(f"Received query: {query}")
    match query:
        case 'android-components' | 'firefox-android':
            return ':android:'
        case 'focus-android':
            return ':focusandroid:'
        case 'fenix':
            return ':firefox-browser:'
        case 'flaky':
            return ':warning:'
        case 'reference-browser':
            return ':refbrowser:'
        case 'success':
            return ':white_check_mark:'
        case 'testfailed' | 'failure':
            return ':x:'
        case _:
            logging.warning(f"Unknown query: {query}")
            return ':question:'


def get_header_result_text(text):
    '''Return header result text based on text'''
    match text:
        case 'testfailed':
            return 'flaky | failed tests'
        case 'success':
            return 'flaky tests'


def main():
    '''Main entry point'''
    args = parse_args(sys.argv[1:])

    try:
        with open(args.input, encoding='utf-8') as data_file:
            dataset = json.load(data_file)

            pattern = r"Bug (\d+)"
            bz_base_url = "https://bugzil.la/"

            for section in dataset:
                content, header, footer = ([] for _ in range(3))
                divider = [{"type": "divider"}]
                header = [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": "Daily {} {} {}: {} w/ {}"
                            .format(
                                section['summary']['project'],
                                get_slack_emoji(section['summary']['project']),
                                section['summary']['job_symbol'],
                                get_slack_emoji(section['summary']['job_result']),
                                get_header_result_text(section['summary']['job_result'])
                            )
                        }
                    }
                ]
                footer = [
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": ":testops-notify: created by [<{}|{}>]"
                                .format(
                                    "https://mozilla-hub.atlassian.net/wiki/spaces/MTE/overview",
                                    "Mobile Test Engineering")
                            }
                        ]
                    }
                ]

                job = (next(iter(section.values())))
                for problem in job:
                    if problem['problem_test_details']:
                        for test in problem['problem_test_details']:
                            try:
                                bug_number = re.findall(pattern, problem['pullreq_html_title'])[0]
                                bug_link = f"<{bz_base_url}{bug_number}|Bug>"
                            except IndexError:
                                bug_link = "No Bug"

                            content.append([
                                test['name'],
                                {
                                    "type": "section",
                                    "text": {
                                        "type": "mrkdwn",
                                        "text":
                                        f"`{test['name']}`"
                                    },
                                    "accessory": {
                                        "type": "button",
                                        "text": {
                                            "type": "plain_text",
                                            "text": "{} {}".format(
                                                test['result'],
                                                get_slack_emoji(test['result'])
                                            )
                                        },
                                        "value": "firebase",
                                        "url":
                                        problem['matrix_general_details']
                                        ['webLink'],
                                        "action_id": "button-action"
                                    }
                                },
                                {
                                    "type": "context",
                                    "elements": [
                                        {
                                            "type": "mrkdwn",
                                            "text": f"<{problem['pullreq_html_url']}|Commit>"
                                        },
                                        {
                                            "type": "mrkdwn",
                                            "text": f"<{problem['task_log']}|Task Log>"
                                        },
                                        {
                                            "type": "mrkdwn",
                                            "text": f"<{problem['pushlog']}|Push Log>"
                                        },
                                        {
                                            "type": "mrkdwn",
                                            "text": f"{bug_link}"
                                        },
                                        {
                                            "type": "plain_text",
                                            "text": f"{problem['revision'][:5]}"
                                        },
                                        {
                                            "type": "plain_text",
                                            "text": f"{problem['matrix_general_details']['matrixId']}"
                                        }
                                    ]
                                }
                            ])
                if content:
                    content = sorted(content, key=lambda x: x[0])
                    [x.__delitem__(0) for x in content]
                    content = [item for sublist in content for item in sublist]

                    post_to_slack({'blocks': header + divider + content + divider + footer, 'text': "no-use"})

                    print(f"Slack message posted for [{section['summary']['job_symbol']}] "
                          f"with results [{section['summary']['job_result']}] ({section['summary']['project']})")
                else:
                    print(f"No Slack message posted for [{next(iter(section))}] in "
                          f"[{section['summary']['job_symbol']}] ({section['summary']['project']})")

    except OSError as err:
        raise SystemExit(err) from err


if __name__ == '__main__':
    main()
