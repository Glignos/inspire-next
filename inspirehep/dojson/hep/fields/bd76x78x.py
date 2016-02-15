# -*- coding: utf-8 -*-
#
# This file is part of INSPIRE.
# Copyright (C) 2014, 2015 CERN.
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

"""MARC 21 model definition."""

from dojson import utils

from ..model import hep, hep2marc


@hep.over('publication_info', '^773..')
@utils.for_each_value
@utils.filter_values
def publication_info(self, key, value):
    """Publication info about record."""
    def get_int_value(val):
        if val:
            out = utils.force_list(val)[0]
            if out.isdigit():
                out = int(out)
                return out
        return None

    year = get_int_value(value.get('y'))
    parent_recid = get_int_value(value.get('0'))
    journal_recid = get_int_value(value.get('1'))
    conference_recid = get_int_value(value.get('2'))

    return {
        'parent_recid': parent_recid,
        'journal_recid': journal_recid,
        'conference_recid': conference_recid,
        'page_artid': value.get('c'),
        'journal_issue': value.get('n'),
        'conf_acronym': value.get('o'),
        'journal_title': value.get('p'),
        'reportnumber': value.get('r'),
        'confpaper_info': value.get('t'),
        'journal_volume': value.get('v'),
        'cnum': utils.force_list(value.get('w')),
        'pubinfo_freetext': value.get('x'),
        'year': year,
        'isbn': value.get('z'),
        'note': value.get('m'),
    }


@hep2marc.over('773', 'publication_info')
@utils.for_each_value
@utils.filter_values
def publication_info2marc(self, key, value):
    """Publication info about record."""
    return {
        '0': value.get('parent_recid'),
        'c': value.get('page_artid'),
        'n': value.get('journal_issue'),
        'o': value.get('conf_acronym'),
        'p': value.get('journal_title'),
        'r': value.get('reportnumber'),
        't': value.get('confpaper_info'),
        'v': value.get('journal_volume'),
        'w': value.get('cnum'),
        'x': value.get('pubinfo_freetext'),
        'y': value.get('year'),
        'z': value.get('isbn'),
        'm': value.get('note')
    }


@hep.over('succeeding_entry', '^785..')
def succeeding_entry(self, key, value):
    """Succeeding Entry."""
    if isinstance(value, (tuple, list)):
        # Too bad: there can only be one succeeding entry.
        value = value[0]

    return {
        'relationship_code': value.get('r'),
        'recid': value.get('w'),
        'isbn': value.get('z'),
    }


@hep2marc.over('785', 'succeeding_entry')
def succeeding_entry2marc(self, key, value):
    """Succeeding Entry."""
    return {
        'r': value.get('relationship_code'),
        'w': value.get('recid'),
        'z': value.get('isbn'),
    }
