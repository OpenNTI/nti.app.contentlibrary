#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from pyramid.view import view_config

from nti.appserver.ugd_edit_views import ContainerContextUGDPostView

from nti.contentlibrary.interfaces import IContentPackageBundle

from nti.dataserver.authorization import ACT_READ

@view_config(route_name='objects.generic.traversal',
			 renderer='rest',
			 request_method='POST',
			 context=IContentPackageBundle,
			 permission=ACT_READ,
			 name='Pages')
class ContentBundlePagesView(ContainerContextUGDPostView):
	"""
	A pages view on the course.  We subclass ``ContainerContextUGDPostView``
	in order to intervene and annotate our ``IContainerContext``
	object with the content bundle context.

	Reading/Editing/Deleting will remain the same.
	"""
