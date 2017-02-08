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

from requests.structures import CaseInsensitiveDict

from zope import component
from zope import lifecycleevent

from zope.file.download import getHeaders

from ZODB.interfaces import IConnection

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

from nti.common.string import is_true

from nti.contentlibrary.interfaces import IContentValidator
from nti.contentlibrary.interfaces import IEditableContentUnit
from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.interfaces import IRenderableContentUnit
from nti.contentlibrary.interfaces import IEditableContentPackage
from nti.contentlibrary.interfaces import resolve_content_unit_associations

from nti.coremetadata.interfaces import SYSTEM_USER_NAME 

from nti.coremetadata.interfaces import IRecordable

from nti.dataserver import authorization as nauth

from nti.externalization.internalization import notify_modified
from nti.externalization.externalization import to_external_object
from nti.externalization.externalization import StandardExternalFields

from nti.links.links import Link

from nti.ntiids.ntiids import make_ntiid
from nti.ntiids.ntiids import get_provider
from nti.ntiids.ntiids import get_specific
from nti.ntiids.ntiids import make_specific_safe

from nti.property.property import Lazy

from nti.recorder.interfaces import TRX_TYPE_CREATE

from nti.recorder.utils import record_transaction

from nti.zodb.containers import time_to_64bit_int

HTML = u'HTML'
RST_MIMETYPE = b'text/x-rst'

CLASS = StandardExternalFields.CLASS
LINKS = StandardExternalFields.LINKS
MIME_TYPE = StandardExternalFields.MIMETYPE

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
                or sources.get('content') \
                or sources.get('contents')
        return None

    def _validate(self, content, contentType=RST_MIMETYPE):
        validator = component.queryUtility(IContentValidator,
                                           name=contentType)
        if validator is not None:
            validator.validate(content)

    def _check_content(self, ext_obj=None):
        contentType = None
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
        library = component.queryUtility(IContentPackageLibrary)
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
        # add to connection
        IConnection(library).add(package)
        # set ntiid according to package class
        self._set_ntiid(package)
        # read content
        contents, contentType = self._check_content(externalValue)
        if contents:
            package.contents = contents
        if contentType and contents:
            package.contentType = contentType
        # set creator
        package.creator = self.remoteUser.username
        # add to library
        lifecycleevent.created(package)
        library.add(package, event=False)
        # record trax
        if IRecordable.providedBy(package):
            record_transaction(package, type_=TRX_TYPE_CREATE)
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
        if contents:
            contentObject.contents = contents
        if contentType:
            contentObject.contentType = contentType
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
            response.headers[str(k)] = str(v)
        response.body = contents
        return response


@view_config(context=IEditableContentPackage)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='DELETE',
               permission=nauth.ACT_CONTENT_EDIT)
class ContentPackageDeleteView(AbstractAuthenticatedView, ContentPackageMixin):

    CONFIRM_CODE = 'EditableContentPackageDelete'
    CONFIRM_MSG = _('This content has associations. Are you sure you want to delete?')
    
    def _do_delete_object(self, theObject, event=True):
        library = self._libray
        library.remove(theObject, event=event)
        return theObject

    def _ntiids(self, associations):
        for x in associations or ():
            try:
                yield x.ntiid
            except AttributeError:
                pass

    def _raise_conflict_error(self, code, message, associations):
        ntiids = [x.ntiid for x in self._ntiids(associations)]
        logger.warn('Attempting to delete content package in (%s) (%s)',
                    self.context.ntiid,
                    ntiids)
        params = dict(self.request.params)
        params['force'] = True
        links = (
            Link(self.request.path, rel='confirm',
                 params=params, method='DELETE'),
        )
        raise_json_error(self.request,
                         hexc.HTTPConflict,
                         {
                            u'code': code,
                            u'message': message,
                            CLASS: 'DestructiveChallenge',
                            LINKS: to_external_object(links),
                            MIME_TYPE: 'application/vnd.nextthought.destructivechallenge'
                         },
                         None)

    def __call__(self):
        associations = resolve_content_unit_associations(self.context)
        params = CaseInsensitiveDict(self.request.params)
        force = is_true(params.get('force'))
        if not associations or force:
            self._do_delete_object(self.context,
                                   self.context.is_published())
        else:
            self._raise_conflict_error(self.CONFIRM_CODE,
                                       self.CONFIRM_MSG,
                                       associations)
        return self.context
