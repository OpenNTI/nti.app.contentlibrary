#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import six
import time
import uuid
import mimetypes

from requests.structures import CaseInsensitiveDict

from zope import component
from zope import lifecycleevent

from zope.cachedescriptors.property import Lazy

from zope.component.hooks import site as current_site

from zope.file.download import getHeaders

from pyramid import httpexceptions as hexc

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.base.abstract_views import get_all_sources

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.contentfile.view_mixins import is_oid_external_link
from nti.app.contentfile.view_mixins import get_file_from_oid_external_link

from nti.app.contentfolder.utils import is_cf_io_href
from nti.app.contentfolder.utils import get_file_from_cf_io_url

from nti.app.contentlibrary import MessageFactory as _

from nti.app.contentlibrary.hostpolicy import get_site_provider

from nti.app.contentlibrary.model import ContentUnitContents

from nti.app.contentlibrary.views import VIEW_CONTENTS
from nti.app.contentlibrary.views import VIEW_PUBLISH_CONTENTS
from nti.app.contentlibrary.views import VIEW_PACKAGE_WITH_CONTENTS

from nti.app.contentlibrary.views import LibraryPathAdapter

from nti.app.externalization.error import raise_json_error

from nti.app.externalization.internalization import read_body_as_external_object

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.appserver.ugd_edit_views import UGDPutView

from nti.base._compat import bytes_

from nti.common.string import is_true

from nti.contentfile.interfaces import IContentBaseFile

from nti.contentlibrary import RST_MIMETYPE

from nti.contentlibrary.interfaces import IEditableContentUnit
from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.interfaces import IEditableContentPackage
from nti.contentlibrary.interfaces import resolve_content_unit_associations

from nti.contentlibrary.library import register_content_units

from nti.contentlibrary.utils import get_published_contents
from nti.contentlibrary.utils import make_content_package_ntiid

from nti.contenttypes.presentation.interfaces import IPresentationAsset

from nti.dataserver import authorization as nauth

from nti.externalization.internalization import notify_modified

from nti.externalization.externalization import to_external_object
from nti.externalization.externalization import StandardExternalFields

from nti.links.links import Link

from nti.recorder.interfaces import TRX_TYPE_CREATE

from nti.recorder.interfaces import IRecordable

from nti.recorder.utils import record_transaction

from nti.site.hostpolicy import get_host_site

from nti.site.interfaces import IHostPolicyFolder

from nti.traversal.traversal import find_interface

CLASS = StandardExternalFields.CLASS
LINKS = StandardExternalFields.LINKS
MIME_TYPE = StandardExternalFields.MIMETYPE


class ContentPackageMixin(object):

    @Lazy
    def _extra(self):
        return str(uuid.uuid4().get_time_low()).upper()

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

    def _get_version(self, ext_obj):
        params = CaseInsensitiveDict(self.request.params)
        return params.get('version') or ext_obj.get('version')

    def _get_overwrite_flag(self, ext_obj):
        params = CaseInsensitiveDict(self.request.params)
        return params.get('force') or ext_obj.get('force')

    def _validate_version(self, ext_obj):
        """
        If given a content version, validate that it matches what
        we have. Otherwise, it indicates the PUT might be trampling
        over another user's edits.
        """
        overwrite_flag = self._get_overwrite_flag(ext_obj)
        if is_true(overwrite_flag):
            logger.info("Overwriting content package edits (%s)",
                        self.context.ntiid)
            return
        version = self._get_version(ext_obj)
        if version is not None and version != self.context.version:
            # Provide links to overwrite (force flag) or refresh on conflict.
            links = []
            link = Link(self.request.path, rel=u'overwrite',
                        params={u'force': True}, method=u'PUT')
            links.append(link)
            link = Link(self.context, rel=u'refresh',
                        method=u'GET',
                        elements=(u'@@%s' % VIEW_PACKAGE_WITH_CONTENTS,))
            links.append(link)
            raise_json_error(
                self.request,
                hexc.HTTPConflict,
                {
                    CLASS: 'DestructiveChallenge',
                    'message': _(u'The contents have been changed while you were editing.'),
                    'code': 'ContentVersionConflictError',
                    LINKS: to_external_object(links),
                    MIME_TYPE: 'application/vnd.nextthought.destructivechallenge'
                },
                None)

    def _validate(self, ext_obj):
        self._validate_version(ext_obj)

    def _check_content(self, ext_obj=None):
        content = self._get_contents(ext_obj) if ext_obj else None
        contentType = self._get_content_type(ext_obj) if ext_obj else None
        if content is None:
            source = self._get_source(self.request)
            if source is not None:
                content = source.read()
                contentType = contentType or source.contentType or RST_MIMETYPE
        if content is not None:
            content = bytes_(content)
            contentType = contentType or RST_MIMETYPE
            self._validate(ext_obj)
        return content, bytes_(contentType or RST_MIMETYPE)

    def get_library(self, context=None):
        if context is None:
            library = component.queryUtility(IContentPackageLibrary)
        else:
            # If context is given, attempt to use the site the given context
            # is stored in. This is necessary to avoid data loss during sync.
            folder = find_interface(context, IHostPolicyFolder, strict=False)
            with current_site(get_host_site(folder.__name__)):
                library = component.queryUtility(IContentPackageLibrary)
        if library is None:
            raise_json_error(self.request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 'message': _(u"Library not available."),
                                 'code': 'LibraryNotAvailable',
                             },
                             None)
        return library

    def is_dataserver_asset(self, uri):
        return is_cf_io_href(uri) or is_oid_external_link(uri)

    def get_dataserver_asset(self, uri):
        if is_cf_io_href(uri):
            return get_file_from_cf_io_url(uri)
        return get_file_from_oid_external_link(uri)

    def associate(self, uri, context):
        if      isinstance(uri, six.string_types) \
            and self.is_dataserver_asset(uri):
            asset = self.get_dataserver_asset(uri)
            if IContentBaseFile.providedBy(asset):
                asset.add_association(context)
        
    def disassociate(self, uri, context):
        if      isinstance(uri, six.string_types) \
            and self.is_dataserver_asset(uri):
            asset = self.get_dataserver_asset(uri)
            if IContentBaseFile.providedBy(asset):
                asset.remove_association(context)
                        
    @classmethod
    def make_package_ntiid(cls, context, provider=None, base=None, extra=None):
        provider = provider or get_site_provider()
        return make_content_package_ntiid(context, provider, base, extra)


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
        context.ntiid = self.make_package_ntiid(context)

    def _do_call(self):
        library = self.get_library()
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
        self.associate(package.icon, package)
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
        # check for icon association
        icon = externalValue.get('icon')
        if icon:
            self.disassociate(contentObject.icon, contentObject)
        UGDPutView.updateContentObject(self,
                                       contentObject,
                                       externalValue,
                                       set_id=set_id,
                                       notify=notify,
                                       pre_hook=pre_hook,
                                       object_hook=object_hook)
        # associate icon
        if icon:
            self.associate(icon, contentObject)
        # check contents
        contents, contentType = self._check_content(externalValue)
        if contents is not None:
            contentObject.contents = contents
        if contentType:
            contentObject.contentType = contentType
        result = self.context
        if contents is not None:
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
        if contents is not None and contentType:
            version = self._get_version(data) or self.context.version
            self.context.write_contents(contents, contentType)
            notify_modified(self.context,
                            {
                                u'version': version,
                                u'contents': contents,
                                u'contentType': contentType,
                            })
        result = self.context
        if contents is not None:
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
               name=VIEW_PACKAGE_WITH_CONTENTS,
               permission=nauth.ACT_CONTENT_EDIT)
class ContentPackageWithContentsGetView(ContentPackageContentsGetView):
    """
    Convenience class to return the package with inlined contents.
    """

    def __call__(self):
        contents = super(ContentPackageWithContentsGetView, self).__call__()
        result = to_external_object(self.context)
        result['contents'] = contents
        return result


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
            raise hexc.HTTPNotFound(_(u'No publish contents found'))
        return result


@view_config(context=IEditableContentPackage)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='DELETE',
               permission=nauth.ACT_CONTENT_EDIT)
class ContentPackageDeleteView(AbstractAuthenticatedView, ContentPackageMixin):

    LESSON_CONFIRM_CODE = 'EditableContentPackageInLessonDelete'
    LESSON_CONFIRM_MSG = _(u'This content is available in lessons. Are you sure you want to delete?')

    CONFIRM_CODE = 'EditableContentPackageDelete'
    CONFIRM_MSG = _(u'Are you sure you want to delete?')

    def _do_delete_object(self, theObject, event=True):
        library = self.get_library(context=self.context)
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
            Link(self.request.path, rel=u'confirm',
                 params=params, method=u'DELETE'),
        )
        raise_json_error(self.request,
                         hexc.HTTPConflict,
                         {
                             'code': code,
                             'message': message,
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
