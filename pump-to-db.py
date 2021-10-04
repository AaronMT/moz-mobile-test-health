#! /usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

'''

'''

import argparse
import json
import sqlite3 as sl
import sys


def parse_args(cmdln_args):
    parser = argparse.ArgumentParser(
        description='database operations on test daily test dataset'
    )

    parser.add_argument(
        '--input',
        default='output.json',
        help='Input (JSON)',
        required=False
    )

    return parser.parse_args(args=cmdln_args)


class SQL:

    def __init__(self):
        self.con = sl.connect('my-test.db')

    def create_table(self):
        try:
            with self.con:
                self.con.execute("""
                    CREATE TABLE Intermittents (
                        `Test Name` VARCHAR(60) NOT NULL,
                        `Result` VARCHAR(20) NOT NULL,
                        `Frequency` INT(3) NOT NULL);
                """)
        except sl.OperationalError as e:
            print(e)

    def check_for_record(self, test):
        sql = 'SELECT 1 FROM Intermittents WHERE `Test Name` = "{}" AND `Result` = "{}"'.format(
            test['name'], test['result']
        )
        with self.con:
            record = self.con.execute(sql)
            count = len(record.fetchall())
        return True if count > 0 else False

    def update_record(self, test):
        sql = 'UPDATE Intermittents SET `Frequency` = `Frequency` + 1 WHERE `Test Name` = "{}" AND `Result` = "{}"'.format(
            test['name'], test['result']
        )
        with self.con:
            self.con.execute(sql)

    def insert_record(self, test):
        sql = 'INSERT INTO Intermittents (`Test name`, `Result`, `Frequency`) VALUES ("{}", "{}", 1)'.format(
            test['name'], test['result']
        )
        with self.con:
            self.con.execute(sql)


def main():
    args = parse_args(sys.argv[1:])

    sql = SQL()
    sql.create_table()

    try:
        with open(args.input) as data_file:
            dataset = json.load(data_file)
            for section in dataset:
                job = (next(iter(section.values())))
                for problem in job:
                    if problem['problem_test_details']:
                        for test in problem['problem_test_details']:
                            if sql.check_for_record(test) is True:
                                sql.update_record(test)
                            else:
                                sql.insert_record(test)
    except OSError as e:
        print(e)
        sys.exit(1)


if __name__ == '__main__':
    main()
