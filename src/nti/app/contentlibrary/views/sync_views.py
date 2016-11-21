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

import transaction
try:
	from transaction._compat import get_thread_ident
except ImportError:
	def get_thread_ident():
		return id(transaction.get())

from zope import component

from zope.security.management import endInteraction
from zope.security.management import restoreInteraction

from zope.traversing.interfaces import IEtcNamespace

from pyramid import httpexceptions as hexc

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.contentlibrary import LOCK_TIMEOUT
from nti.app.contentlibrary import SYNC_LOCK_NAME

from nti.app.contentlibrary.synchronize import syncContentPackages
from nti.app.contentlibrary.synchronize import addRemoveContentPackages

from nti.app.externalization.error import raise_json_error

from nti.app.externalization.internalization import read_body_as_external_object

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.common.maps import CaseInsensitiveDict

from nti.common.string import TRUE_VALUES

from nti.dataserver.interfaces import IRedisClient
from nti.dataserver.interfaces import IDataserverFolder

from nti.dataserver.authorization import ACT_SYNC_LIBRARY

from nti.externalization.interfaces import LocatedExternalDict

from nti.property.property import Lazy

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
		lock = self.redis.lock(SYNC_LOCK_NAME, LOCK_TIMEOUT, blocking_timeout=1)
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
						 {'message': 'Sync already in progress',
						  'code':'Exception'},
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
		hostsites = component.getUtility(IEtcNamespace, name='hostsites')
		result = getattr(hostsites, 'lastSynchronized', 0)
		return result

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

@view_config(permission=ACT_SYNC_LIBRARY)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   context=IDataserverFolder,
			   name='AddRemoveContentPackages')
class _AddRemoveContentPackagesView(_AbstractSyncAllLibrariesView):
	"""
	A view that adds new content pacakges and removes old ones
	using the data rom on-disk and site configurations.
	If you GET this view, changes to not take effect but are just
	logged.
	"""

	# Because we'll be doing a lot of filesystem IO, which may not
	# be well cooperatively tasked (gevent), we would like to give
	# the opportunity for other greenlets to run by sleeping inbetween
	# syncing each library. However, for some reason, under unittests,
	# this leads to very odd and unexpected test failures
	# (specifically in nti.app.products.courseware) so we allow
	# disabling it.
	_SLEEP = True

	def _executable(self, sleep, site, *args, **kwargs):
		return addRemoveContentPackages(sleep=sleep, site=site)

	def _do_sync(self, site, *args, **kwargs):
		now = time.time()
		result = LocatedExternalDict()
		result['Transaction'] = self._txn_id()
		try:
			params, results = self._executable(sleep=self._SLEEP,
										  	   site=site,
										  	   *args, **kwargs)
			result['Params'] = params
			result['Results'] = results
			result['SyncTime'] = time.time() - now
		except Exception as e: # FIXME: Way too broad an exception
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
		result = self._do_sync(site=site)
		return result

@view_config(permission=ACT_SYNC_LIBRARY)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   context=IDataserverFolder,
			   name='SyncAllLibraries')
class _SyncAllLibrariesView(_AddRemoveContentPackagesView):
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
		allowRemoval = allowRemoval.lower() in TRUE_VALUES
		# things to sync (package and courses)
		for name in ('ntiids', 'ntiid', 'packages', 'package'):
			ntiids = values.get(name)
			if ntiids:
				break
		ntiids = set(ntiids.split()) if isinstance(ntiids, string_types) else ntiids
		ntiids = list(ntiids) if ntiids else ()
		# execute
		result = self._do_sync(site=site, ntiids=ntiids, allowRemoval=allowRemoval)
		return result
