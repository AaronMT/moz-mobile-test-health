# moz-mobile-test-health
## About

Small treeherder-client script for fetching push and job metadata from provided configuration and building a sharable JSON dataset from the Treeherder API through [the existing API client](https://pypi.org/project/treeherder-client/).

This is primarily useful for finding flaky and failing tests from UI test jobs on mobile projects at Mozilla.

Use `post.py` to forward payload data to a pre-configured Slack message payload.

### Requirements

Requires exporting a Github API token and an optional Slack API token (requires setting up an application on your own)

### Installation
Recommend creating a Python3 virtual environment
`pip install -r requirements.txt`

### Usage
```sh
python3 treeherder-client.py 
usage: treeherder-client.py [-h] --project PROJECT [--config CONFIG] [--disabled-tests]
treeherder-client.py: error: the following arguments are required: --project
```
### Examples

```sh
python treeherder-client.py --project=focus-android
```

### Output

```sh
Fetching [2] queries in [focus-android] ['job.ui-test-x86.success', 'job.ui-test-x86.testfailed']

Fetching result [success] in [ui-test-x86] (100 max pushes) from the past [1] day(s) ...
Output written to LOG file

Fetching result [testfailed] in [ui-test-x86] (100 max pushes) from the past [1] day(s) ...
No results found with provided config.

Output written to [output.json]
```
#### Output.log
```Log
INFO:__main__:Duration: 8 min @noreply.mozilla.org - success - https://firefox-ci-tc.services.mozilla.com/tasks/QsFHcMKQSWmx3m0YO7OQnA - 2021-11-22T09:50:36.142707 - https://firefox-ci-tc.services.mozilla.com/api/queue/v1/task/QsFHcMKQSWmx3m0YO7OQnA/runs/0/artifacts/public/logs/live_backing.log - [70 test cases passed] - [success] - https://console.firebase.google.com/project/moz-focus-android/testlab/histories/bh.2189b040bbce6d5a/matrices/7376268047555971089 - 046c38938a96d856c4d041ccba529c2037dd01e8 - [] - https://github.com/mozilla-mobile/focus-android/pull/5895 - l10n-tests-add-screengrabfile
INFO:__main__:Duration: 11 min @noreply.mozilla.org - success - https://firefox-ci-tc.services.mozilla.com/tasks/XtNh3KqYTmmka0cKhqcdWw - 2021-11-22T12:35:07.867546 - https://firefox-ci-tc.services.mozilla.com/api/queue/v1/task/XtNh3KqYTmmka0cKhqcdWw/runs/0/artifacts/public/logs/live_backing.log - [69 test cases passed, 1 flaky] - [flaky] - https://console.firebase.google.com/project/moz-focus-android/testlab/histories/bh.2189b040bbce6d5a/matrices/9180648678380244643 - 15e4d7f1b8fc13943b4ee31bf618b87bca8433f8 - [{'name': 'notificationEraseAndOpenButtonTest', 'result': 'flaky'}] - https://github.com/mozilla-mobile/focus-android/pull/5922 - Import strings from android-l10n.
INFO:__main__:Duration: 8 min @noreply.mozilla.org - success - https://firefox-ci-tc.services.mozilla.com/tasks/Qe27klpHSJebCpU8ktBrAg - 2021-11-22T15:14:57.688063 - https://firefox-ci-tc.services.mozilla.com/api/queue/v1/task/Qe27klpHSJebCpU8ktBrAg/runs/0/artifacts/public/logs/live_backing.log - [70 test cases passed] - [success] - https://console.firebase.google.com/project/moz-focus-android/testlab/histories/bh.2189b040bbce6d5a/matrices/7666042062316364726 - 55dfeb87e7b6b072ad29a45fa93787a5a1512fa6 - [] - https://github.com/mozilla-mobile/focus-android/pull/5800 - Issue #5795: Replace "multiple tabs" feature flag with Nimbus experiment
INFO:__main__:Duration: 8 min @noreply.mozilla.org - success - https://firefox-ci-tc.services.mozilla.com/tasks/e5sIWyHPQceCq-O_G9KUsQ - 2021-11-22T15:25:59.056713 - https://firefox-ci-tc.services.mozilla.com/api/queue/v1/task/e5sIWyHPQceCq-O_G9KUsQ/runs/0/artifacts/public/logs/live_backing.log - [70 test cases passed] - [success] - https://console.firebase.google.com/project/moz-focus-android/testlab/histories/bh.2189b040bbce6d5a/matrices/8989374055191914422 - 55dfeb87e7b6b072ad29a45fa93787a5a1512fa6 - [] - https://github.com/mozilla-mobile/focus-android/pull/5800 - Issue #5795: Replace "multiple tabs" feature flag with Nimbus experiment
INFO:__main__:Duration: 6 min @noreply.mozilla.org - success - https://firefox-ci-tc.services.mozilla.com/tasks/XLwNghlvRrSFU-jD82_nmQ - 2021-11-22T15:50:46.580095 - https://firefox-ci-tc.services.mozilla.com/api/queue/v1/task/XLwNghlvRrSFU-jD82_nmQ/runs/0/artifacts/public/logs/live_backing.log - [57 test cases passed] - [success] - https://console.firebase.google.com/project/moz-focus-android/testlab/histories/bh.2189b040bbce6d5a/matrices/8472897554622531441 - 8cbaae95a5710054d63bc4ba113792315761d561 - [] - https://github.com/mozilla-mobile/focus-android/pull/5852 - Relocate erase and tabs counter to toolbar
INFO:__main__:Duration: 6 min @noreply.mozilla.org - success - https://firefox-ci-tc.services.mozilla.com/tasks/fyXtyReeSGeVzPItZ3foUg - 2021-11-22T16:16:57.391155 - https://firefox-ci-tc.services.mozilla.com/api/queue/v1/task/fyXtyReeSGeVzPItZ3foUg/runs/0/artifacts/public/logs/live_backing.log - [57 test cases passed] - [success] - https://console.firebase.google.com/project/moz-focus-android/testlab/histories/bh.2189b040bbce6d5a/matrices/6371871301889249232 - 510e1117d30624680bee481aee0a758754a644d3 - [] - https://github.com/mozilla-mobile/focus-android/pull/5928 - Update to Android-Components 96.0.20211122143347.
INFO:__main__:Duration: 7 min @noreply.mozilla.org - success - https://firefox-ci-tc.services.mozilla.com/tasks/XLAWVgHwSg6S9yIXDJ7wCA - 2021-11-22T19:58:03.599580 - https://firefox-ci-tc.services.mozilla.com/api/queue/v1/task/XLAWVgHwSg6S9yIXDJ7wCA/runs/0/artifacts/public/logs/live_backing.log - [57 test cases passed] - [success] - https://console.firebase.google.com/project/moz-focus-android/testlab/histories/bh.2189b040bbce6d5a/matrices/6410855674592003851 - 510e1117d30624680bee481aee0a758754a644d3 - [] - https://github.com/mozilla-mobile/focus-android/pull/5928 - Update to Android-Components 96.0.20211122143347.
INFO:__main__:Duration: 9 min @noreply.mozilla.org - success - https://firefox-ci-tc.services.mozilla.com/tasks/P2mLCtHRRDONTclZzf9cfQ - 2021-11-22T20:36:17.714679 - https://firefox-ci-tc.services.mozilla.com/api/queue/v1/task/P2mLCtHRRDONTclZzf9cfQ/runs/0/artifacts/public/logs/live_backing.log - [57 test cases passed] - [success] - https://console.firebase.google.com/project/moz-focus-android/testlab/histories/bh.2189b040bbce6d5a/matrices/5119296087529725469 - 4f153c48bf134e5fe263fde75e79450e05140104 - [] - https://github.com/mozilla-mobile/focus-android/pull/5930 - Update to Android-Components 96.0.20211122190138.
INFO:__main__:Duration: 7 min @noreply.mozilla.org - success - https://firefox-ci-tc.services.mozilla.com/tasks/DYI4GzN_Rs-VVg_dbwzHsg - 2021-11-23T08:25:00.225132 - https://firefox-ci-tc.services.mozilla.com/api/queue/v1/task/DYI4GzN_Rs-VVg_dbwzHsg/runs/0/artifacts/public/logs/live_backing.log - [57 test cases passed] - [success] - https://console.firebase.google.com/project/moz-focus-android/testlab/histories/bh.2189b040bbce6d5a/matrices/6863948469283992561 - b5255050e2d2676fb107891a0d1a2c2cb25afbc1 - [] - https://github.com/mozilla-mobile/focus-android/pull/5886 - For #5885: Migrate autocomplete domains related telemetry.
INFO:__main__:Duration: 7 min @noreply.mozilla.org - success - https://firefox-ci-tc.services.mozilla.com/tasks/DkpzJljHR9GSDOzrP09WXg - 2021-11-23T10:23:30.271089 - https://firefox-ci-tc.services.mozilla.com/api/queue/v1/task/DkpzJljHR9GSDOzrP09WXg/runs/0/artifacts/public/logs/live_backing.log - [57 test cases passed] - [success] - https://console.firebase.google.com/project/moz-focus-android/testlab/histories/bh.2189b040bbce6d5a/matrices/5726758187094649929 - 74299ea50aed1db53b9f360dff4d7e4996f70176 - [] - https://github.com/mozilla-mobile/focus-android/pull/5917 - For #5914: Migrate telemetry related to back button navigation.
INFO:__main__:Duration: 7 min @noreply.mozilla.org - success - https://firefox-ci-tc.services.mozilla.com/tasks/Uy6G5zytSF6nfqGDC0cdqA - 2021-11-23T11:26:15.554149 - https://firefox-ci-tc.services.mozilla.com/api/queue/v1/task/Uy6G5zytSF6nfqGDC0cdqA/runs/0/artifacts/public/logs/live_backing.log - [57 test cases passed] - [success] - https://console.firebase.google.com/project/moz-focus-android/testlab/histories/bh.2189b040bbce6d5a/matrices/6022212403567452227 - 989d1bb47702f9d2de9de02bb3b362bfeebbc9a8 - [] - https://github.com/mozilla-mobile/focus-android/pull/5931 - Import strings from android-l10n.
INFO:__main__:Duration: 7 min @noreply.mozilla.org - success - https://firefox-ci-tc.services.mozilla.com/tasks/FK7plTGLRHSUPH9TRHSaJw - 2021-11-23T13:26:02.867200 - https://firefox-ci-tc.services.mozilla.com/api/queue/v1/task/FK7plTGLRHSUPH9TRHSaJw/runs/0/artifacts/public/logs/live_backing.log - [57 test cases passed] - [success] - https://console.firebase.google.com/project/moz-focus-android/testlab/histories/bh.2189b040bbce6d5a/matrices/4634043516685354457 - 438daf6a52cb2f6393c1202a63133729af35f850 - [] - https://github.com/mozilla-mobile/focus-android/pull/5898 - For #5897: Migrate report site issue telemetry.
INFO:__main__:Duration: 7 min @noreply.mozilla.org - success - https://firefox-ci-tc.services.mozilla.com/tasks/LrYfb7w3RT6is-g2MObkBA - 2021-11-23T14:16:54.278047 - https://firefox-ci-tc.services.mozilla.com/api/queue/v1/task/LrYfb7w3RT6is-g2MObkBA/runs/0/artifacts/public/logs/live_backing.log - [57 test cases passed] - [success] - https://console.firebase.google.com/project/moz-focus-android/testlab/histories/bh.2189b040bbce6d5a/matrices/8305881186039156474 - e4276ca953d73ab89d0d37ed663e96bc74d68905 - [] - https://github.com/mozilla-mobile/focus-android/pull/5932 - Use the correct value of toolbar height at dynamic behavior
INFO:__main__:Duration: 7 min @noreply.mozilla.org - success - https://firefox-ci-tc.services.mozilla.com/tasks/dUIlGfv4TVKn4nzLj3g6tA - 2021-11-23T15:25:24.617542 - https://firefox-ci-tc.services.mozilla.com/api/queue/v1/task/dUIlGfv4TVKn4nzLj3g6tA/runs/0/artifacts/public/logs/live_backing.log - [57 test cases passed] - [success] - https://console.firebase.google.com/project/moz-focus-android/testlab/histories/bh.2189b040bbce6d5a/matrices/8625103808576983634 - e4276ca953d73ab89d0d37ed663e96bc74d68905 - [] - https://github.com/mozilla-mobile/focus-android/pull/5932 - Use the correct value of toolbar height at dynamic behavior
INFO:__main__:Summary: [ui-test-x86]
INFO:__main__:Duration average: 7 minutes
INFO:__main__:Results: 14 
```
Example in the above output we have a flaky test fetched.

#### Output.json

The JSON dataset created will contain object data housing a summary of all data fetched from various sources (e.g, Taskcluster, Treeherder, Github and Firebase) related to the flaky or failing testcase.

E.g, from the above results

```JSON
"problem_test_details":[{ 
    "name": "notificationEraseAndOpenButtonTest",
    "result": "flaky"
}]
```

## Slack

`post.py` requires an `output.json` payload to post. This payload is created from the above client. A Slack API token is also required to be exported in local environment.

### Usage

    python3 post.py

### Output
```
Slack message posted for [ui-test-x86.success] results
```
