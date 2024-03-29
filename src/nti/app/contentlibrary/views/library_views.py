#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Views for exposing the content library to clients.

.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from pyramid import traversal
from pyramid import httpexceptions as hexc

from pyramid.view import view_config
from pyramid.view import view_defaults

from requests.structures import CaseInsensitiveDict

from six.moves import urllib_parse

from zope import component
from zope import interface

from zope.location.interfaces import ILocationInfo

from nti.app.authentication import get_remote_user

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.contentlibrary import LIBRARY_PATH_GET_VIEW

from nti.app.contentlibrary import MessageFactory as _

from nti.app.contentlibrary.utils import PAGE_INFO_MT
from nti.app.contentlibrary.utils import PAGE_INFO_MT_JSON
from nti.app.contentlibrary.utils import find_page_info_view_helper

from nti.app.renderers.caching import AbstractReliableLastModifiedCacheController

from nti.app.renderers.interfaces import IExternalCollection
from nti.app.renderers.interfaces import IPreRenderResponseCacheController
from nti.app.renderers.interfaces import IResponseCacheController

from nti.appserver.context_providers import get_hierarchy_context
from nti.appserver.context_providers import get_top_level_contexts
from nti.appserver.context_providers import get_top_level_contexts_for_user

from nti.appserver.dataserver_pyramid_views import GenericGetView

from nti.appserver.interfaces import ForbiddenContextException
from nti.appserver.interfaces import IHierarchicalContextProvider
from nti.appserver.interfaces import ILibraryPathLastModifiedProvider

from nti.appserver.pyramid_authorization import is_readable
from nti.appserver.pyramid_authorization import has_permission

from nti.appserver.workspaces.interfaces import IService

from nti.contentlibrary import CONTENT_UNIT_MIME_TYPE
from nti.contentlibrary import CONTENT_PACKAGE_MIME_TYPE
from nti.contentlibrary import RENDERABLE_CONTENT_UNIT_MIME_TYPE
from nti.contentlibrary import RENDERABLE_CONTENT_PACKAGE_MIME_TYPE

from nti.contentlibrary.indexed_data import get_catalog

from nti.contentlibrary.interfaces import IContentUnit
from nti.contentlibrary.interfaces import IContentPackage
from nti.contentlibrary.interfaces import IContentRendered
from nti.contentlibrary.interfaces import IRenderableContentUnit
from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.interfaces import IContentUnitHrefMapper

from nti.contenttypes.presentation.interfaces import IPresentationAsset

from nti.coremetadata.interfaces import IContainerContext
from nti.coremetadata.interfaces import IDeactivatedObject

from nti.dataserver import authorization as nauth

from nti.dataserver.contenttypes.forums.interfaces import IPost
from nti.dataserver.contenttypes.forums.interfaces import ITopic
from nti.dataserver.contenttypes.forums.interfaces import IForum
from nti.dataserver.contenttypes.forums.interfaces import IBoard
from nti.dataserver.contenttypes.forums.interfaces import IPersonalBlog

from nti.dataserver.interfaces import IBookmark
from nti.dataserver.interfaces import IHighlight
from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IDataserverFolder

from nti.recorder.interfaces import TRX_TYPE_CREATE
from nti.recorder.interfaces import ITransactionRecordHistory

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import LocatedExternalList
from nti.externalization.interfaces import StandardExternalFields

from nti.externalization.externalization import toExternalObject
from nti.externalization.externalization import removed_unserializable

from nti.links.links import Link

from nti.mimetype.mimetype import nti_mimetype_with_class

from nti.ntiids.ntiids import ROOT
from nti.ntiids.ntiids import is_valid_ntiid_string
from nti.ntiids.ntiids import find_object_with_ntiid

from nti.publishing.interfaces import IPublishable

from nti.traversal.traversal import find_interface

CLASS = StandardExternalFields.CLASS
ITEMS = StandardExternalFields.ITEMS
MIMETYPE = StandardExternalFields.MIMETYPE
LAST_MODIFIED = StandardExternalFields.LAST_MODIFIED

logger = __import__('logging').getLogger(__name__)


def _create_page_info(request, href, ntiid, last_modified=0, jsonp_href=None):
    """
    :param float last_modified: If greater than 0, the best known date for the
            modification time of the contents of the `href`.
    """
    # Traverse down to the pages collection and use it to create the info.
    # This way we get the correct link structure

    dataserver = request.registry.getUtility(IDataserver)
    remote_user = get_remote_user(request, dataserver=dataserver)
    if not remote_user:
        raise hexc.HTTPForbidden()

    registry = request.registry
    user_service = registry.getAdapter(remote_user, IService)
    user_workspace = user_service.user_workspace
    pages_collection = user_workspace.pages_collection
    info = pages_collection.make_info_for(ntiid)

    # set extra links
    if href:
        info.extra_links = (Link(href, rel='content'),)  # TODO: The rel?
    if jsonp_href:
        link = Link(jsonp_href,
                    rel='jsonp_content',
                    target_mime_type='application/json')
        info.extra_links = info.extra_links + (link,)  # TODO: The rel?

    info.contentUnit = request.context
    package = find_interface(info.contentUnit, IContentPackage, strict=False)
    if package is not None:
        link = Link(package, rel='package')
        info.extra_links = info.extra_links + (link,)
    if last_modified:
        # FIXME: Need to take into account the assessment item times as well
        # This is probably not huge, because right now they both change at the
        # same time due to the rendering process. But we can expect that to decouple
        # NOTE: The preferences decorator may change this, but only to be newer
        info.lastModified = last_modified
    return info


_content_view_defaults = dict(route_name='objects.generic.traversal',
                              renderer='rest',
                              context=IContentUnit,
                              permission=nauth.ACT_READ,
                              request_method='GET')


@view_config(accept=CONTENT_UNIT_MIME_TYPE,
             **_content_view_defaults)
class _ContentUnitGetView(GenericGetView):
    pass


@view_config(accept=CONTENT_PACKAGE_MIME_TYPE,
             **_content_view_defaults)
class _ContentPackageGetView(GenericGetView):
    pass


@view_config(accept=RENDERABLE_CONTENT_UNIT_MIME_TYPE,
             **_content_view_defaults)
class _RenderableContentUnitGetView(GenericGetView):
    pass


@view_config(accept=RENDERABLE_CONTENT_PACKAGE_MIME_TYPE,
             **_content_view_defaults)
class _RenderableContentPackageGetView(GenericGetView):
    pass

@view_config(name='')
@view_config(name='link+json')
@view_config(name='pageinfo+json')
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               context=IContentUnit,
               permission=nauth.ACT_READ,
               request_method='GET')
class _LibraryTOCRedirectClassView(object):
    """
    Given an :class:`lib_interfaces.IContentUnit`, redirect the request
    to the (perhaps) static content. This allows unifying handling of
    NTIIDs.

    If the client uses the ``Accept`` header to ask for a Link to the
    content, though, then return that link; the client will do the
    redirection manually. (This is helpful for clients that need to
    know the URL of the content and which are using libraries that
    otherwise would swallow it and automatically redirect.) Our response
    will include the ``Vary: Accept`` header.

    Certain browsers have a hard time dealing with the ``Vary:
    Accept`` header, and this is one place that it really matters. Our
    request provides an ETag that is variant-specific to encourage
    good behaviour. However, the browsers that apparently mis-behave,
    (Chrome [25,27)), pay no attention to that. They also pay no
    attention to Cache-Control: no-store, no-cache and Pragma:
    no-cache. We thus rely on the client to deal with this situation.
    To facilitate that, we are registered as the empty view name, plus
    two other view names; all of them use the standard Accept mechanism, but
    the alternate names allow browsers to form unique URLs (without the totally
    cache-busting use of query parameters).

    This also works when used as a view named for the ROOT ntiid; no
    href is possible, but the rest of the data can be returned.
    """

    def __init__(self, request):
        self.request = request

    def _is_published(self, unit):
        return not IPublishable.providedBy(unit) or unit.is_published()

    def _lastModified(self, request):
        # This should be the time of the .html file
        lastModified = request.context.lastModified
        # But the ToC is important too, so we take the newest
        # of all these that we can find
        root_package = traversal.find_interface(request.context,
                                                IContentPackage)
        lastModified = max(lastModified,
                           getattr(root_package, 'lastModified', 0),
                           getattr(root_package, 'index_last_modified', 0))
        return lastModified

    link_mimeType = link_mt = nti_mimetype_with_class('link')
    link_mt_json = link_mimeType + '+json'
    link_mts = (link_mimeType, link_mt_json)

    json_mimeType = u'application/json'
    page_info_mimeType = PAGE_INFO_MT
    page_info_mt_json = PAGE_INFO_MT_JSON
    page_mts = (json_mimeType, page_info_mimeType, page_info_mt_json)

    mimeTypes = (u'text/html', link_mimeType, link_mt_json,
                 json_mimeType, page_info_mimeType, page_info_mt_json)

    def _as_link(self, href, lastModified, request):
        link = Link(href, rel="content")
        # We cannot render a raw link using the code in pyramid_renderers, but
        # we need to return one to get the right mime type header. So we
        # fake it by rendering here

        def _t_ext_obj(**unused_kwargs):
            return {CLASS: "Link",
                    MIMETYPE: self.link_mt,
                    "href": href,
                    "rel": "content",
                    LAST_MODIFIED: lastModified or None}

        link.__name__ = href
        link.__parent__ = request.context
        link.toExternalObject = _t_ext_obj
        interface.alsoProvides(link, ILocationInfo)
        link.getNearestSite = lambda: component.getUtility(IDataserver).root
        return link

    def _check_publication_view(self, context):
        # Allow access if rendered and the content is published or we have
        # admin.
        if      not self._is_published(context) \
            and not has_permission(nauth.ACT_CONTENT_EDIT, context, self.request):
            msg = _(u'Do not have access to unpublished object.')
            raise hexc.HTTPForbidden(msg)
        if      IRenderableContentUnit.providedBy(context) \
            and not IContentRendered.providedBy(context):
            raise hexc.HTTPNotFound(_(u'Object not yet rendered.'))

    def _get_unit_href(self, unit, default_href):
        mapper = IContentUnitHrefMapper(unit, None)
        if mapper is None:
            # Try key
            mapper = IContentUnitHrefMapper(unit.key, None)
        result = mapper and mapper.href
        return result or default_href

    def __call__(self):
        jsonp_href = None
        request = self.request
        href = request.context.href

        self._check_publication_view(request.context)

        # Right now, the ILibraryTOCEntries always have relative hrefs,
        # which may or may not include a leading /.
        # Is it a relative path?
        assert not href.startswith('/') or '://' not in href

        # FIXME: We're assuming these map into the URL space based on their
        # root name. Is that valid? Do we need another mapping layer?
        href = self._get_unit_href(request.context, href)
        jsonp = request.context.href + '.jsonp'
        jsonp_key = request.context.does_sibling_entry_exist(jsonp)
        if jsonp_key is not None and jsonp_key:
            jsonp_href = IContentUnitHrefMapper(jsonp_key).href

        lastModified = self._lastModified(request)

        # If the client asks for a specific type of data,
        # a link, then give it to them. Otherwise...
        accept_type = u'text/html'
        if request.accept:
            accept_type = request.accept.best_match(self.mimeTypes)

        if accept_type in self.link_mts:
            return self._as_link(href, lastModified, request)

        if accept_type in self.page_mts:
            # Send back our canonical location, just in case we got here via
            # something like the _ContentUnitPreferencesPutView. This assists the cache
            # to know what to invalidate.
            # (Mostly in tests we find we cannot rely on traversal, so HACK it in manually)
            location = '/dataserver2/Objects/' + request.context.ntiid
            request.response.content_location = urllib_parse.quote(location).encode('utf-8')

            return _create_page_info(request,
                                     href,
                                     request.context.ntiid,
                                     last_modified=lastModified,
                                     jsonp_href=jsonp_href)

        # ...send a 302. Return rather than raise so that webtest works better
        return hexc.HTTPSeeOther(location=href)


def _LibraryTOCRedirectView(request):
    return _LibraryTOCRedirectClassView(request)()


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             name=ROOT,
             permission=nauth.ACT_READ,
             request_method='GET')
def _RootLibraryTOCRedirectView(request):
    """
    For the root NTIID, we only support returning PageInfo (never a link to content,
    and never the content itself, because those things do not exist.) Thus we bypass
    the complex Accept logic of :class:`._LibraryTOCRedirectClassView`.
    """
    # It turns out to be not worth it to try to share the logic
    # because our request.context is not specified (in practice, it may be a
    # _ContentUnitPreferences or _NTIIDsContainerResource)

    ntiid = request.view_name
    location = '/dataserver2/Objects/' + ntiid
    request.response.content_location = urllib_parse.quote(location).encode('utf-8')
    return _create_page_info(request, None, ntiid)


@view_config(context=IContentPackageLibrary,
             request_method='GET')
class MainLibraryGetView(GenericGetView):
    """
    Invoked to return the contents of a library.
    """

    def __call__(self):
        # TODO: Should generic get view do this step?
        controller = IPreRenderResponseCacheController(self.request.context)
        controller(self.request.context, {'request': self.request})
        # GenericGetView currently wants to try to turn the context into an ICollection
        # for externalization. We would like to be specific about that here, but
        # that causes problems when we try to find a CacheController for request.context
        # self.request.context = ICollection(self.request.context)
        return super(MainLibraryGetView, self).__call__()


@component.adapter(IContentPackageLibrary)
class _ContentPackageLibraryCacheController(AbstractReliableLastModifiedCacheController):

    # Before the advent of purchasables, there was no way the user
    # could modify his own library. Going through the purchase process
    # took a long time, so we had a 30 to 60 second max_age. Then
    # courses came along, and it was possible to enroll in a bunch of
    # them, one after the other, very quickly, and that max_age caused
    # the UI to not be able to see the new entries. This is unlikely
    # if you expect the user to actually consider what he's enrolling
    # in, but possible. And when it does happen, it's very confusing
    # to the end user and gives a very flaky impression.
    # So currently it is 0 for that use case.
    max_age = 0

    @property
    def _context_specific(self):
        return sorted(x.ntiid for x in self.context.contentPackages)


def _get_hierarchy_context_for_context(obj, top_level_context):
    provider = component.queryMultiAdapter((top_level_context, obj),
                                           IHierarchicalContextProvider)
    if provider is not None:
        results = provider.get_context_paths()
    else:
        results = ((top_level_context,),)
    return results


def _get_board_obj_path(obj):
    """
    For a board level object, return the lineage path.
    """
    # Permissioning concerns? If we have permission
    # on underlying object, we should have permission up the tree.
    result = LocatedExternalList()
    top_level_context = get_top_level_contexts(obj)
    top_level_context = top_level_context[0] if top_level_context else None

    item = obj.__parent__
    result_list = [item]

    # Go up tree until we hit board/blog
    while item is not None:
        if     IBoard.providedBy(item) \
            or IPersonalBlog.providedBy(item):

            if top_level_context is not None:
                result_list.append(top_level_context)
            else:
                result_list.append(item.__parent__)
            item = None
        else:
            item = item.__parent__
            if item is not None:
                result_list.append(item)

    result_list.reverse()
    if result_list and IDeactivatedObject.providedBy(result_list[0]):
        raise hexc.HTTPNotFound()
    result.append(result_list)
    return result


class PreResponseLibraryPathCacheController(object):

    def __call__(self, last_modified, system):
        request = system['request']
        self.remote_user = request.authenticated_userid
        response = request.response
        response.last_modified = last_modified
        obj = object()
        cache_controller = IResponseCacheController(obj)
        # Context is ignored
        return cache_controller(obj, system)


class AbstractCachingLibraryPathView(AbstractAuthenticatedView):
    """
    Handle the caching and 403 response communication for
    LibraryPath views.
    """
    # Max age of 5 minutes, then they need to check with us.
    max_age = 300

    def to_json_body(self, obj):
        result = toExternalObject(toExternalObject(obj))
        result = removed_unserializable(result)
        return result

    def _get_library_path_last_mod(self):
        result = 0
        for library_last_mod in component.subscribers((self.remoteUser,),
                                                      ILibraryPathLastModifiedProvider):
            if library_last_mod is not None:
                result = max(library_last_mod, result)
        return result

    def _get_library_last_mod(self):
        lib = component.queryUtility(IContentPackageLibrary)
        return getattr(lib, 'lastModified', 0)

    @property
    def last_mod(self):
        lib_last_mod = self._get_library_last_mod()
        sub_last_mod = self._get_library_path_last_mod()
        result = max(lib_last_mod, sub_last_mod)
        return result or None

    def do_caching(self, obj):
        setattr(obj, 'lastModified', self.last_mod)
        interface.alsoProvides(obj, IExternalCollection)
        controller = IPreRenderResponseCacheController(obj)
        controller.max_age = self.max_age
        controller(obj, {'request': self.request})

    def pre_caching(self):
        cache_controller = PreResponseLibraryPathCacheController()
        cache_controller(self.last_mod, {'request': self.request})

    def do_call(self, to_call, *args):
        # Try to bail early if our last mod hasn't changed.
        # 4.2016 - This caching may not hold anymore, since items may
        # be published/visible/edited via the API. But with a max
        # age set, it may not be a big deal.
        self.pre_caching()

        # Otherwise, try after we have data.
        try:
            results = to_call(*args)
            self.do_caching(results)
        except ForbiddenContextException as e:
            # It appears we only have top-level-context objects,
            # return a 403 so the client can react appropriately.
            response = hexc.HTTPForbidden()
            result = LocatedExternalDict()
            result[ITEMS] = e.joinable_contexts
            __traceback_info__ = result
            self.do_caching(result)
            response.json_body = self.to_json_body(result)
            results = response
        return results


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=IDataserverFolder,
             name=LIBRARY_PATH_GET_VIEW,
             permission=nauth.ACT_READ,
             request_method='GET')
class _LibraryPathView(AbstractCachingLibraryPathView):
    """
    Return an ordered list of lists of library paths to an object.

    If no such paths exist, we'll return a HTTPForbidden. If we
    are only able to return TopLevelContexts, we will return
    HTTPForbidden, indicating the user can access the content via
    joining the TopLevelContexts.

    Typical return:
            [ [ <TopLevelContext>,
                <Heirarchical Node>,
                <Presentation Asset>,
                <PageInfo>* ],
                ...
            ]

    For authored content, that will not exist in a content package,
    we should simply return the TopLevelContext and outline paths,
    which should be enough for client navigation.
    """

    def _get_path_for_package(self, package, obj, target_ntiid):
        """
        For a given package, return the path to the target ntiid.
        """
        unit = find_interface(obj, IContentUnit, strict=False)
        if unit is not None and not IContentPackage.providedBy(unit):
            # Found a non-content package unit in our lineage.
            return [unit]

        # Try catalog.
        catalog = get_catalog()
        containers = catalog.get_containers(obj) or ()
        for container in containers:
            # Necessary for videos/slides, return the first
            # non-package unit in our index.  These items will
            # show up as embedded in the package. If we might
            # have multiple units here, we could take the longest
            # pathToNtiid from the library to get the leaf node.
            try:
                container = package[container]
                if container is not None and container != package:
                    # In alpha, some packages can access themselves (?)
                    # package[package.ntiid] == package -> True
                    return [container]
            except (KeyError, AttributeError):
                pass

        # Try iterating
        def recur(unit):
            item_ntiid = getattr(unit, 'ntiid', None)
            if     item_ntiid == target_ntiid \
                or target_ntiid in unit.embeddedContainerNTIIDs:
                return [unit]
            for child in unit.children:
                result = recur(child)
                if result:
                    result.append(unit)
                    return result

        results = recur(package)
        if results:
            results.reverse()

        return results

    def _externalize_children(self, units):
        # For content units, we need to externalize as pageinfos.
        results = []
        try:
            # The clients only need the leaf pageinfo. So
            # we start at the end.
            units.reverse()
            for unit in units:
                try:
                    unit_res = find_page_info_view_helper(self.request, unit)
                    results.append(unit_res.json_body)
                    break
                except hexc.HTTPMethodNotAllowed:
                    # Underlying content object, append as-is
                    results.append(unit)
        except hexc.HTTPForbidden:
            # No permission
            pass
        results.reverse()
        return results

    def _do_get_legacy_path_to_id(self, library, container_id):
        # This should hit most UGD on lessons.
        result = library.pathToNTIID(container_id)
        if not result:
            # Now we try embedded, and the first of the results.
            # We
            result = library.pathsToEmbeddedNTIID(container_id)
            result = result[0] if result else result
        return result

    def _get_legacy_path_to_id(self, container_id):
        # In the worst case, we may have to go through the library twice,
        # looking for children and then embedded.
        # TODO: This will not find items contained by other items
        # (e.g. videos, slides, etc).
        library = component.queryUtility(IContentPackageLibrary)
        result = None
        if library:
            result = self._do_get_legacy_path_to_id(library, container_id)
        return result

    def _get_legacy_results(self, obj, target_ntiid):
        """
        We need to iterate through the library, and some paths
        only return the first available result. So we make
        sure we only return a single result for now.
        """
        legacy_path = self._get_legacy_path_to_id(target_ntiid)
        if legacy_path:
            package = legacy_path[0]
            top_level_contexts = get_top_level_contexts_for_user(package,
                                                                 self.remoteUser)
            for top_level_context in top_level_contexts:

                # Bail if our top-level context is not readable.
                if not is_readable(top_level_context):
                    continue
                # We have a hit.
                result_list = [top_level_context]
                if is_readable(package):
                    hierarchy_context = _get_hierarchy_context_for_context(obj,
                                                                           top_level_context)
                    if hierarchy_context:
                        hierarchy_context = hierarchy_context[0]
                    if      hierarchy_context \
                        and isinstance(hierarchy_context, (list, tuple)) \
                        and len(hierarchy_context) > 1:
                        # Drop returned top level context
                        result_list.extend(hierarchy_context[1:])
                    path_list = self._externalize_children(legacy_path)
                    result_list.extend(path_list)
                return result_list

    def _is_content_asset(self, obj):
        # We used to blindly return our content packages
        # for our context, but now, we need to make sure
        # our target is actually in a package (e.g. versus
        # authored through the API).
        records = None
        history = ITransactionRecordHistory(obj, None)
        if history is not None:
            records = history.query(record_type=TRX_TYPE_CREATE)
        return not records

    def _get_content_packages(self, obj, context):
        # If we're an asset, but not a content asset, we will not be
        # found in our course units.
        if      IPresentationAsset.providedBy(obj) \
            and not self._is_content_asset(obj):
            return ()

        if IContentUnit.providedBy(obj):
            # Short circuit and just use the package we have
            # XXX: Global library does not have lineage...
            package = find_interface(obj, IContentPackage, strict=False)
            return (package,)

        try:
            packages = context.ContentPackageBundle.ContentPackages
        except AttributeError:
            try:
                packages = (context.legacy_content_package,)
            except AttributeError:
                try:
                    packages = context.ContentPackages
                except AttributeError:
                    packages = ()
        return packages

    def get_container_context(self, obj):
        """
        Attempt to get the root context from the object itself.
        """
        result = None
        container_context = IContainerContext(obj, None)
        if container_context:
            context_id = container_context.context_id
            result = find_object_with_ntiid(context_id)
        return result

    def _get_path(self, obj, target_ntiid):
        result = LocatedExternalList()
        container_context = self.get_container_context(obj)
        if     IHighlight.providedBy(obj) \
            or IBookmark.providedBy(obj):
            # Now that we have our container context, we need to
            # use that container to find the actual path
            target_ntiid = obj.containerId
            obj = find_object_with_ntiid(target_ntiid)
        hierarchy_contexts = get_hierarchy_context(obj,
                                                   self.remoteUser,
                                                   context=container_context)
        # We have some readings that do not exist in our catalog.
        # We need content units to be indexed.
        for hierarchy_context in hierarchy_contexts:
            # Bail if our top-level context is not readable
            top_level_context = hierarchy_context[0]
            if not is_readable(top_level_context):
                continue
            result_list = list(hierarchy_context)
            packages = self._get_content_packages(obj, top_level_context)

            for package in packages:
                path_list = self._get_path_for_package(package, obj, target_ntiid)
                if path_list and is_readable(package):
                    path_list = self._externalize_children(path_list)
                    result_list.extend(path_list)
                    break
            result.append(result_list)

        # If we have nothing yet, it could mean our object
        # is in legacy content. So we have to look through the library.
        if not result and not hierarchy_contexts:
            logger.info('Iterating through library for library path.')
            result_list = self._get_legacy_results(obj, target_ntiid)
            if result_list:
                result.append(result_list)

        # Not sure how we would cache here, it would have to be by user
        # since we may have user-specific data returned.
        self._sort(result)
        return result

    def _sort(self, result_lists):
        """
        Sorting by the length of the results may generally be good enough.
        Longer paths might indicate full permission down the path tree.
        """
        result_lists.sort(key=lambda x: len(x), reverse=True)

    def _is_visible(self, item):
        """
        Object is published or we're an editor.
        """
        return     not IPublishable.providedBy(item) \
                or item.is_published() \
                or has_permission(nauth.ACT_CONTENT_EDIT, item, self.request)

    def _get_params(self):
        params = CaseInsensitiveDict(self.request.params)
        obj_ntiid = params.get('objectId')
        if obj_ntiid is None or not is_valid_ntiid_string(obj_ntiid):
            raise hexc.HTTPUnprocessableEntity("Invalid ObjectId.")

        obj = find_object_with_ntiid(obj_ntiid)
        if obj is None:
            raise hexc.HTTPNotFound(_('%s not found' % obj_ntiid))
        # See if the reading is no longer visible to our user.
        if      IContentUnit.providedBy(obj) \
            and not self._is_visible( obj ):
            raise hexc.HTTPForbidden(_('Path not accessible.'))

        # Get the ntiid off the object because we may have an OID
        obj_ntiid = getattr(obj, 'ntiid', None) or obj_ntiid
        return obj, obj_ntiid

    def __call__(self):
        obj, object_ntiid = self._get_params()
        if     ITopic.providedBy(obj) \
            or IPost.providedBy(obj) \
            or IForum.providedBy(obj):
            results = self.do_call(_get_board_obj_path, obj)
        else:
            results = self.do_call(self._get_path, obj, object_ntiid)

        # Nothing found, perhaps no longer available.
        if not results:
            results = hexc.HTTPForbidden()
        return results


@view_config(context=IPost)
@view_config(context=ITopic)
@view_config(context=IForum)
@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             name=LIBRARY_PATH_GET_VIEW,
             permission=nauth.ACT_READ,
             request_method='GET')
class _PostLibraryPathView(AbstractCachingLibraryPathView):
    """
    For board items, getting the path traversal can
    be accomplished through lineage.
    """

    def __call__(self):
        return self.do_call(_get_board_obj_path, self.context)


del _content_view_defaults
