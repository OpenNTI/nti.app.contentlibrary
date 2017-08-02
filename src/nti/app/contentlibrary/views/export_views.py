#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from requests.structures import CaseInsensitiveDict

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.contentlibrary import VIEW_EXPORT

from nti.common.string import is_true

from nti.contentlibrary.interfaces import IEditableContentPackage

from nti.contentlibrary.utils import export_content_package

from nti.dataserver.authorization import ACT_CONTENT_EDIT


@view_config(permission=ACT_CONTENT_EDIT)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='GET',
               context=IEditableContentPackage,
               name=VIEW_EXPORT)
class ExportContentPackageView(AbstractAuthenticatedView):

    def __call__(self):
        params = CaseInsensitiveDict(self.request.params)
        backup = is_true(params.get('backup'))
        salt = params.get('salt') or ''
        result = export_content_package(self.context, backup, salt)
        return result
