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

from zope.intid.interfaces import IIntIds

from pyramid import httpexceptions as hexc

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.base.abstract_views import get_all_sources

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.contentlibrary import MessageFactory as _

from nti.app.externalization.error import raise_json_error

from nti.app.externalization.internalization import read_body_as_external_object

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.contentlibrary.model import ContentUnitContents

from nti.app.contentlibrary.views import VIEW_CONTENTS
from nti.app.contentlibrary.views import VIEW_PUBLISH_CONTENTS

from nti.app.contentlibrary.views import LibraryPathAdapter

from nti.appserver.ugd_edit_views import UGDPutView

from nti.base._compat import bytes_

from nti.common.string import is_true

from nti.contentlibrary.interfaces import IEditableContentUnit
from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.interfaces import IRenderableContentUnit
from nti.contentlibrary.interfaces import IEditableContentPackage
from nti.contentlibrary.interfaces import resolve_content_unit_associations

from nti.contentlibrary.library import register_content_units

from nti.contentlibrary.utils import get_published_contents

from nti.contenttypes.presentation.interfaces import IPresentationAsset

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
    def _get_contents(cls, ext_obj):
        return ext_obj.get('contents')

    def _get_contents_object(self, contents):
        result = ContentUnitContents()
        result.contents = contents
        result.ntiid = self.context.ntiid
        result.contentType = bytes_(self.context.contentType or RST_MIMETYPE)
        return result

    @classmethod
    def _get_content_type(cls, ext_obj):
        return ext_obj.get('contentType')

    def _get_source(self, request=None):
        request = self.request if not request else request
        sources = get_all_sources(request, RST_MIMETYPE)
        if sources:
            if len(sources) == 1:
                return iter(sources.values()).next()
            return self._get_contents(sources)
        return None

    def _validate_version(self):
        """
        If given a content version, validate that it matches what
        we have. Otherwise, it indicates the PUT might be trampling
        over another user's edits.
        """
        params = CaseInsensitiveDict( self.request.params )
        version = params.get( 'version' )
        # XXX: We dont want a 'force' link right?
        if version and version != self.context.version:
            raise_json_error(
                self.request,
                hexc.HTTPConflict,
                {
                    u'message': _('The content version does not match. Please refresh.'),
                    u'code': 'ContentVersionConflictError'
                },
                None)

    def _validate(self):
        self._validate_version()

    def _check_content(self, ext_obj=None):
        content = self._get_contents(ext_obj) if ext_obj else None
        contentType = self._get_content_type(ext_obj) if ext_obj else None
        if content is None:
            source = self._get_source(self.request)
            if source is not None:
                content = source.read()
                contentType = source.contentType or RST_MIMETYPE
        if content is not None:
            content = bytes_(content)
            contentType = bytes_(contentType or RST_MIMETYPE)
            self._validate()
        return content, contentType

    @Lazy
    def _library(self):
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
    def make_package_ntiid(cls, provider=None, base=None, extra=None):
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
            ntiid = self.make_package_ntiid(extra=self._extra)
        else:
            # Use predictable ntiids for renderable content packages
            intids = component.getUtility(IIntIds)
            specific= '%s.0' % intids.getId(context)
            ntiid = make_ntiid(nttype=HTML,
                               provider='NTI',
                               specific=specific)
        context.ntiid = ntiid

    def _do_call(self):
        library = self._library
        externalValue = self.readInput()
        package, _, externalValue = \
            self.performReadCreateUpdateContentObject(user=self.remoteUser,
                                                      search_owner=False,
                                                      externalValue=externalValue,
                                                      deepCopy=True)
        # Register early and set the ntiid before adding to the library
        # (this adds to the connection).
        register_content_units(library, package)
        self._set_ntiid(package)
        # read content
        contents, contentType = self._check_content(externalValue)
        if contents is not None:
            package.contents = contents
            if contentType is not None:
                package.contentType = contentType
        # set creator
        package.creator = self.remoteUser.username
        # add to library
        lifecycleevent.created(package)
        library.add(package, event=False)
        lifecycleevent.added(package, library)
        # record trax
        if IRecordable.providedBy(package):
            record_transaction(package, type_=TRX_TYPE_CREATE)
        self.request.response.status_int = 201
        logger.info('Created new content package (%s)', package.ntiid)
        return package


@view_config(context=IEditableContentUnit)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='PUT',
               permission=nauth.ACT_CONTENT_EDIT)
class ContentUnitPutView(UGDPutView, ContentPackageMixin):

    def updateContentObject(self, contentObject, externalValue, set_id=False,
                            notify=True, pre_hook=None, object_hook=None):
        UGDPutView.updateContentObject(self,
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
        result = self.context
        if contents:
            result = to_external_object(result)
            result['contents'] = self._get_contents_object(contents)
        return result


@view_config(context=IEditableContentUnit)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='PUT',
               name=VIEW_CONTENTS,
               permission=nauth.ACT_CONTENT_EDIT)
class ContentUnitContentsPutView(AbstractAuthenticatedView,
                                 ContentPackageMixin):

    def readInput(self):
        data = read_body_as_external_object(self.request)
        return CaseInsensitiveDict(data or {})

    def __call__(self):
        data = self.readInput()
        contents, contentType = self._check_content(data)
        if contents and contentType:
            self.context.write_contents(contents, contentType)
            notify_modified(self.context,
                            {
                                'contents': contents,
                                'contentType': contentType,
                                'version': self.context.version
                            })
        result = self.context
        if contents:
            result = to_external_object(self.context)
            result['contents'] = self._get_contents_object(contents)
        return result


@view_config(context=IEditableContentPackage)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='GET',
               name=VIEW_CONTENTS,
               permission=nauth.ACT_CONTENT_EDIT)
class ContentPackageContentsGetView(AbstractAuthenticatedView,
                                    ContentPackageMixin):

    def _get_contents(self):
        return self.context.contents or b''

    def as_attachment(self):
        response = self.request.response
        contents = self._get_contents()
        contentType = bytes_(self.context.contentType or RST_MIMETYPE)
        ext = mimetypes.guess_extension(contentType) or ".rst"
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

    def __call__(self):
        params = CaseInsensitiveDict(self.request.params)
        attachment = is_true(params.get('attachment') or 'False')
        if attachment:
            return self.as_attachment()
        contents = self._get_contents()
        return self._get_contents_object(contents)


@view_config(context=IEditableContentPackage)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='GET',
               name=VIEW_PUBLISH_CONTENTS,
               permission=nauth.ACT_CONTENT_EDIT)
class PackagePublishedContentsGetView(ContentPackageContentsGetView):
    """
    A view to fetch the contents of an `IEditableContentPackage` as-of
    the most recent publish.
    """

    def _get_contents(self):
        result = get_published_contents(self.context)

        if result is None:
            logger.warn('No publish contents found (%s)', self.context)
            raise hexc.HTTPNotFound(_('No publish contents found'))
        return result


@view_config(context=IEditableContentPackage)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='DELETE',
               permission=nauth.ACT_CONTENT_EDIT)
class ContentPackageDeleteView(AbstractAuthenticatedView, ContentPackageMixin):

    LESSON_CONFIRM_CODE = 'EditableContentPackageInLessonDelete'
    LESSON_CONFIRM_MSG = _(
        'This content is available in lessons. Are you sure you want to delete?')

    CONFIRM_CODE = 'EditableContentPackageDelete'
    CONFIRM_MSG = _('Are you sure you want to delete?')

    def _do_delete_object(self, theObject, event=True):
        library = self._library
        library.remove(theObject, event=event)
        return theObject

    def _ntiids(self, associations):
        for x in associations or ():
            try:
                yield x.ntiid
            except AttributeError:
                pass

    def _raise_conflict_error(self, code, message, associations):
        ntiids = [x for x in self._ntiids(associations)]
        logger.warn('Attempting to delete content package (%s) (%s)',
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

    def _get_lesson_associations(self):
        associations = resolve_content_unit_associations(self.context)
        return [x for x in associations or () if IPresentationAsset.providedBy(x)]

    def __call__(self):
        associations = resolve_content_unit_associations(self.context)
        lesson_associations = [x for x in associations or ()
                               if IPresentationAsset.providedBy(x)]
        params = CaseInsensitiveDict(self.request.params)
        force = is_true(params.get('force'))
        if force:
            self._do_delete_object(self.context)
        elif lesson_associations:
            self._raise_conflict_error(self.LESSON_CONFIRM_CODE,
                                       self.LESSON_CONFIRM_MSG,
                                       associations)
        else:
            self._raise_conflict_error(self.CONFIRM_CODE,
                                       self.CONFIRM_MSG,
                                       associations)
        result = hexc.HTTPNoContent()
        result.last_modified = time.time()
        return result
