"""
Generates an HTML report from a dataset containing test results. The report
displays the names of each test, as well as badges indicating whether the test
result was a failure, or flaky. The report also includes links to the
details of each test, the task associated with each test, and the GitHub pull
request that triggered the test run.

Inputs:
- cmdln_args: a list of command-line arguments, including an optional argument
  '--input' specifying the name of the input file containing the test results.

Outputs:
- A report.html file containing an HTML report of the test results.
"""

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import argparse
import json
import sys
from html import escape


def parse_args(cmdln_args):
    parser = argparse.ArgumentParser(
        description='Generates a HTML report from a dataset'
    )

    parser.add_argument(
        '--input',
        default='output.json',
        help='Input (JSON)',
        required=False
    )

    return parser.parse_args(args=cmdln_args)


def generate_html(test_object):
    match test_object["testResult"]:
        case "flaky":
            color = "#FFFFCC"
            test_badge = "https://img.shields.io/badge/flaky-yellow"
        case "failure":
            color = "#ffcccc"
            test_badge = "https://img.shields.io/badge/failure-red"
        case _:
            color = "#ccffcc"
            test_badge = "https://img.shields.io/badge/success-green"
    match test_object["task"]:
        case _:
            task_badge = "https://img.shields.io/badge/-task-lightgrey"
    match test_object["source"]:
        case _:
            source_badge = "https://img.shields.io/badge/Github-Pull%20Request-black"
    return f"""
        <tr style="background-color:{color};">
            <td>{escape(test_object['testName'])}</td>
            <td style="text-align: center;"><a href="{escape(test_object['details'])}"><img src="{test_badge}"></a></td>
            <td style="text-align: center;"><a href="{escape(test_object['task'])}"><img src="{task_badge}"</a></td>
            <td><a href={escape(test_object['source'])}><img src="{source_badge}"</a></td>
        </tr>
    """


def generate_report(section, test_objects):
    tests_html = '\n'.join(generate_html(test) for test in test_objects)

    return f"""
        <!DOCTYPE html>
        <html>
            <head>
                <meta charset="utf-8">
                <title>Test Report</title>
                <style>
                    body {{
                        font-family: Segoe UI;
                    }}
                    table {{
                        border-collapse: collapse;
                    }}
                    th, td {{
                        text-align: left;
                        padding: 8px;
                    }}
                    th {{
                        background-color: #d3d3d3;
                        color: black;
                        font-size: 16px;
                        font-weight: bold;
                    }}
                    </style>
            </head>
            <body>
                <h1>{section}</h1>
                <table>
                    <thead>
                        <tr>
                            <th>Test Name</th>
                            <th><img src="https://www.gstatic.com/mobilesdk/160503_mobilesdk/logo/favicon.ico"></th>
                            <th><img src="https://media.taskcluster.net/favicons/faviconLogo.png"></th>
                            <th><img src="https://github.com/favicon.ico"></th>
                        </tr>
                    </thead>
                    <tbody>
                        {tests_html}
                    </tbody>
                </table>
            </body>
        </html>
    """


def write_report(report, filename):
    try:
        with open(filename, 'a') as report_file:
            report_file.write(report)
    except Exception as err:
        print(f"An error occurred while writing the report to {filename}: {err}")
        raise SystemExit(err) from err


def main():
    args = parse_args(sys.argv[1:])

    try:
        with open(args.input, encoding='utf-8') as data_file:
            dataset = json.load(data_file)

            for section in dataset:
                content = []
                job = (next(iter(section.values())))
                for problem in job:
                    if problem['problem_test_details']:
                        for test in problem['problem_test_details']:
                            content.append([
                                test['name'],
                                {
                                    "testName": test['name'],
                                    "testResult": test['result'],
                                    "source": problem['pullreq_html_url'],
                                    "details": problem['matrix_general_details']['webLink'],
                                    "task": problem['task_html_url']
                                }
                            ])

                if content:
                    content = sorted(content, key=lambda x: x[0])
                    [x.__delitem__(0) for x in content]          
                    content = [item for sublist in content for item in sublist]
                    p = generate_report(
                        f"{section['summary']['project']}  {next(iter(section))}",
                        content
                    )

                    write_report(p, "report.html")

                    print(f"Report written for [{section['summary']['job_symbol']}] "
                          f"with results [{section['summary']['job_result']}] ({section['summary']['project']})")
                else:
                    print(f"No report generated for [{next(iter(section))}] in "
                          f"[{section['summary']['job_symbol']}] ({section['summary']['project']})")
    except OSError as err:
        raise SystemExit(err) from err


if __name__ == '__main__':
    main()
