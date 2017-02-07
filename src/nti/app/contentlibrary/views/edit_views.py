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
import mimetypes

from zope import component

from zope.file.download import getHeaders

from pyramid import httpexceptions as hexc

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.base.abstract_views import get_all_sources

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.contentlibrary import MessageFactory as _

from nti.app.externalization.error import raise_json_error

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.contentlibrary.views import VIEW_CONTENTS
from nti.app.contentlibrary.views import LibraryPathAdapter

from nti.appserver.ugd_edit_views import UGDPutView

from nti.contentlibrary.interfaces import IContentValidator
from nti.contentlibrary.interfaces import IEditableContentUnit
from nti.contentlibrary.interfaces import IRenderableContentUnit
from nti.contentlibrary.interfaces import IEditableContentPackage
from nti.contentlibrary.interfaces import IEditableContentPackageLibrary
from nti.contentlibrary.interfaces import resolve_content_unit_associations

from nti.coremetadata.interfaces import SYSTEM_USER_NAME

from nti.dataserver import authorization as nauth

from nti.externalization.internalization import notify_modified

from nti.ntiids.ntiids import make_ntiid
from nti.ntiids.ntiids import get_provider
from nti.ntiids.ntiids import get_specific
from nti.ntiids.ntiids import make_specific_safe

from nti.property.property import Lazy

from nti.zodb.containers import time_to_64bit_int

HTML = u'HTML'
RST_MIMETYPE = b'text/x-rst'


class ContentPackageMixin(object):

    @Lazy
    def _extra(self):
        return str(uuid.uuid4()).split('-')[0].upper()

    @classmethod
    def _get_content(cls, ext_obj):
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
        if validator is not None:
            validator.validate(content)

    def _check_content(self, ext_obj=None):
        contentType = RST_MIMETYPE
        content = self._get_content(ext_obj) if ext_obj else None
        if not content:
            source = self._get_source(self.request)
            if source is not None:
                content = source.read()
                contentType = source.contentType or RST_MIMETYPE
        if content:
            self._validate(content, contentType)
        return content, contentType

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
               request_method='POST',
               permission=nauth.ACT_CONTENT_EDIT)
class LibraryPostView(AbstractAuthenticatedView,
                      ModeledContentUploadRequestUtilsMixin,
                      ContentPackageMixin):

    content_predicate = IEditableContentPackage

    def _set_ntiid(self, context):
        if not IRenderableContentUnit.providedBy(context):
            ntiid = self.make_pacakge_ntiid(extra=self._extra)
            context.ntiid = ntiid

    def _do_call(self):
        library = self._libray
        externalValue = self.readInput()
        package = self.readCreateUpdateContentObject(self.remoteUser,
                                                     search_owner=False,
                                                     externalValue=externalValue)
       
        self._set_ntiid(package)
        contents, contentType = self._check_content(externalValue)
        package.contents = contents
        package.contentType = contentType
        library.add(package, event=False)
        self.request.response.status_int = 201
        return package


@view_config(context=IEditableContentUnit)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='PUT',
               permission=nauth.ACT_CONTENT_EDIT)
class ContentUnitPutView(UGDPutView, ContentPackageMixin):

    def updateContentObject(self, contentObject, externalValue, set_id=False,
                            notify=True, pre_hook=None, object_hook=None):
        result = UGDPutView.updateContentObject(self,
                                                contentObject,
                                                externalValue,
                                                set_id=set_id,
                                                notify=notify,
                                                pre_hook=pre_hook,
                                                object_hook=object_hook)
        contents, contentType = self._check_content(externalValue)
        contentObject.contents = contents
        contentObject.contentType = contentType
        return result

    def __call__(self):
        result = UGDPutView.__call__(self)
        return result


@view_config(context=IEditableContentUnit)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='PUT',
               name=VIEW_CONTENTS,
               permission=nauth.ACT_CONTENT_EDIT)
class ContentUnitContentsPutView(AbstractAuthenticatedView, 
                                 ContentPackageMixin):

    def __call__(self):
        content, contentType = self._check_content()
        self.context.write_contents(content, contentType)
        notify_modified(self.context,
                        {
                            'contents': content,
                            'contentType': contentType
                        })
        return self.context


@view_config(context=IEditableContentPackage)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='GET',
               name=VIEW_CONTENTS,
               permission=nauth.ACT_CONTENT_EDIT)
class ContentPackageContentsGetView(AbstractAuthenticatedView,
                                    ContentPackageMixin):

    def __call__(self):
        response = self.request.response
        contents = self.context.contents or b''
        contentType = bytes(self.context.contentType or RST_MIMETYPE)
        ext = mimetypes.guess_extension(RST_MIMETYPE) or ".rst"
        downloadName = "contents%s" % ext
        headers = getHeaders(self.context,
                             contentType=contentType,
                             downloadName=downloadName,
                             contentLength=len(contents),
                             contentDisposition="attachment")
        for k, v in headers:
            response.setHeader(k, v)
        response.body = contents
        return response


@view_config(context=IEditableContentPackage)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='DELETE',
               permission=nauth.ACT_CONTENT_EDIT)
class ContentPackageDeleteView(AbstractAuthenticatedView, ContentPackageMixin):

    def _do_delete_object(self, theObject, event=False):
        library = self._libray
        library.remove(theObject, event=event)
        return theObject

    def __call__(self):
        if not self.context.is_published():
            self._do_delete_object(self.context, event=False)
        associations = resolve_content_unit_associations(self.context)
        if not associations:
            self._do_delete_object(self.context, event=True)
        return self.context
