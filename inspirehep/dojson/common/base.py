# -*- coding: utf-8 -*-
#
# This file is part of INSPIRE.
# Copyright (C) 2014, 2015, 2016, 2017 CERN.
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

"""Common DoJSON rules."""

from __future__ import absolute_import, division, print_function

import re

from dojson import utils

from inspire_schemas.api import load_schema
from inspirehep.utils.helpers import force_force_list

from ..conferences.model import conferences
from ..experiments.model import experiments
from ..hep.model import hep, hep2marc
from ..hepnames.model import hepnames, hepnames2marc
from ..institutions.model import institutions
from ..jobs.model import jobs
from ..journals.model import journals
from ..utils import (
    classify_field,
    force_single_element,
    get_recid_from_ref,
    get_record_ref,
)


@hep.over('acquisition_source', '^541..')
@hepnames.over('acquisition_source', '^541..')
def acquisition_source(self, key, value):
    def _get_source(value):
        sources = force_force_list(value.get('a'))
        sources_without_inspire_uid = [
            el for el in sources if not el.startswith('inspire:uid:')]

        return force_single_element(sources_without_inspire_uid)

    def _get_orcid(value):
        orcids = force_force_list(value.get('a'))
        orcid = [el[6:] for el in orcids
                 if re.match('^orcid:\\d{4}-\\d{4}-\\d{4}-\\d{3}[0-9X]$', el)]

        return force_single_element(orcid)

    return {
        'date': value.get('d'),
        'email': value.get('b'),
        'method': value.get('c'),
        'source': _get_source(value),
        'submission_number': value.get('e'),
        'orcid': _get_orcid(value),
    }


@hep2marc.over('541', '^acquisition_source$')
@hepnames2marc.over('541', '^acquisition_source$')
def acquisition_source2marc(self, key, value):
    def _get_a(value):
        # ORCID has the priority over source
        if value.get('orcid'):
            return value.get('orcid')
        return value.get('source')

    return {
        'a': _get_a(value),
        'b': value.get('email'),
        'c': value.get('method'),
        'd': value.get('date'),
        'e': value.get('submission_number'),
    }


def self_url(index):
    def _self_url(self, key, value):
        """Url of the record itself."""
        self['control_number'] = int(value)
        return get_record_ref(value, index)
    return _self_url

institutions.over('self', '^001')(self_url('institutions'))
hep.over('self', '^001')(self_url('literature'))
conferences.over('self', '^001')(self_url('conferences'))
experiments.over('self', '^001')(self_url('experiments'))
journals.over('self', '^001')(self_url('journals'))
hepnames.over('self', '^001')(self_url('authors'))
jobs.over('self', '^001')(self_url('jobs'))


@hep2marc.over('001', '^control_number$')
@hepnames2marc.over('001', '^control_number$')
def control_number2marc(self, key, value):
    """Record Identifier."""
    return value


@hep.over('external_system_identifiers', '^970..')
@conferences.over('external_system_identifiers', '^970..')
@institutions.over('external_system_identifiers', '^970..')
@experiments.over('external_system_identifiers', '^970..')
@journals.over('external_system_identifiers', '^970..')
@hepnames.over('external_system_identifiers', '^970..')
@jobs.over('external_system_identifiers', '^970..')
def external_system_identifiers(self, key, value):
    """Populate the ``external_system_identifiers`` key.

    Also populates the ``new_record`` key through side effects.
    """
    external_system_identiers = self.get('external_system_identiers', [])
    new_record = self.get('new_record', {})

    values = force_force_list(value)
    for value in values:
        ids = force_force_list(value.get('a'))
        for id_ in ids:
            external_system_identiers.append({
                'schema': 'SPIRES',
                'value': id_,
            })

        new_recid = force_single_element(value.get('d', ''))
        if new_recid:
            new_record = get_record_ref(new_recid)

    self['new_record'] = new_record
    return external_system_identiers


@hep2marc.over('970', '^new_record$')
@hepnames2marc.over('970', '^new_record$')
def new_record2marc(self, key, value):
    return {'d': get_recid_from_ref(value)}


@conferences.over('collections', '^980..')
@institutions.over('collections', '^980..')
@experiments.over('collections', '^980..')
@journals.over('collections', '^980..')
@hepnames.over('collections', '^980..')
@jobs.over('collections', '^980..')
def collections(self, key, value):
    def _get_collection(value):
        return {
            'primary': force_single_element(value.get('a')),
            'secondary': force_force_list(value.get('b')),
        }

    def _is_deleted(value):
        return value and value.lower() == 'deleted'

    collections = self.get('collections', [])

    values = force_force_list(value)
    for value in values:
        if _is_deleted(value.get('c')):
            self['deleted'] = True

        collections.append(_get_collection(value))

    return collections


@hepnames2marc.over('980', '^collections$')
@utils.for_each_value
def collections2marc(self, key, value):
    return {
        'a': value.get('primary'),
        'b': value.get('secondary'),
    }


@hepnames2marc.over('980', '^deleted$')
@utils.for_each_value
def deleted2marc(self, key, value):
    if value:
        return {'c': 'DELETED'}


@hep.over('deleted_records', '^981..')
@conferences.over('deleted_records', '^981..')
@institutions.over('deleted_records', '^981..')
@experiments.over('deleted_records', '^981..')
@journals.over('deleted_records', '^981..')
@hepnames.over('deleted_records', '^981..')
@jobs.over('deleted_records', '^981..')
@utils.for_each_value
@utils.ignore_value
def deleted_records(self, key, value):
    return get_record_ref(value.get('a'))


@hep2marc.over('981', 'deleted_records')
@hepnames2marc.over('981', 'deleted_records')
@utils.for_each_value
def deleted_records2marc(self, key, value):
    return {'a': get_recid_from_ref(value)}


@hep.over('fft', '^FFT..')
@conferences.over('fft', '^FFT..')
@institutions.over('fft', '^FFT..')
@experiments.over('fft', '^FFT..')
@journals.over('fft', '^FFT..')
@utils.for_each_value
def fft(self, key, value):
    return {
        'url': value.get('a'),
        'docfile_type': value.get('t'),
        'flag': value.get('o'),
        'description': value.get('d'),
        'filename': value.get('n'),
        'filetype': value.get('f'),
    }


@hep2marc.over('FFT', 'fft')
@utils.for_each_value
def fft2marc(self, key, value):
    return {
        'a': value.get('url'),
        't': value.get('docfile_type'),
        'o': value.get('flag'),
        'd': value.get('description'),
        'n': value.get('filename'),
        'f': value.get('filetype'),
    }


@conferences.over('inspire_categories', '^65017')
@experiments.over('inspire_categories', '^65017')
@hep.over('inspire_categories', '^650[1_][_7]')
@hepnames.over('inspire_categories', '^65017')
@institutions.over('inspire_categories', '^65017')
@jobs.over('inspire_categories', '^65017')
@utils.for_each_value
def inspire_categories(self, key, value):
    schema = load_schema('elements/inspire_field')
    possible_sources = schema['properties']['source']['enum']

    _terms = force_force_list(value.get('a'))
    source = value.get('9')

    if source not in possible_sources:
        if source == 'automatically added based on DCC, PPF, DK':
            source = 'curator'
        elif source == 'submitter':
            source = 'user'
        else:
            source = 'undefined'

    self.setdefault('inspire_categories', [])
    if _terms:
        for _term in _terms:
            term = classify_field(_term)
            if term:
                inspire_category = {
                    'term': term,
                    'source': source,
                }
                self['inspire_categories'].append(inspire_category)


@conferences.over('urls', '^8564')
@experiments.over('urls', '^8564')
@hep.over('urls', '^856.[10_28]')
@hepnames.over('urls', '^856.[10_28]')
@institutions.over('urls', '^856.[10_28]')
@jobs.over('urls', '^856.[10_28]')
@journals.over('urls', '^856.[10_28]')
@utils.for_each_value
def urls(self, key, value):
    self.setdefault('urls', [])

    description = value.get('y')
    if isinstance(description, (list, tuple)):
        description = description[0]

    _urls = force_force_list(value.get('u'))

    if _urls:
        for _url in _urls:
            self['urls'].append({
                'description': description,
                'value': _url,
            })
