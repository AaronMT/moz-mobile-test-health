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

import requests

session = requests.Session()


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


def search_bugs(test_name):
    url = "https://bugzilla.mozilla.org/rest/bug"
    params = {
        "summary": test_name,
        "status": ["UNCONFIRMED", "NEW", "ASSIGNED", "REOPENED"]
    }
    response = session.get(url, params=params)

    if response.status_code != 200:
        return None

    results = json.loads(response.content.decode())
    bugs = []

    for result in results["bugs"]:
        bug = {
            "id": result["id"],
            "summary": result["summary"],
            "url": f"https://bugzilla.mozilla.org/show_bug.cgi?id={result['id']}"
        }
        bugs.append(bug)

    return bugs


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
            task_badge = "https://img.shields.io/badge/-task-lightblue"
    match test_object["source"]:
        case _:
            source_badge = "https://img.shields.io/badge/Github-Pull%20Request-lightgrey"

    bugs = search_bugs(test_object['testName'])

    if bugs:
        bug_list = '<ul>'
        for bug in bugs:
            bug_list += f'<li><a href="{bug["url"]}">{bug["summary"]} (#{bug["id"]})</a></li>'
            bug_html = f'{bug_list}'
        bug_list += '</ul>'

    else:
        bug_html = '<a href="https://bugzilla.mozilla.org/enter_bug.cgi?product=Fenix&component=UI%20Tests">' \
                   '<img src=https://img.shields.io/badge/bugzilla-new%20bug-green></a>'

    return f"""
        <tr style="background-color:{color};">
            <td>
                <div class="test-name" onclick="toggleDetails('{escape(test_object['testName'])}_details')">
                   <span class="icon">&#43;</span> {escape(test_object['testName'])}
                </div>
               </div>
                <div id="{escape(test_object['testName'])}_details" style="display:none;" onclick="event.stopPropagation();">
                    <div class="toggle" onclick="toggleDetails('{escape(test_object['testName'])}_details')">
                        <span class="icon">&#8722;</span>
                    </div>
                    <div style="display: inline-block;">
                      <div class="details-link">Hide details</div>
                    </div>
                    <div class="console-wrapper">
                        {bug_html}
                    </div>
                    <div class="console-wrapper">
                        <pre class="console-output log">
                            <code>{escape(test_object['trace'])}</code>
                        </pre>
                    </div>
                </div>
            </td>
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
                <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.2.0/styles/default.min.css" />
                <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.2.0/highlight.min.js"></script>
                <style>
                    body {{
                        font-family: "Open Sans", sans-serif;
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
                    .console-output {{
                        font-family: monospace;
                        font-size: 12px;
                        line-height: 1.4;
                        background-color: #f4f4f4;
                        border-radius: 5px;
                        padding: 10px;
                        white-space: pre-wrap;
                    }}
                    .test-name {{
                        font-family: "Open Sans", sans-serif;
                        font-weight: bold;
                        font-size: 14px;
                        padding: 5px;
                        margin-bottom: 10px;
                        border-radius: 5px;
                    }}
                    .console-wrapper {{
                        overflow-y: auto;
                        padding: 10px;
                        max-height: 150px
                    }}
                    .bugs {{
                        font-family: "Open Sans", sans-serif;"
                        font-size: 12px;
                    }}
                    .toggle {{
                       display: inline-block;
                       cursor: pointer;
                    }}
                    .details-link {{
                        font-family: "Open Sans", sans-serif;
                        font-size: 12px;
                    }}
                    ul {{
                        padding-left: 60px;
                        list-style-image: url('https://img.shields.io/badge/-bugzilla-green');
                    }}
                    li {{
                        vertical-align: -2px;
                    }}
                </style>
                <script>
                    function toggleDetails(id) {{
                        var element = document.getElementById(id);
                        if (element.style.display === "none") {{
                            element.style.display = "block";
                        }} else {{
                            element.style.display = "none";
                        }}
                    }}
                </script>
                <script>
                    document.addEventListener("DOMContentLoaded", function() {{
                        hljs.highlightAll();
                    }});
                </script>
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
                                    "trace": test['details'],
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
