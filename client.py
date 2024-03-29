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


def parse_args():
    import argparse
    parser = argparse.ArgumentParser(
        description="Supply a INI configuration file to "
                    "fetch data from Treeherder, Github, and Taskcluster "
                    "and build a sharable JSON dataset "
                    "for the Mozilla Mobile Test Engineering team "
                    "to use for analysis and reporting. "
                    "See README.md for more information. "
                    "Example: python client.py --project firefox-android",
        epilog="Note: This script requires a GITHUB_TOKEN environment variable to be set (optional: SLACK_WEBHOOK)."
    )
    parser.add_argument(
        "--project",
        help="Project configuration "
             "(e.g. 'mozilla-mobile/firefox-android')",
        required=True
    )
    parser.add_argument(
        '--disabled-tests',
        default=False,
        required=False,
        action='store_true',
        help='Query list of disabled tests'
    )

    return parser.parse_args()


def main():
    from lib.databuilder import data_builder
    args = parse_args()
    data_builder = data_builder()
    data_builder.build_complete_dataset(args)


if __name__ == "__main__":
    main()
