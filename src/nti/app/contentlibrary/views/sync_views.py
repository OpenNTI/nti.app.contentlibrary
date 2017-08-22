#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import sys
import time
from six import string_types

from requests.structures import CaseInsensitiveDict

import transaction
try:
    from transaction._compat import get_thread_ident
except ImportError:
    def get_thread_ident():
        return id(transaction.get())

from zope import component
from zope import exceptions

from zope.cachedescriptors.property import Lazy

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
from nti.app.contentlibrary import BLOCKING_TIMEOUT

from nti.app.contentlibrary.interfaces import IContentPackageMetadata
from nti.app.contentlibrary.interfaces import IContentTrackingRedisClient

from nti.app.contentlibrary.synchronize import syncContentPackages

from nti.app.contentlibrary.synchronize.subscribers import update_indices_when_content_changes

from nti.app.externalization.error import raise_json_error

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.common.string import is_true

from nti.contentlibrary.interfaces import IContentPackage
from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.interfaces import IRenderableContentPackage

from nti.contentlibrary.synchronize import SynchronizationResults
from nti.contentlibrary.synchronize import ContentPackageSyncResults

from nti.dataserver.authorization import ACT_SYNC_LIBRARY

from nti.dataserver.interfaces import IDataserverFolder

from nti.externalization.interfaces import LocatedExternalDict

from nti.externalization.externalization import to_external_object
from nti.externalization.externalization import StandardExternalFields

from nti.links.links import Link

from nti.publishing.interfaces import IPublishable

from nti.site.interfaces import IHostPolicyFolder

ITEMS = StandardExternalFields.ITEMS
LINKS = StandardExternalFields.LINKS
ITEM_COUNT = StandardExternalFields.ITEM_COUNT


@view_config(permission=ACT_SYNC_LIBRARY)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='POST',
               context=IDataserverFolder,
               name='RemoveSyncLock')
class RemoveSyncLockView(AbstractAuthenticatedView):

    @Lazy
    def redis(self):
        return component.getUtility(IContentTrackingRedisClient)

    def __call__(self):
        self.redis.delete_lock(SYNC_LOCK_NAME)
        return hexc.HTTPNoContent()


@view_config(permission=ACT_SYNC_LIBRARY)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='GET',
               context=IDataserverFolder,
               name='IsSyncInProgress')
class IsSyncInProgressView(AbstractAuthenticatedView):

    @Lazy
    def redis(self):
        return component.getUtility(IContentTrackingRedisClient)

    def __call__(self):
        return self.redis.is_locked


@view_config(permission=ACT_SYNC_LIBRARY)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='POST',
               context=IDataserverFolder,
               name='SetSyncLock')
class SetSyncLockView(AbstractAuthenticatedView):

    @Lazy
    def redis(self):
        return component.getUtility(IContentTrackingRedisClient)

    def acquire(self):
        # Fail fast if we cannot acquire the lock.
        acquired = self.redis.acquire_lock(self.remoteUser,
                                           SYNC_LOCK_NAME,
                                           LOCK_TIMEOUT,
                                           BLOCKING_TIMEOUT)
        if acquired:
            return self.redis.lock
        raise_json_error(self.request,
                         hexc.HTTPLocked,
                         {
                             'message': _(u'Sync in progress'),
                             'code': 'Exception'
                         },
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
class LastSyncTimeView(AbstractAuthenticatedView):

    def __call__(self):
        try:
            hostsites = component.getUtility(IEtcNamespace, name='hostsites')
            return hostsites.lastSynchronized or 0
        except AttributeError:
            return 0


class _AbstractSyncAllLibrariesView(SetSyncLockView,
                                    ModeledContentUploadRequestUtilsMixin):

    def readInput(self, value=None):
        result = CaseInsensitiveDict()
        if self.request:
            if self.request.body:
                values = super(_AbstractSyncAllLibrariesView, self).readInput(value)
            else:
                values = self.request.params
            result.update(values)
        return result

    def release(self):
        try:
            self.redis.release_lock(self.remoteUser)
        except Exception:
            logger.exception("Error while releasing Sync lock")

    def _mark_sync_data(self):
        metadata = IContentPackageMetadata(self.context)
        metadata.updateLastMod()
        metadata.holding_user = self.remoteUser.username
        metadata.is_locked = self.redis.is_locked

    def _txn_id(self):
        return "txn.%s" % get_thread_ident()

    def _do_call(self):
        pass

    def __call__(self):
        logger.info('Acquiring sync lock')
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
        endInteraction()
        self.acquire()
        try:
            logger.info('Starting sync %s', self._txn_id())
            return self._do_call()
        except Exception as e:  # FIXME: Way too broad an exception
            logger.exception("Failed to Sync %s", self._txn_id())
            exc_type, exc_value, exc_traceback = sys.exc_info()
            result = LocatedExternalDict()
            result['message'] = str(e)
            result['code'] = e.__class__.__name__
            result['traceback'] = repr(exceptions.format_exception(exc_type,
                                                                   exc_value,
                                                                   exc_traceback,
                                                                   with_filenames=True))
            raise_json_error(self.request,
                             hexc.HTTPUnprocessableEntity,
                             result,
                             exc_traceback)
        finally:
            self.release()
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
        params, results = self._executable(sleep=self._SLEEP,
                                           site=site,
                                           *args,
                                           **kwargs)
        result['Params'] = params
        result['Results'] = results
        result['SyncTime'] = time.time() - now
        return result

    def _do_call(self):
        values = self.readInput()
        # parse params
        site = values.get('site')
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
class SyncContentPackageView(_AbstractSyncAllLibrariesView):
    """
    A view that synchronizes a content package
    """

    def release(self):
        super(SyncContentPackageView, self).release()
        self._mark_sync_data()

    def acquire(self):
        super(SyncContentPackageView, self).acquire()
        self._mark_sync_data()

    def _replace(self, package):
        ntiid = package.ntiid
        # prepare results
        folder = IHostPolicyFolder(package)
        sync_results = SynchronizationResults()
        results = ContentPackageSyncResults(Site=folder.__name__,
                                            ContentPackageNTIID=package.ntiid)
        sync_results.add(results)
        # do sync
        with current_site(folder):  # use pkg site
            library = component.getUtility(IContentPackageLibrary)
            # enumerate all content packages
            enumeration = library.enumeration
            content_packages = [
                x for x in enumeration.enumerateContentPackages() if x.ntiid == ntiid
            ]
            if not content_packages:
                raise_json_error(self.request,
                                 hexc.HTTPUnprocessableEntity,
                                 {
                                     'message': _(u'Could not find contents in library.'),
                                 },
                                 None)
            # replace w/ new one
            library.replace(content_packages[0], results=sync_results)
        return results

    def _do_call(self):
        package = self.context
        if      IRenderableContentPackage.providedBy(package) \
            and not package.is_published():
            raise_json_error(self.request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 'message': _(u'Content has not been published.'),
                             },
                             None)
        return self._replace(package)


@view_config(context=IContentPackage)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               permission=ACT_SYNC_LIBRARY,
               name='SyncPresentationAssets')
class SyncPresentationAssetsView(SyncContentPackageView):

    def _process_package(self, package):
        folder = IHostPolicyFolder(package)
        with current_site(folder):  # use pkg site
            return update_indices_when_content_changes(package)

    def _do_call(self):
        package = self.context
        if IPublishable.providedBy(package) and not package.is_published():
            raise_json_error(self.request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 'message': _(u'Content has not been published.'),
                             },
                             None)
        return self._process_package(package)


@view_config(context=IDataserverFolder)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               permission=ACT_SYNC_LIBRARY,
               name='SyncMetadata')
class SyncMetadataView(AbstractAuthenticatedView):

    def __call__(self):
        tracking_redis = component.getUtility(IContentTrackingRedisClient)
        results = to_external_object(tracking_redis)
        try:
            hostsites = component.getUtility(IEtcNamespace, name='hostsites')
            results['last_synchronized'] = hostsites.lastSynchronized or 0
        except AttributeError:
            results['last_synchronized'] = 0
        if results['last_released'] == None:
            results.pop('last_released')
        else:
            results.pop('last_locked')
        return results


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             permission=ACT_SYNC_LIBRARY,
             context=IDataserverFolder,
             name='SyncableContentPackages')
class GetSyncablePackagesView(AbstractAuthenticatedView):

    def __call__(self):
        results = LocatedExternalDict()
        library = component.getUtility(IContentPackageLibrary)
        syncable_packages = [
            x for x in library.enumeration.enumerateContentPackages()
        ]
        results[ITEM_COUNT] = len(syncable_packages)
        results[ITEMS] = []
        for package in syncable_packages:
            metadata = IContentPackageMetadata(package)
            ext_object = to_external_object(metadata)
            ext_object[LINKS] = [Link(package,
                                      rel="Sync",
                                      elements=("@@Sync",))]
            results[ITEMS].append(ext_object)
        return results
