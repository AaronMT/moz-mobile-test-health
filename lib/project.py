#! /usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.


class Project:
    def __init__(self, project):
        self.project_configuration = self.set_project(project)

    def set_project(self, project):
        return self.get_project_configuration(project)

    def get_project_configuration(self, project):
        '''Reads INI configuration file'''
        import configparser
        config = configparser.ConfigParser()
        config.read(f'configurations/{project}.ini')
        return config
