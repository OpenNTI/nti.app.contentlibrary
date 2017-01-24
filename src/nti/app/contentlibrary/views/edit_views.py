#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

# import six

# from zope import component
# from zope import interface
# from zope import lifecycleevent

# from pyramid import httpexceptions as hexc

from pyramid.view import view_config
from pyramid.view import view_defaults

# from nti.app.contentlibrary import MessageFactory as _

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.contentlibrary.views import LibraryPathAdapter

from nti.app.publishing import VIEW_PUBLISH
from nti.app.publishing import VIEW_UNPUBLISH

from nti.appserver.ugd_edit_views import UGDPutView
from nti.appserver.ugd_edit_views import UGDPostView
from nti.appserver.ugd_edit_views import UGDDeleteView

from nti.contentlibrary.interfaces import IEditableContentPackage

from nti.dataserver import authorization as nauth

HTML = u'HTML'
RST_MIMETYPE = u'text/x-rst'

@view_config(context=LibraryPathAdapter)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='GET',
               permission=nauth.ACT_CONTENT_EDIT)
class LibraryPostView(AbstractAuthenticatedView):

    def __call__(self):
        pass


@view_config(context=IEditableContentPackage)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='POST',
               permission=nauth.ACT_CONTENT_EDIT)
class ContentPackagePostView(UGDPostView):
    pass


@view_config(context=IEditableContentPackage)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='PUT',
               permission=nauth.ACT_CONTENT_EDIT)
class ContentPackagePutView(UGDPutView):
    pass


@view_config(context=IEditableContentPackage)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='DELETE',
               permission=nauth.ACT_CONTENT_EDIT)
class ContentPackageDeleteView(UGDDeleteView):
    pass


@view_config(context=IEditableContentPackage)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='POST',
               name=VIEW_PUBLISH,
               permission=nauth.ACT_CONTENT_EDIT)
class ContentPackagePublishView(AbstractAuthenticatedView):
    pass


@view_config(context=IEditableContentPackage)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='POST',
               name=VIEW_UNPUBLISH,
               permission=nauth.ACT_CONTENT_EDIT)
class ContentPackageUnpublishView(AbstractAuthenticatedView):
    pass
