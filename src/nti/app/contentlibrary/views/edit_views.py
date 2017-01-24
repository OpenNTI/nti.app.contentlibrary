#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

# import six

from zope import component
# from zope import interface
# from zope import lifecycleevent

from pyramid import httpexceptions as hexc

from pyramid.view import view_config
from pyramid.view import view_defaults

# from nti.app.contentlibrary import MessageFactory as _

from nti.app.base.abstract_views import get_all_sources

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.error import raise_json_error

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.contentlibrary.views import LibraryPathAdapter

from nti.app.publishing import VIEW_PUBLISH
from nti.app.publishing import VIEW_UNPUBLISH

from nti.appserver.ugd_edit_views import UGDPutView
from nti.appserver.ugd_edit_views import UGDDeleteView

from nti.contentlibrary.interfaces import IContentValidator
from nti.contentlibrary.interfaces import IEditableContentPackage

from nti.dataserver import authorization as nauth

from nti.dublincore.interfaces import IDCOptionalDescriptiveProperties

HTML = u'HTML'
RST_MIMETYPE = u'text/x-rst'


class ContentPackageMixin(object):

    ALLOWED_KEYS = tuple(IDCOptionalDescriptiveProperties.names()) + \
        ('icon', 'thumbnail', 'data', 'content')

    def _clean_input(self, ext_obj):
        for name in list(ext_obj.keys()):
            if name not in self.ALLOWED_KEYS:
                ext_obj.pop(name, None)
        return ext_obj

    def _get_source(self, request):
        sources = get_all_sources(request, RST_MIMETYPE)
        if sources:
            if len(sources) == 1:
                return iter(sources.values()).next()
            return sources.get('data') \
                or sources.get('content')
        return None

    def _validate(self, content, contentType=RST_MIMETYPE):
        validator = component.queryUtility(IContentValidator,
                                           name=contentType)
        if validator is None:
            raise_json_error(self.request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                u'message': _("Cannot find content validator."),
                                u'code': 'CannotFindContentValidator',
                             },
                             None)
        validator.validate(content)


@view_config(context=LibraryPathAdapter)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='GET',
               permission=nauth.ACT_CONTENT_EDIT)
class LibraryPostView(AbstractAuthenticatedView,
                      ModeledContentUploadRequestUtilsMixin,
                      ContentPackageMixin):

    content_predicate = IEditableContentPackage

    def readInput(self, value=None):
        result = ModeledContentUploadRequestUtilsMixin.readInput(
            self, value=value)
        return self._clean_input(result)

    def _do_call(self):
        pass


@view_config(context=IEditableContentPackage)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='PUT',
               permission=nauth.ACT_CONTENT_EDIT)
class ContentPackagePutView(UGDPutView, ContentPackageMixin):

    def readInput(self, value=None):
        result = UGDPutView.readInput(self, value=value)
        return self._clean_input(result)


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
