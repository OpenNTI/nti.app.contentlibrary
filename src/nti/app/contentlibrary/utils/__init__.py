#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import six
import collections
from six.moves import urllib_parse

from zope import component

from nti.contentlibrary.interfaces import IContentUnit
from nti.contentlibrary.interfaces import IContentPackage
from nti.contentlibrary.interfaces import IGlobalContentPackage
from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.dataserver.authorization import CONTENT_ROLE_PREFIX
from nti.dataserver.authorization import role_for_providers_content

from nti.dataserver.interfaces import IRole
from nti.dataserver.interfaces import IMutableGroupMember

from nti.mimetype.mimetype import nti_mimetype_with_class

from nti.ntiids.ntiids import get_parts
from nti.ntiids.ntiids import get_provider
from nti.ntiids.ntiids import get_specific
from nti.ntiids.ntiids import find_object_with_ntiid

PAGE_INFO_MT = nti_mimetype_with_class('pageinfo')
PAGE_INFO_MT_JSON = PAGE_INFO_MT + '+json'

CONTENT_BUNDLE_ROLE_PREFIX = 'content-bundle-role:'

logger = __import__('logging').getLogger(__name__)


def _encode(s):
    return s.encode('utf-8') if isinstance(s, six.text_type) else s


def find_page_info_view_helper(request, page_ntiid_or_content_unit):
    """
    Helper function to resolve a NTIID to PageInfo.
    """

    # XXX Assuming one location in the hierarchy, plus assuming things
    # about the filename For the sake of the application (trello #932
    # https://trello.com/c/5cxwEgVH), if the question is nested in a
    # sub-section of a content library, we want to return the PageInfo
    # for the nearest containing *physical* file. In short, this means
    # we look for an href that does not have a '#' in it.
    if not IContentUnit.providedBy(page_ntiid_or_content_unit):
        content_unit = find_object_with_ntiid(page_ntiid_or_content_unit)
    else:
        content_unit = page_ntiid_or_content_unit

    while content_unit and '#' in getattr(content_unit, 'href', ''):
        content_unit = getattr(content_unit, '__parent__', None)

    page_ntiid = u''
    if content_unit:
        page_ntiid = content_unit.ntiid
    elif isinstance(page_ntiid_or_content_unit, basestring):
        page_ntiid = page_ntiid_or_content_unit

    # Rather than redirecting to the canonical URL for the page, request it
    # directly. This saves a round trip, and is more compatible with broken clients that
    # don't follow redirects parts of the request should be native strings,
    # which under py2 are bytes. Also make sure we pass any params to
    # subrequest
    path = '/dataserver2/Objects/' + _encode(page_ntiid)
    if request.query_string:
        path += '?' + _encode(request.query_string)

    # set subrequest
    subrequest = request.blank(path)
    subrequest.method = 'GET'
    subrequest.possible_site_names = request.possible_site_names
    # prepare environ
    subrequest.environ['REMOTE_USER'] = request.environ['REMOTE_USER']
    subrequest.environ['repoze.who.identity'] = request.environ['repoze.who.identity'].copy()
    for k in request.environ:
        if k.startswith('paste.') or k.startswith('HTTP_'):
            if k not in subrequest.environ:
                subrequest.environ[k] = request.environ[k]
    subrequest.accept = PAGE_INFO_MT_JSON

    # invoke
    result = request.invoke_subrequest(subrequest)
    return result


def yield_sync_content_packages(ntiids=()):
    library = component.getUtility(IContentPackageLibrary)
    if not ntiids:
        for package in library.contentPackages:
            if not IGlobalContentPackage.providedBy(package):
                yield package
    else:
        for ntiid in ntiids:
            obj = find_object_with_ntiid(ntiid)
            package = IContentPackage(obj, None)
            if package is None:
                logger.error("Could not find package with NTIID %s", ntiid)
            elif not IGlobalContentPackage.providedBy(package):
                yield package
yield_content_packages = yield_sync_content_packages


def update_users_content_roles(user, idurl, content_roles):
    """
    Update the content roles assigned to the given user based on information
    returned from an external provider.

    :param user: The user object
    :param idurl: The URL identifying the user on the external system. All
            content roles we update will be based on this idurl; in particular, we assume
            that the base hostname of the URL maps to a NTIID ``provider``, and we will
            only add/remove roles from this provider. For example, ``http://openid.primia.org/username``
            becomes the provider ``prmia.``
    :param iterable content_roles: An iterable of strings naming provider-local
            content roles. If empty/None, then the user will be granted no roles
            from the provider of the ``idurl``; otherwise, the content roles from the given
            ``provider`` will be updated to match. The local roles can be the exact (case-insensitive) match
            for the title of a work, and the user will be granted access to the derived NTIID for the work
            whose title matches. Otherwise (no title match), the user will be granted direct access
            to the role as given.
    """
    member = component.getAdapter(user,
                                  IMutableGroupMember,
                                  CONTENT_ROLE_PREFIX)
    if not content_roles and not member.hasGroups():
        return  # No-op

    # http://x.y.z.nextthought.com/openid => nextthought
    provider = urllib_parse.urlparse(idurl).netloc.split('.')[-2]
    provider = provider.lower()

    empty_role = role_for_providers_content(provider, '')

    # Delete all of our provider's roles, leaving everything else intact
    other_provider_roles = [
        x for x in member.groups if not x.id.startswith(empty_role.id)
    ]
    # Create new roles for what they tell us
    # NOTE: At this step here we may need to map from external provider identifiers (stock numbers or whatever)
    # to internal NTIID values. Somehow. Searching titles is one way to ease
    # that

    library = component.queryUtility(IContentPackageLibrary)

    roles_to_add = []
    # Set up a map from title to list-of specific-parts-of-ntiids for all
    # content from this provider
    provider_packages = collections.defaultdict(list)
    for package in (library.contentPackages if library is not None else ()):
        if get_provider(package.ntiid).lower() == provider:
            key = package.title.lower()
            provider_packages[key].append(get_specific(package.ntiid))

    for local_role in (content_roles or ()):
        local_role = local_role.lower()
        if local_role in provider_packages:
            for specific in provider_packages[local_role]:
                roles_to_add.append(
                    role_for_providers_content(provider, specific)
                )
        else:
            roles_to_add.append(
                role_for_providers_content(provider, local_role)
            )
    # set groups
    member.setGroups(other_provider_roles + roles_to_add)
_update_users_content_roles = update_users_content_roles  # BWC


def role_for_content_package(package):
    """
    For an IContentPackage, return an IRole.
    """
    ntiid = package.ntiid
    ntiid = get_parts(ntiid)
    provider = ntiid.provider
    specific = ntiid.specific
    return role_for_providers_content(provider, specific)
get_package_role = role_for_content_package # BWC


def role_for_content_bundle(bundle):
    """
    Create an IRole for access to this :class:`IContentPackageBundle
    provided by the given ``provider`` and having the local (specific)
    part of an NTIID matching ``local_part``.
    """
    ntiid = bundle.ntiid
    ntiid = get_parts(ntiid)
    provider = ntiid.provider
    specific = ntiid.specific
    val = '%s%s:%s' % (CONTENT_BUNDLE_ROLE_PREFIX,
                       provider.lower(), specific.lower())
    return IRole(val)
