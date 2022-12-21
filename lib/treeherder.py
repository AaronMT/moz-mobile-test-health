#! /usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

'''Treeherder module for fetching data from Treeherder'''

import logging

from thclient import TreeherderClient

logging.basicConfig(filename='output.log', filemode='w', level=logging.INFO)
logger = logging.getLogger(__name__)


class Treeherder:
    '''Treeherder class for fetching data from Treeherder'''

    def __init__(self, project):
        self.project = project
        self.config = self.get_global_config()
        self.client = self.set_client()

    def get_global_config(self):
        return TreeherderConfig.read_global_config(self)  # type: ignore

    def set_client(self):
        return self.create_client()

    def create_client(self):
        return TreeherderClient(
            server_url=self.config['production']['host']
        )

    def get_client(self):
        return self.client

    def get_pushes(self):
        from datetime import date, timedelta

        import requests

        try:
            return self.client.get_pushes(
                project=self.project,
                count=int(self.config['pushes']['maxcount']),
                enddate=date.today().isoformat(),
                startdate=date.today() - timedelta(
                    days=int(self.config['pushes']['days'])
                )
            )
        except requests.exceptions.HTTPError as err:
            raise SystemExit(err) from err


class TreeherderConfig:
    '''TreeherderConfig class for reading from INI config file'''

    def __init__(self):
        pass

    def read_global_config(self):
        import configparser
        config = configparser.ConfigParser()
        config.read('configurations/config.ini')
        return config


class TreeherderHelper:
    '''TreeherderHelper utility class'''

    def __init__(self, project):
        self.client = Treeherder(project)
        self.project_configuration = self.get_project_configuration(project)
        self.global_configuration = self.client.config

    def get_project_configuration(self, project):
        from lib.project import Project
        return Project(project).project_configuration

    def get_pushes(self):
        return self.client.get_pushes()

    def get_client(self):
        return self.client.get_client()
