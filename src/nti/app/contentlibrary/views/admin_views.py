#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import time

from zope import component

from zope.intid.interfaces import IIntIds

from requests.structures import CaseInsensitiveDict

from pyramid import httpexceptions as hexc

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.view_mixins import BatchingUtilsMixin

from nti.app.contentlibrary import MessageFactory as _

from nti.app.contentlibrary.views import LibraryPathAdapter

from nti.app.externalization.error import raise_json_error

from nti.common.string import is_true

from nti.contentlibrary import ALL_CONTENT_MIMETYPES

from nti.contentlibrary.index import get_contentlibrary_catalog

from nti.contentlibrary.interfaces import IContentPackage
from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.interfaces import resolve_content_unit_associations

from nti.contentlibrary.utils import get_content_packages

from nti.dataserver import authorization as nauth

from nti.externalization.externalization import to_external_object
from nti.externalization.externalization import StandardExternalFields

from nti.externalization.interfaces import LocatedExternalDict

from nti.links.links import Link

from nti.property.property import Lazy

CLASS = StandardExternalFields.CLASS
ITEMS = StandardExternalFields.ITEMS
LINKS = StandardExternalFields.LINKS
TOTAL = StandardExternalFields.TOTAL
MIMETYPE = StandardExternalFields.MIMETYPE
ITEM_COUNT = StandardExternalFields.ITEM_COUNT


@view_config(context=IContentPackage)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='DELETE',
               permission=nauth.ACT_NTI_ADMIN)
class ContentPackageDeleteView(AbstractAuthenticatedView):

    CONFIRM_CODE = 'ContentPackageDelete'
    CONFIRM_MSG = _(
        'This content has associations. Are you sure you want to delete?')

    @Lazy
    def _library(self):
        library = component.queryUtility(IContentPackageLibrary)
        return library

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
        raise_json_error(
            self.request,
            hexc.HTTPConflict,
            {
                u'code': code,
                u'message': message,
                CLASS: 'DestructiveChallenge',
                LINKS: to_external_object(links),
                MIMETYPE: 'application/vnd.nextthought.destructivechallenge'
            },
            None)

    def __call__(self):
        associations = resolve_content_unit_associations(self.context)
        params = CaseInsensitiveDict(self.request.params)
        force = is_true(params.get('force'))
        if not associations or force:
            self._do_delete_object(self.context)
        else:
            self._raise_conflict_error(self.CONFIRM_CODE,
                                       self.CONFIRM_MSG,
                                       associations)
        result = hexc.HTTPNoContent()
        result.last_modified = time.time()
        return result


@view_config(context=LibraryPathAdapter)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='POST',
               name="RemoveInvalidContentPackages",
               permission=nauth.ACT_NTI_ADMIN)
class RemoveInvalidPackagesView(AbstractAuthenticatedView):

    @Lazy
    def _library(self):
        library = component.queryUtility(IContentPackageLibrary)
        return library

    def _do_delete_object(self, theObject, event=True):
        library = self._library
        library.remove(theObject, event=event)
        return theObject

    def __call__(self):
        library = self._library
        result = LocatedExternalDict()
        result[ITEMS] = items = {}
        packages = get_content_packages(mime_types=ALL_CONTENT_MIMETYPES)
        for package in packages:
            stored = library.get(package.ntiid)
            if stored is None:
                logger.info('Removing package (%s)', package.ntiid)
                self._do_delete_object(package)
                items[package.ntiid] = package
        # remove invalid registrations
        try:
            for ntiid in library.removeInvalidContentUnits().keys():
                items[ntiid] = None
        except AttributeError:
            pass
        result[TOTAL] = result[ITEM_COUNT] = len(items)
        return result


@view_config(context=LibraryPathAdapter)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='GET',
               name="AllContentPackages",
               permission=nauth.ACT_NTI_ADMIN)
class AllContentPackagesView(AbstractAuthenticatedView,
                             BatchingUtilsMixin):

    _DEFAULT_BATCH_SIZE = 30
    _DEFAULT_BATCH_START = 0

    def __call__(self):
        result = LocatedExternalDict()
        result.__name__ = self.request.view_name
        result.__parent__ = self.request.context
        packages = get_content_packages(mime_types=ALL_CONTENT_MIMETYPES)
        packages.sort(key=lambda p: p.ntiid)
        result['TotalItemCount'] = len(packages)
        self._batch_items_iterable(result, packages)
        result[ITEM_COUNT] = len(result[ITEMS])
        return result


@view_config(context=LibraryPathAdapter)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='POST',
               name="ReindexAllContentPackages",
               permission=nauth.ACT_NTI_ADMIN)
class ReindexAllContentPackagesView(AbstractAuthenticatedView):

    @Lazy
    def _library(self):
        library = component.queryUtility(IContentPackageLibrary)
        return library

    def _process_meta(self, package):
        try:
            from nti.metadata import queue_add
            queue_add(package)
        except ImportError:
            pass

    def __call__(self):
        library  = self._library
        if library is not None:
            intids = component.getUtility(IIntIds)
            catalog = get_contentlibrary_catalog()
            for package in library.contentPackages or ():
                doc_id = intids.queryId(package)
                if doc_id is None:
                    continue
                catalog.index_doc(doc_id, package)
                self._process_meta(package)
        return hexc.HTTPNoContent()
