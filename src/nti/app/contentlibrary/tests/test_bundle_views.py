#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import none
from hamcrest import is_not
from hamcrest import not_none
from hamcrest import has_item
from hamcrest import contains
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import has_property
from hamcrest import contains_inanyorder
does_not = is_not

import os
import shutil
import tempfile

import fudge

from zope import component

from zope.intid.interfaces import IIntIds

from nti.app.contentlibrary import VIEW_BUNDLE_GRANT_ACCESS
from nti.app.contentlibrary import VIEW_BUNDLE_REMOVE_ACCESS

from nti.app.contentlibrary.interfaces import IContentBoard

from nti.app.contentlibrary.utils import get_package_role

from nti.cabinet.mixins import SourceFile

from nti.contentlibrary.bundle import PublishableContentPackageBundle

from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.interfaces import IContentPackageBundleLibrary

from nti.contentlibrary.subscribers import sync_bundles_when_library_synched

from nti.dataserver.users.communities import Community

from nti.dataserver.interfaces import ICommunity
from nti.dataserver.interfaces import IGroupMember

from nti.externalization.externalization import to_external_object

from nti.externalization.proxy import removeAllProxies

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.app.contentlibrary.tests import PersistentApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.dataserver.tests import mock_dataserver


class TestBundleViews(ApplicationLayerTest):

    layer = PersistentApplicationTestLayer
    default_origin = 'http://platform.ou.edu'

    pkg_ntiid = u'tag:nextthought.com,2011-10:OU-HTML-CS1323_F_2015_Intro_to_Computer_Programming.introduction_to_computer_programming'

    def presentation_assets_zip(self, tmpdir=None):
        tmpdir = tmpdir or tempfile.mkdtemp()
        outfile = os.path.join(tmpdir, "assets")
        path = os.path.join(os.path.dirname(__file__),
                            "presentation-assets")
        return shutil.make_archive(outfile, "zip", path)

    def _sync(self):
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            library = component.getUtility(IContentPackageLibrary)
            sync_bundles_when_library_synched(library, None)

    def _get_entity_groups(self, entity):
        result = set()
        for _, adapter in component.getAdapters((entity,), IGroupMember):
            result.update(adapter.groups)
        return result

    def _get_bundle_ntiids(self, username, environ):
        bundle_href = '/dataserver2/users/%s/ContentBundles/VisibleContentBundles' % username
        admin_bundles = self.testapp.get(bundle_href, extra_environ=environ)
        return [x['ntiid'] for x in admin_bundles.json_body['titles']]

    @WithSharedApplicationMockDS(users=True, testapp=True)
    def test_library_restricted(self):
        """
        Validate our post-sync state, including access.
        """
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            Community.create_community(dataserver=self.ds,
                                       username='ou.nextthought.com')
        # Create a regular user and add him to the site community.
        basic_username = 'GeorgeBluth'
        admin_username = 'sjohnson@nextthought.com'
        with mock_dataserver.mock_db_trans(self.ds):
            user = self._create_user(basic_username)
            community = Community.get_community(username='ou.nextthought.com')
            user.record_dynamic_membership(community)
        user_environ = self._make_extra_environ(basic_username)

        visible_ntiid = "tag:nextthought.com,2011-10:NTI-Bundle-VisibleBundle"
        restricted_ntiid = "tag:nextthought.com,2011-10:NTI-Bundle-RestrictedBundle"

        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            library = component.getUtility(IContentPackageBundleLibrary)
            bundles = tuple(library.getBundles())
            assert_that(bundles, has_length(2))

        # Admin can see all
        admin_bundle_ntiids = self._get_bundle_ntiids(admin_username, None)
        assert_that(admin_bundle_ntiids, contains_inanyorder(visible_ntiid,
                                                             restricted_ntiid))

        # Regular user cannot view restricted bundles
        user_bundle_ntiids = self._get_bundle_ntiids(basic_username, user_environ)
        assert_that(user_bundle_ntiids, contains(visible_ntiid))

        # Now grant access for both
        for bundle_ntiid in (restricted_ntiid, visible_ntiid):
            grant_href = '/dataserver2/ContentBundles/%s/@@%s' \
                        % (bundle_ntiid, VIEW_BUNDLE_GRANT_ACCESS)
            self.testapp.post(grant_href)

        for username, environ in ((admin_username, None),
                                  (basic_username, user_environ)):
            bundle_ntiids = self._get_bundle_ntiids(username, environ)
            assert_that(bundle_ntiids,
                        contains_inanyorder(visible_ntiid,
                                            restricted_ntiid),
                        username)

        # Now restrict access to both
        # XXX: Note the visible package status does not change
        # Is that what we want?
        for bundle_ntiid in (restricted_ntiid, visible_ntiid):
            grant_href = '/dataserver2/ContentBundles/%s/@@%s' \
                        % (bundle_ntiid, VIEW_BUNDLE_REMOVE_ACCESS)
            self.testapp.post(grant_href)

        admin_bundle_ntiids = self._get_bundle_ntiids(admin_username, None)
        assert_that(admin_bundle_ntiids, contains_inanyorder(visible_ntiid,
                                                             restricted_ntiid))

        # Regular user cannot view restricted bundles
        user_bundle_ntiids = self._get_bundle_ntiids(basic_username, user_environ)
        assert_that(user_bundle_ntiids, contains(visible_ntiid))


    def _test_access(self, ntiid):
        """
        Validate granting/removing access to bundle. Multiple calls work
        correctly.
        """
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            Community.create_community(dataserver=self.ds,
                                       username='ou.nextthought.com')
        # Grant community access
        grant_href = '/dataserver2/ContentBundles/%s/@@%s' \
                     % (ntiid, VIEW_BUNDLE_GRANT_ACCESS)
        self.testapp.post(grant_href)
        self.testapp.post(grant_href)
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            package = find_object_with_ntiid(self.pkg_ntiid)
            package_role = get_package_role(package)
            community = Community.get_community('ou.nextthought.com')
            groups = self._get_entity_groups(community)
            assert_that(groups, has_item(package_role))

        # Remove community access
        remove_href = '/dataserver2/ContentBundles/%s/@@%s' \
                      % (ntiid, VIEW_BUNDLE_REMOVE_ACCESS)
        self.testapp.post(remove_href)
        self.testapp.post(remove_href)
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            package = find_object_with_ntiid(self.pkg_ntiid)
            package_role = get_package_role(package)
            community = Community.get_community('ou.nextthought.com')
            groups = self._get_entity_groups(community)
            assert_that(groups, does_not(has_item(package_role)))

    @WithSharedApplicationMockDS(users=True, testapp=True)
    @fudge.patch('nti.app.contentlibrary.views.bundle_views.get_all_sources')
    def test_create_and_publish_bundle(self, mock_src):
        tmpdir = tempfile.mkdtemp()
        bundle_path_part = None
        try:
            path = self.presentation_assets_zip(tmpdir)
            with open(path, "rb") as fp:
                source = SourceFile("assets.zip", fp.read())
            mock_src.is_callable().with_args().returns({"assets.zip":source})
            href = '/dataserver2/ContentBundles'
            bundle = PublishableContentPackageBundle(title=u'Bleach',
                                                     description=u'Manga bleach')
            ext_obj = to_external_object(bundle)
            ext_obj.pop('NTIID', None)
            ext_obj.pop('ntiid', None)
            ext_obj['ContentPackages'] = [self.pkg_ntiid]

            res = self.testapp.post_json(href, ext_obj, status=201)
            assert_that(res.json_body, has_entry('OID', is_not(none())))
            assert_that(res.json_body, has_entry('NTIID', is_not(none())))
            assert_that(res.json_body, has_entry('title', is_('Bleach')))
            ntiid = res.json_body['NTIID']

            with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
                bundle = find_object_with_ntiid(ntiid)
                assert_that(bundle,
                            has_property('root', is_(none())))
                assert_that(bundle,
                            has_property('_presentation_assets', is_not(none())))

                community = ICommunity(bundle, None)
                assert_that(community, is_not(none()))

            href = '/dataserver2/ContentBundles/%s/@@publish' % ntiid
            self.testapp.post(href, status=200)
            with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
                bundle = find_object_with_ntiid(ntiid)
                assert_that(bundle,
                            has_property('root', is_not(none())))

                board = IContentBoard(bundle, None)
                assert_that(board, is_not(none()))
                # Disk folder
                intids = component.getUtility(IIntIds)
                bundle_path_part = intids.getId(removeAllProxies(bundle))
                assert_that(bundle_path_part, not_none())
                bundle_path_part = str(bundle_path_part)

            self._test_access(ntiid)
        finally:
            if bundle_path_part:
                new_bundle = os.path.join(self.layer.library_path,
                                          'sites',
                                          'platform.ou.edu',
                                          'ContentPackageBundles',
                                          bundle_path_part)
                shutil.rmtree(new_bundle, ignore_errors=True)
            shutil.rmtree(tmpdir, ignore_errors=True)

