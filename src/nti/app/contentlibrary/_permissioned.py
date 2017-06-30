#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from nti.appserver.pyramid_authorization import is_readable


class _PermissionedContentPackageMixin(object):

    def _test_is_readable(self, content_package, request=None):
        # test readability
        request = request or self._v_request
        result = is_readable(content_package, request)
        if not result:
            # Nope. What about a top-level child? 
            # TODO: Why we check children?
            result = any(is_readable(x, request)
                         for x in content_package.children or ())
        return result
