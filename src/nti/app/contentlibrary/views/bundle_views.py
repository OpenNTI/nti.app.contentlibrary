#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import uuid

from zope import component

from zope import lifecycleevent

from zope.cachedescriptors.property import Lazy

from zope.component.hooks import site as current_site

from pyramid import httpexceptions as hexc

from pyramid.view import view_config

from nti.app.base.abstract_views import get_all_sources
from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.contentlibrary import MessageFactory as _

from nti.app.contentlibrary.views import BundlesPathAdapter

from nti.app.externalization.error import raise_json_error

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.appserver.policies.interfaces import ISitePolicyUserEventListener

from nti.appserver.ugd_edit_views import ContainerContextUGDPostView

from nti.contentlibrary.interfaces import IContentPackageBundle
from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.interfaces import IContentPackageBundleLibrary
from nti.contentlibrary.interfaces import IFilesystemContentPackageLibrary

from nti.contentlibrary.utils import NTI
from nti.contentlibrary.utils import make_content_package_bundle_ntiid 

from nti.dataserver.authorization import ACT_READ
from nti.dataserver.authorization import ACT_CONTENT_EDIT

from nti.site.interfaces import IHostPolicyFolder


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


class ContentPackageBundleMixin(object):

    @Lazy
    def extra(self):
        return str(uuid.uuid4()).split('-')[0].upper()

    def get_source(self, request=None):
        request = self.request if not request else request
        sources = get_all_sources(request)
        if sources:
            return iter(sources.values()).next()
        return None

    #def presentation_assets
    def get_library(self, context=None, provided=IContentPackageBundleLibrary):
        if context is None:
            library = component.queryUtility(provided)
        else:
            # If context is given, attempt to use the site the given context
            # is stored in. This is necessary to avoid data loss during sync.
            with current_site(IHostPolicyFolder(context)):
                library = component.queryUtility(provided)
        if library is None:
            raise_json_error(self.request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                'message': _(u"Library not available."),
                                'code': 'LibraryNotAvailable',
                             },
                             None)
        return library

    def validate_content_library(self, context=None):
        library = self.get_library(context, IContentPackageLibrary)
        if not IFilesystemContentPackageLibrary.providedBy(library):
            raise_json_error(self.request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                'message': _(u"Library not supported."),
                                'code': 'LibraryNotSupported',
                             },
                             None)
        return library

    @classmethod
    def make_bundle_ntiid(cls, provider=None, base=None, extra=None):
        policy = component.queryUtility(ISitePolicyUserEventListener)
        provider = provider or getattr(policy, 'PROVIDER', None) or NTI
        return make_content_package_bundle_ntiid(provider, base, extra)


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             request_method='POST',
             context=BundlesPathAdapter,
             permission=ACT_CONTENT_EDIT)
class ContentBundlePostView(AbstractAuthenticatedView,
                            ModeledContentUploadRequestUtilsMixin,
                            ContentPackageBundleMixin):
    
    content_predicate = IContentPackageBundle

    def readInput(self, value=None):
        result = super(ContentBundlePostView, self).readInput(value)
        result.pop('NTIID', None)
        result.pop('ntiid', None)
        return result

    def _set_ntiid(self, context):
        context.ntiid = self.make_bundle_ntiid(context)

    def _do_call(self):
        # make sure we can write in the library
        self.validate_content_library()
        # read incoming object
        bundle = self.readCreateUpdateContentObject(self.remoteUser, 
                                                    search_owner=False)
        # set ntiid
        self._set_ntiid(bundle)
        # set creator
        bundle.creator = self.remoteUser.username
        # add to library
        lifecycleevent.created(bundle)
        bundle_library = self.get_library(provided=IContentPackageBundleLibrary)
        bundle_library[bundle.ntiid] = bundle
        self.request.response.status_int = 201
        logger.info('Created new content package bundle (%s)', bundle.ntiid)
        return bundle
