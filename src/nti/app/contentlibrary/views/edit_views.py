#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import time
import uuid

from zope import component

from pyramid import httpexceptions as hexc

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.contentlibrary import MessageFactory as _

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
from nti.contentlibrary.interfaces import IEditableContentUnit
from nti.contentlibrary.interfaces import IEditableContentPackage
from nti.contentlibrary.interfaces import IEditableContentPackageLibrary

from nti.coremetadata.interfaces import SYSTEM_USER_NAME

from nti.dataserver import authorization as nauth

from nti.dublincore.interfaces import IDCOptionalDescriptiveProperties

from nti.externalization.interfaces import StandardExternalFields

from nti.ntiids.ntiids import make_ntiid
from nti.ntiids.ntiids import get_provider
from nti.ntiids.ntiids import get_specific
from nti.ntiids.ntiids import make_specific_safe

from nti.property.property import Lazy

from nti.zodb.containers import time_to_64bit_int

HTML = u'HTML'
RST_MIMETYPE = u'text/x-rst'
MIME_TYPE = StandardExternalFields.MIMETYPE


class ContentPackageMixin(object):

    ALLOWED_KEYS = tuple(IDCOptionalDescriptiveProperties.names()) + \
        ('icon', 'thumbnail', 'data', 'content', MIME_TYPE)

    @Lazy
    def _extra(self):
        return str(uuid.uuid4()).split('-')[0].upper()

    def _clean_input(self, ext_obj):
        for name in list(ext_obj.keys()):
            if name not in self.ALLOWED_KEYS:
                ext_obj.pop(name, None)
        return ext_obj

    def _get_content(self, ext_obj):
        return ext_obj.get('data') or ext_obj.get('content')

    def _get_source(self, request=None):
        request = self.request if not request else request
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

    @Lazy
    def _libray(self):
        library = component.queryUtility(IEditableContentPackageLibrary)
        if library is None:
            raise_json_error(self.request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 u'message': _("Library not available."),
                                 u'code': 'LibraryNotAvailable',
                             },
                             None)
        return library

    @classmethod
    def make_pacakge_ntiid(cls, provider=None, base=None, extra=None):
        creator = SYSTEM_USER_NAME
        current_time = time_to_64bit_int(time.time())
        provider = provider \
                or (get_provider(base) or 'NTI' if base else 'NTI')

        specific_base = get_specific(base) if base else None
        if specific_base:
            specific_base += '.%s.%s' % (creator, current_time)
        else:
            specific_base = '%s.%s' % (creator, current_time)

        if extra:
            specific_base = specific_base + ".%s" % extra
        specific = make_specific_safe(specific_base)

        ntiid = make_ntiid(nttype=HTML,
                           base=base,
                           provider=provider,
                           specific=specific)
        return ntiid


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
        result = super(LibraryPostView, self).readInput(self, value=value)
        return self._clean_input(result)

    def _do_call(self):
        library = self._libray
        externalValue = self.readInput()
        ntiid = self.make_pacakge_ntiid(extra=self._extra)
        package = self.readCreateUpdateContentObject(self.remoteUser,
                                                     search_owner=False,
                                                     externalValue=externalValue)
        package.ntiid = ntiid
        contentType = RST_MIMETYPE
        content = self._get_content(externalValue)
        if not content:
            source = self._get_source(self.request)
            if source is not None:
                content = source.read()
                contentType = source.contentType or RST_MIMETYPE
        if content:
            self._validate(content, contentType)
            package.write_contents(content, contentType)
        library.add(package, event=False)
        self.request.response.status_int = 201
        return package
    
@view_config(context=IEditableContentUnit)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='PUT',
               permission=nauth.ACT_CONTENT_EDIT)
class ContentUnitPutView(UGDPutView, ContentPackageMixin):

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
