# -*- coding: utf-8 -*-
#
# This file is part of INSPIRE.
# Copyright (C) 2015 CERN.
#
# INSPIRE is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# INSPIRE is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with INSPIRE. If not, see <http://www.gnu.org/licenses/>.
#
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as an Intergovernmental Organization
# or submit itself to any jurisdiction.

"""Manage migration from INSPIRE legacy instance."""

from __future__ import print_function

import os
import sys

from flask import current_app

from invenio.ext.es import create_index as create_main_index
from invenio.ext.es import delete_index as delete_main_index
from invenio.ext.script import Manager
from invenio.ext.sqlalchemy import db

from invenio_workflows.receivers import create_holdingpen_index
from invenio_workflows.receivers import delete_holdingpen_index

from .tasks import migrate

manager = Manager(description=__doc__)


@manager.option('--records', '-r', dest='records',
                action='append',
                default=None,
                help='Specific record IDs to migrate.')
@manager.option('--collection', '-c', dest='collections',
                action='append',
                default=None,
                help='Specific collections to migrate.')
@manager.option('--input', '-f', dest='file_input',
                help='Specific collections to migrate.')
def populate(records, collections, file_input=None):
    """Train a set of records from the command line.

    Usage: inveniomanage predicter train -r /path/to/json -o model.pickle
    """
    if records is None and collections is None:
        # We harvest all
        print("Migrating all records...", file=sys.stderr)
    if records:
        print("Migrating records: {0}".format(",".join(records)))
    if collections:
        print("Migrating collections: {0}".format(",".join(collections)))

    if file_input and not os.path.isfile(file_input):
        print("{0} is not a file!".format(file_input), file=sys.stderr)
        return

    legacy_base_url = current_app.config.get("CFG_INSPIRE_LEGACY_BASEURL")
    print("Migrating records from {0}".format(legacy_base_url), file=sys.stderr)

    job = migrate.delay(legacy_base_url,
                        records=records,
                        collections=collections,
                        file_input=file_input)
    print("Scheduled job {0}".format(job.id))


@manager.command
def remove_bibxxx():
    """Drop all the legacy bibxxx tables."""
    table_names = db.engine.execute(
        "SELECT TABLE_NAME"
        " FROM INFORMATION_SCHEMA.TABLES"
        " WHERE ENGINE='MyISAM'"
        " AND TABLE_NAME LIKE '%%_bib%%x'"
        " AND table_schema='{0}'".format(
            current_app.config.get('CFG_DATABASE_NAME')
        )
    ).fetchall()
    for table in table_names:
        db.engine.execute("DROP TABLE {0}".format(table[0]))
        print(">>> Dropped {0}.".format(table[0]))
    print(">>> Removed {0} tables.".format(len(table_names)))


@manager.command
def remove_idx():
    """Deop all the legacy BibIndex tables."""
    table_names = db.engine.execute(
        "SELECT TABLE_NAME"
        " FROM INFORMATION_SCHEMA.TABLES"
        " WHERE ENGINE='MyISAM'"
        " AND TABLE_NAME LIKE 'idx%%'"
        " AND table_schema='{0}'".format(
            current_app.config.get('CFG_DATABASE_NAME')
        )
    ).fetchall()
    for table in table_names:
        db.engine.execute("DROP TABLE {0}".format(table[0]))
        print(">>> Dropped {0}.".format(table[0]))
    print(">>> Removed {0} tables.".format(len(table_names)))


@manager.command
def create_index():
    """Create or recreate the indices for records and holdingpen.

    The methods called require an argument which then they don't use.
    So we work around that by passing a dummy argument.
    """
    create_main_index('banana')
    create_holdingpen_index('banana')


@manager.command
def delete_index():
    """Delete the indices for records and holdingpen.

    The methods called require an argument which then they don't use.
    So we work around that by passing a dummy argument.
    """
    delete_main_index('banana')
    delete_holdingpen_index('banana')


@manager.command
def clean_records():
    """Truncate all the records from various tables."""
    from sqlalchemy.engine import reflection

    print('>>> Truncating all records.')

    fks = []
    db.session.begin(subtransactions=True)
    try:
        db.engine.execute("SET FOREIGN_KEY_CHECKS=0;")

        # Grab any table with foreign keys to bibrec for truncating
        inspector = reflection.Inspector.from_engine(db.engine)
        for table_name in inspector.get_table_names():
            for fk in inspector.get_foreign_keys(table_name):
                if not fk["referred_table"] == "bibrec":
                    continue
                fks.append(fk["referred_table"])

        for table in fks:
            db.engine.execute("TRUNCATE TABLE {0}".format(table))
            print(">>> Truncated {0}".format(table))
        db.engine.execute("TRUNCATE TABLE bibrec")
        print(">>> Truncated bibrec")
        db.engine.execute("TRUNCATE TABLE record_json")
        print(">>> Truncated record_json")
        db.engine.execute("DELETE FROM pidSTORE WHERE pid_type='recid'")
        print(">>> Truncated pidSTORE WHERE pid_type='recid'")

        db.engine.execute("SET FOREIGN_KEY_CHECKS=1;")
        db.session.commit()
    except Exception as err:
        db.session.rollback()
        current_app.logger.exception(err)
