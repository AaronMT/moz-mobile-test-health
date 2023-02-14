# moz-mobile-test-health
## About

Small client script for fetching push and job metadata from provided Taskcluster configuration and building a sharable JSON dataset from the Treeherder API through [the existing API client](https://pypi.org/project/treeherder-client/).

This is primarily useful for finding flaky and failing tests from UI test jobs on mobile projects at Mozilla.

Use `post.py` to forward payload data to a pre-configured Slack message payload.

### Requirements

Requires exporting a Github API token and an optional Slack API token (requires setting up an application on your own)

### Installation
Recommend creating a Python3 virtual environment
`pip install -r requirements.txt`

### Usage
```sh
python3 client.py 
usage: client.py [-h] --project PROJECT [--config CONFIG] [--disabled-tests]
```
### Examples

```sh
python client.py --project=firefox-android
```

### Output

```sh
Fetching [6] in [firefox-android] ['job.ui-samples-browser.success', 'job.ui-samples-browser.testfailed', 'job.ui-components.success', 'job.ui-components.testfailed', 'job.ui-samples-glean.success', 'job.ui-samples-glean.testfailed']

Fetching result [success] in [ui-samples-browser] (100 max pushes) from the past [1] day(s) ...
Output written to LOG file

Output written to [output.json]
```
#### Output.log
```Log
...
INFO:databuilder:Duration: 24 min mergify[bot]@users.noreply.github.com - success - https://firefox-ci-tc.services.mozilla.com/tasks/MLbg1O5vQsSkgS2EDnI6jw - 2022-11-21T07:25:15.225441 - https://firefox-ci-tc.services.mozilla.com/api/queue/v1/task/MLbg1O5vQsSkgS2EDnI6jw/runs/0/artifacts/public/logs/live_backing.log - [1 test cases passed, 1 flaky] - [flaky] - https://console.firebase.google.com/project/moz-android-components-230120/testlab/histories/bh.9f526cd30412cc12/matrices/5316543285647261116 - 9a41f9e49ccab08075a0dd067550804f6bf0f4c7 - [{'name': 'loadWebsitesInMultipleTabsTest', 'result': 'flaky'}] - https://github.com/mozilla-mobile/firefox-android/pull/168 - Bug 1801164 - Don't try and record history for URLs with an invalid scheme.
...

INFO:databuilder:Summary: [ui-samples-browser]
INFO:databuilder:Duration average: 19 minutes
INFO:databuilder:Results: 1
```
Example in the above output we have flaky tests logged.

#### Output.json

The JSON dataset created will contain object data housing a summary of all data fetched from various sources (e.g, Taskcluster, Treeherder, Github and Firebase) related to the flaky or failing testcase.

E.g, summary object from the above results

```JSON
"problem_test_details":[{ 
    "name": "loadWebsitesInMultipleTabsTest",
    "result": "flaky"
}]
```

## Slack

`post.py` requires an `output.json` payload to post. This payload is created from the above client. A Slack API token is also required to be exported in local environment.

### Usage

    python3 post.py

### Output
```
Slack message posted for [ui-samples-browser.success] results
No failures or intermittents in (job.ui-components.success) in [ui-components]. No Slack message posted.
No failures or intermittents in (job.ui-samples-glean.success) in [ui-samples-glean]. No Slack message posted.
```

## TODO

- [🌟] Consolidate project configuration sections into a list using ConfigParser converters