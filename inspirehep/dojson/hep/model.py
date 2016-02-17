# -*- coding: utf-8 -*-
#
# This file is part of INSPIRE.
# Copyright (C) 2014, 2015, 2016 CERN.
#
# INSPIRE is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# INSPIRE is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with INSPIRE. If not, see <http://www.gnu.org/licenses/>.
#
# In applying this licence, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as an Intergovernmental Organization
# or submit itself to any jurisdiction.

"""HEP model definition."""

from dojson import Overdo
from dojson.utils import force_list

from ..schema import SchemaOverdo


def add_book_info(record, blob):
    """Add link to the appropriate book record."""
    collections = []
    if 'collections' in record:
        for c in record.get('collections', ''):
            if c.get('primary', ''):
                collections.append(c.get('primary').lower())
        if 'bookchapter' in collections:
            pubinfos = force_list(blob.get("773__", []))
            for pubinfo in pubinfos:
                if pubinfo.get('0'):
                    if isinstance(pubinfo['0'], list):
                        record['book'] = {
                            'recid': int(pubinfo['0'][0])
                        }
                    else:
                        record['book'] = {
                            'recid': int(pubinfo['0'])
                        }


class Publication(SchemaOverdo):

    def do(self, blob):
        output = super(Publication, self).do(blob)
        add_book_info(output, blob)
        return output

hep = Publication(schema="hep-0.0.1.json")
hep2marc = Overdo()
