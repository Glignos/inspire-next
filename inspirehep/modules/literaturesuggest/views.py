# -*- coding: utf-8 -*-
#
# This file is part of INSPIRE.
# Copyright (C) 2014-2017 CERN.
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
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as an Intergovernmental Organization
# or submit itself to any jurisdiction.

"""INSPIRE Literature suggestion blueprint."""

from __future__ import absolute_import, division, print_function

import copy
import os
import re

import requests

from flask import (
    abort,
    Blueprint,
    redirect,
    request,
    render_template,
    url_for,
    jsonify,
    current_app,
)
from flask_login import current_user, login_required
from flask_babelex import gettext as _
from flask_breadcrumbs import register_breadcrumb

from werkzeug.datastructures import MultiDict

from inspirehep.modules.forms.form import DataExporter

from invenio_db import db
from invenio_workflows import workflow_object_class, start

from .forms import LiteratureForm
from .normalizers import normalize_formdata
from .tasks import formdata_to_model


blueprint = Blueprint('inspirehep_literature_suggest',
                      __name__,
                      url_prefix='/literature',
                      template_folder='templates',
                      static_folder='static')


def get_inspire_url(data):
    """ Generate url for the user to go back to INSPIRE. """
    url = ""
    if "bai" in data and data["bai"]:
        url = "http://inspirehep.net/author/profile/" + data["bai"]
    elif "control_number" in data and data["control_number"]:
        url = "http://inspirehep.net/record/" + str(data["control_number"])
    else:
        url = "http://inspirehep.net/hepnames"
    return url


def convert_for_form(data):
    """
    Convert author data model form field names.

    FIXME This might be better in a different file and as a dojson conversion
    """

    if 'abstracts' in data:
        abstracts = data.get('abstracts', [])
        data['abstract'] = abstracts[0]['value']
    if 'authors' in data:
        authors = data.get('authors', [])
        i=0
        for author in authors:
            new_author = {}
            if 'affiliations' in author:
                new_author['affiliation'] = author['affiliations'][0]['value']
            if 'full_name' in author:
                new_author['name'] = author['full_name']
            data['authors'][i] = new_author
    if 'document_type' in data:
        data['type_of_doc'] = data['document_type'][0]
    if 'dois' in data:
        data['doi'] = dois[0]['value']
    if 'inspire_categories' in data:
        categories = data.get('inspire_categories', [])
        new_categories = []
        for category in categories:
            new_categories.append(category['term'])
        data['subject'] = new_categories






    if "name" in data:
        data["full_name"] = data["name"].get("value")
        try:
            data["given_names"] = data["name"].get(
                "value").split(",")[1].strip()
        except IndexError:
            data["given_names"] = ""
        data["family_name"] = data["name"].get("value").split(",")[0].strip()
        data["display_name"] = data["name"].get("preferred_name")
    if "native_name" in data:
        data["native_name"] = data["native_name"][0]
    if "urls" in data:
        data["websites"] = []
        for url in data["urls"]:
            if not url.get('description'):
                data["websites"].append({"webpage": url["value"]})
            else:
                if url["description"].lower() == "twitter":
                    data["twitter_url"] = url["value"]
                elif url["description"].lower() == "blog":
                    data["blog_url"] = url["value"]
                elif url["description"].lower() == "linkedin":
                    data["linkedin_url"] = url["value"]
        del data["urls"]
    if 'arxiv_categories' in data:
        data['research_field'] = data['arxiv_categories']
    if "positions" in data:
        data["institution_history"] = []
        data["public_emails"] = []
        for position in data["positions"]:
            if not any(
                [
                    key in position for key in ('institution', '_rank',
                                                'start_year', 'end_year')
                ]
            ):
                if 'emails' in position:
                    for email in position['emails']:
                        data["public_emails"].append(
                            {
                                'email': email,
                                'original_email': email
                            }
                        )
                continue
            pos = {}
            pos["name"] = position.get("institution", {}).get("name")
            rank = position.get("_rank", "")
            if rank:
                pos["rank"] = rank
            set_int_or_skip(pos, "start_year", position.get("start_date", ""))
            set_int_or_skip(pos, "end_year", position.get("end_date", ""))
            pos["current"] = True if position.get("current") else False
            pos["old_emails"] = position.get("old_emails", [])
            if position.get("emails"):
                pos["emails"] = position['emails']
                for email in position['emails']:
                    data["public_emails"].append(
                        {
                            'email': email,
                            'original_email': email
                        }
                    )
            data["institution_history"].append(pos)
        data["institution_history"].reverse()
    if 'advisors' in data:
        advisors = data['advisors']
        data['advisors'] = []
        for advisor in advisors:
            adv = {}
            adv["name"] = advisor.get("name", "")
            adv["degree_type"] = advisor.get("degree_type", "")
            data["advisors"].append(adv)
    if "ids" in data:
        for id in data["ids"]:
            try:
                if id["schema"] == "ORCID":
                    data["orcid"] = id["value"]
                elif id["schema"] == "INSPIRE BAI":
                    data["bai"] = id["value"]
                elif id["schema"] == "INSPIRE ID":
                    data["inspireid"] = id["value"]
            except KeyError:
                # Protect against cases when there is no value in metadata
                pass


@blueprint.route('/new', methods=['GET'])
@login_required
def create():
    """View for INSPIRE suggestion create form."""
    form = LiteratureForm()
    ctx = {
        "action": url_for('.submit'),
        "name": "submitForm",
        "id": "submitForm",
    }

    return render_template(
        'literaturesuggest/forms/suggest.html',
        form=form,
        **ctx
    )


@blueprint.route('/new/submit', methods=['POST'])
def submit():
    """Get form data and start workflow."""
    form = LiteratureForm(formdata=request.form)
    visitor = DataExporter()
    visitor.visit(form)

    workflow_object = workflow_object_class.create(
        data={},
        id_user=current_user.get_id(),
        data_type="hep"
    )
    workflow_object.extra_data['formdata'] = copy.deepcopy(visitor.data)
    visitor.data = normalize_formdata(workflow_object, visitor.data)
    workflow_object.data = formdata_to_model(workflow_object, visitor.data)
    workflow_object.save()
    db.session.commit()

    # Start workflow. delayed=True will execute the workflow in the
    # background using, for example, Celery.
    start.delay("article", object_id=workflow_object.id)

    return redirect(url_for('.success'))


@blueprint.route('/new/success', methods=['GET'])
def success():
    """Render success template for the user."""
    return render_template('literaturesuggest/forms/suggest_success.html')


@blueprint.route('/new/validate', methods=['POST'])
def validate():
    """Validate form and return validation errors.

    FIXME: move to forms module as a generic /validate where we can pass
    the for class to validate.
    """
    if request.method != 'POST':
        abort(400)
    data = request.json or MultiDict({})
    formdata = MultiDict(data or {})
    form = LiteratureForm(formdata=formdata)
    form.validate()

    result = {}
    changed_msgs = dict(
        (name, messages) for name, messages in form.messages.items()
        if name in formdata.keys()
    )
    result['messages'] = changed_msgs

    return jsonify(result)


@blueprint.route('/<int:recid>/update', methods=['GET'])
@register_breadcrumb(blueprint, '.update', _('Update hep information'))
@login_required
def update(recid):
    """View for INSPIRE hep update form."""
    from dojson.contrib.marc21.utils import create_record
    from inspirehep.dojson.hep import hep

    data = {}
    if recid:
        try:
            url = os.path.join(
                current_app.config["AUTHORS_UPDATE_BASE_URL"],
                "record", str(recid), "export", "xm")
            xml = requests.get(url)
            record_regex = re.compile(
                r"\<record\>.*\<\/record\>", re.MULTILINE + re.DOTALL)
            xml_content = record_regex.search(xml.content).group()
            data = hep.do(create_record(xml_content))  # .encode("utf-8")
            from remote_pdb import RemotePdb
            RemotePdb('0.0.0.0', 4444).set_trace()
            convert_for_form(data)
        except requests.exceptions.RequestException:
            pass
        data["control_number"] = recid
    else:
        return redirect(url_for("inspirehep_authors_holdingpen.new"))
    form = LiteratureForm(data=data, is_update=True)
    ctx = {
        "action": url_for('.submit'),
        "name": "submitForm",
        "id": "submitForm",
    }

    return render_template('literaturesuggest/forms/update_record.html', form=form, **ctx)


@blueprint.route('/update/submit', methods=['POST'])
@login_required
def submitupdate():
    """Form action handler for INSPIRE author update form."""
    form = LiteratureForm(formdata=request.form, is_update=True)
    visitor = DataExporter()
    visitor.visit(form)

    workflow_object = workflow_object_class.create(
        data={},
        id_user=current_user.get_id(),
        data_type="hep"
    )

    workflow_object.extra_data['formdata'] = copy.deepcopy(visitor.data)
    workflow_object.extra_data['is-update'] = True
    workflow_object.data = formdata_to_model(workflow_object, visitor.data)
    workflow_object.save()
    db.session.commit()

    # Start workflow. delay will execute the workflow in the background
    start.delay("article", object_id=workflow_object.id)

    ctx = {
        "inspire_url": get_inspire_url(visitor.data)
    }

    return render_template('literaturesuggest/forms/update_success.html', **ctx)

