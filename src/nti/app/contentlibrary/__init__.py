#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import zope.i18nmessageid
MessageFactory = zope.i18nmessageid.MessageFactory(__name__)

from nti.app.contentlibrary.utils import PAGE_INFO_MT
from nti.app.contentlibrary.utils import PAGE_INFO_MT_JSON

#: Contents
VIEW_CONTENTS = 'contents'

#: A view to fetch the published contentx
VIEW_PUBLISH_CONTENTS = 'PublishContents'

#: A view to fetch the published contentx
VIEW_PACKAGE_WITH_CONTENTS = 'PackageWithContents'

#: A view to get user bundle records.
VIEW_USER_BUNDLE_RECORDS = 'UserBundleRecords'

#: A view to grant access to a bundle.
VIEW_BUNDLE_GRANT_ACCESS = 'GrantBundleAccess'

#: A view to remove access to a bundle.
VIEW_BUNDLE_REMOVE_ACCESS = 'RemoveBundleAccess'

#: Library path adapter
LIBRARY_ADAPTER = 'Library'

#: Content bundles path adapter
CONTENT_BUNDLES_ADAPTER = 'ContentBundles'

#: Bundle users path adapter
BUNDLE_USERS_PATH_ADAPTER = 'users'

#: Library Path (GET) View
LIBRARY_PATH_GET_VIEW = 'LibraryPath'

#: Redis sync lock name
SYNC_LOCK_NAME = '/var/libraries/Lock/sync'

#: The amount of time for which we will hold the lock during sync
LOCK_TIMEOUT = 80 * 60  # 80 minutes

#: The maximum amount of time in seconds to spend trying to acquire the lock
BLOCKING_TIMEOUT = 1.5
