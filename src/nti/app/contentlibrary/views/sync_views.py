#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Sync views.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import sys
import time
import traceback
from six import string_types

from requests.structures import CaseInsensitiveDict

import transaction
try:
    from transaction._compat import get_thread_ident
except ImportError:
    def get_thread_ident():
        return id(transaction.get())

from zope import component

from zope.component.hooks import site as current_site

from zope.security.management import endInteraction
from zope.security.management import restoreInteraction

from zope.traversing.interfaces import IEtcNamespace

from pyramid import httpexceptions as hexc

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.contentlibrary import MessageFactory as _

from nti.app.contentlibrary import LOCK_TIMEOUT
from nti.app.contentlibrary import SYNC_LOCK_NAME

from nti.app.contentlibrary.subscribers import update_indices_when_content_changes

from nti.app.contentlibrary.synchronize import syncContentPackages

from nti.app.externalization.error import raise_json_error

from nti.app.externalization.internalization import read_body_as_external_object

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.common.string import is_true

from nti.contentlibrary.interfaces import IContentPackage
from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.interfaces import IRenderableContentPackage

from nti.contentlibrary.synchronize import SynchronizationResults
from nti.contentlibrary.synchronize import ContentPackageSyncResults

from nti.contentlibrary.utils import get_content_package_site

from nti.coremetadata.interfaces import IPublishable

from nti.dataserver.interfaces import IRedisClient
from nti.dataserver.interfaces import IDataserverFolder

from nti.dataserver.authorization import ACT_SYNC_LIBRARY

from nti.externalization.interfaces import LocatedExternalDict

from nti.property.property import Lazy

from nti.site.hostpolicy import get_host_site


@view_config(permission=ACT_SYNC_LIBRARY)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='POST',
               context=IDataserverFolder,
               name='RemoveSyncLock')
class _RemoveSyncLockView(AbstractAuthenticatedView):

    @Lazy
    def redis(self):
        return component.getUtility(IRedisClient)

    def __call__(self):
        self.redis.delete(SYNC_LOCK_NAME)
        return hexc.HTTPNoContent()


@view_config(permission=ACT_SYNC_LIBRARY)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='GET',
               context=IDataserverFolder,
               name='IsSyncInProgress')
class _IsSyncInProgressView(AbstractAuthenticatedView):

    @Lazy
    def redis(self):
        return component.getUtility(IRedisClient)

    def acquire(self):
        lock = self.redis.lock(SYNC_LOCK_NAME,
                               LOCK_TIMEOUT,
                               blocking_timeout=1)
        acquired = lock.acquire(blocking=False)
        return (lock, acquired)

    def release(self, lock, acquired):
        try:
            if acquired:
                lock.release()
        except Exception:
            pass

    def __call__(self):
        lock, acquired = self.acquire()
        self.release(lock, acquired)
        return not acquired


@view_config(permission=ACT_SYNC_LIBRARY)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='POST',
               context=IDataserverFolder,
               name='SetSyncLock')
class _SetSyncLockView(AbstractAuthenticatedView):

    @Lazy
    def redis(self):
        return component.getUtility(IRedisClient)

    def acquire(self):
        # Fail fast if we cannot acquire the lock.
        lock = self.redis.lock(SYNC_LOCK_NAME, LOCK_TIMEOUT)
        acquired = lock.acquire(blocking=False)
        if acquired:
            return lock
        raise_json_error(self.request,
                         hexc.HTTPLocked,
                         {
                             'message': _('Sync already in progress'),
                             'code': 'Exception'},
                         None)

    def __call__(self):
        self.acquire()
        return hexc.HTTPNoContent()


@view_config(permission=ACT_SYNC_LIBRARY)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='GET',
               context=IDataserverFolder,
               name='LastSyncTime')
class _LastSyncTimeView(AbstractAuthenticatedView):

    def __call__(self):
        try:
            hostsites = component.getUtility(IEtcNamespace, name='hostsites')
            return hostsites.lastSynchronized or 0
        except AttributeError:
            return 0


class _AbstractSyncAllLibrariesView(_SetSyncLockView,
                                    ModeledContentUploadRequestUtilsMixin):

    def readInput(self, value=None):
        result = CaseInsensitiveDict()
        if self.request:
            if self.request.body:
                values = read_body_as_external_object(self.request)
            else:
                values = self.request.params
            result.update(values)
        return result

    def release(self, lock):
        try:
            lock.release()
        except Exception:
            logger.exception("Error while releasing Sync lock")

    def _txn_id(self):
        return "txn.%s" % get_thread_ident()

    def _do_call(self):
        pass

    def __call__(self):
        logger.info('Acquiring sync lock')
        endInteraction()
        lock = self.acquire()
        try:
            logger.info('Starting sync %s', self._txn_id())
            return self._do_call()
        finally:
            self.release(lock)
            restoreInteraction()


class _SyncContentPackagesMixin(_AbstractSyncAllLibrariesView):

    # Because we'll be doing a lot of filesystem IO, which may not
    # be well cooperatively tasked (gevent), we would like to give
    # the opportunity for other greenlets to run by sleeping inbetween
    # syncing each library. However, for some reason, under unittests,
    # this leads to very odd and unexpected test failures
    # (specifically in nti.app.products.courseware) so we allow
    # disabling it.
    _SLEEP = True

    def _executable(self, sleep, site=None, *args, **kwargs):
        raise NotImplementedError

    def _do_sync(self, site=None, *args, **kwargs):
        now = time.time()
        result = LocatedExternalDict()
        result['Transaction'] = self._txn_id()
        try:
            params, results = self._executable(sleep=self._SLEEP,
                                               site=site,
                                               *args,
                                               **kwargs)
            result['Params'] = params
            result['Results'] = results
            result['SyncTime'] = time.time() - now
        except Exception as e:  # FIXME: Way too broad an exception
            logger.exception("Failed to Sync %s", self._txn_id())

            transaction.doom()  # cancel changes

            exc_type, exc_value, exc_traceback = sys.exc_info()
            result['code'] = e.__class__.__name__
            result['message'] = str(e)
            # XXX: No, we should not expose the traceback over the web. Ever,
            # unless the exception catching middleware is installed, which is only
            # in devmode.
            result['traceback'] = repr(traceback.format_exception(exc_type,
                                                                  exc_value,
                                                                  exc_traceback))
            raise_json_error(self.request,
                             hexc.HTTPUnprocessableEntity,
                             result,
                             exc_traceback)
        return result

    def _do_call(self):
        values = self.readInput()
        # parse params
        site = values.get('site')
        # Unfortunately, zope.dublincore includes a global subscriber registration
        # (zope.dublincore.creatorannotator.CreatorAnnotator)
        # that will update the `creators` property of IZopeDublinCore to include
        # the current principal when any ObjectCreated /or/ ObjectModified event
        # is fired, if there is a current interaction. Normally we want this,
        # but here we care specifically about getting the dublincore metadata
        # we specifically defined in the libraries, and not the requesting principal.
        # Our simple-minded approach is to simply void the interaction during this process
        # (which works so long as zope.securitypolicy doesn't get involved...)
        # This is somewhat difficult to test the side-effects of, sadly.

        # JZ - 8.2015 - Disabling interaction also prevents stream changes
        # from being broadcast (specifically topic creations). We've seen such
        # changes end up causing conflict issues when managing sessions. These
        # retries cause syncs to take much longer to perform.
        return self._do_sync(site=site)


@view_config(permission=ACT_SYNC_LIBRARY)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               context=IDataserverFolder,
               name='SyncAllLibraries')
class _SyncAllLibrariesView(_SyncContentPackagesMixin):
    """
    A view that synchronizes all of the in-database libraries
    (and sites) with their on-disk and site configurations.
    If you GET this view, changes to not take effect but are just
    logged.

    .. note:: TODO: While this may be useful for scripts,
            we also need to write a pretty HTML page that shows
            the various sync stats, like time last sync'd, whether
            the directory is found, etc, and lets people sync
            from there.
    """

    def _executable(self, sleep, site, *args, **kwargs):
        return syncContentPackages(sleep=sleep, site=site, *args, **kwargs)

    def _do_call(self):
        values = self.readInput()
        # parse params
        site = values.get('site')
        allowRemoval = values.get('allowRemoval') or u''
        allowRemoval = is_true(allowRemoval)
        # things to sync
        for name in ('ntiids', 'ntiid', 'packages', 'package'):
            ntiids = values.get(name)
            if ntiids:
                break
        if isinstance(ntiids, string_types):
            ntiids = set(ntiids.split())
        ntiids = tuple(ntiids) if ntiids else ()
        # execute
        result = self._do_sync(site=site,
                               ntiids=ntiids,
                               allowRemoval=allowRemoval)
        return result


@view_config(name='Sync')
@view_config(name='Synchronize')
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               context=IContentPackage,
               permission=ACT_SYNC_LIBRARY)
class _SyncContentPacakgeView(_AbstractSyncAllLibrariesView):
    """
    A view that synchronizes a content package
    """

    def _replace(self, package):
        ntiid = package.ntiid
        site = get_content_package_site(package)
        # prepare results
        sync_results = SynchronizationResults()
        results = ContentPackageSyncResults(Site=site,
                                            ContentPackageNTIID=package.ntiid)
        sync_results.add(results)
        # do sync
        with current_site(get_host_site(site)):  # use pkg site
            library = component.getUtility(IContentPackageLibrary)
            # enumerate all content packages
            enumeration = library.enumeration
            content_packages = enumeration.enumerateContentPackages()
            content_packages = {x.ntiid: x for x in content_packages}
            # replace w/ new one
            library.replace(content_packages[ntiid], results=sync_results)
        return results

    def _do_call(self):
        package = self.context
        if      IRenderableContentPackage.providedBy(package) \
            and not package.is_published():
            raise_json_error(self.request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 'message': _('Content has not been published'),
                                 'code': 'Exception'},
                             None)
        return self._replace(package)


@view_config(context=IContentPackage)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               permission=ACT_SYNC_LIBRARY,
               name='SyncPresentationAssets')
class SyncPresentationAssetsView(_AbstractSyncAllLibrariesView):

    def _process_package(self, package):
        site = get_content_package_site(package)
        with current_site(get_host_site(site)):  # use pkg site
            return update_indices_when_content_changes(package)

    def _do_call(self):
        package = self.context
        if IPublishable.providedBy(package) and not package.is_published():
            raise_json_error(self.request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 'message': _('Content has not been published'),
                                 'code': 'Exception'},
                             None)
        return self._process_package(package)
