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

from nti.app.contentlibrary.utils import role_for_content_package

from nti.cabinet.mixins import SourceFile

from nti.contentlibrary.bundle import PublishableContentPackageBundle

from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.interfaces import IContentPackageBundleLibrary

from nti.contentlibrary.subscribers import sync_bundles_when_library_synched

from nti.dataserver.interfaces import ICommunity
from nti.dataserver.interfaces import IGroupMember

from nti.dataserver.users.communities import Community

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
        admin_bundles = admin_bundles.json_body
        titles = admin_bundles['titles']
        if username.endswith('@nextthought.com'):
            for title in titles:
                self.require_link_href_with_rel(title, VIEW_BUNDLE_GRANT_ACCESS)
                self.require_link_href_with_rel(title, VIEW_BUNDLE_REMOVE_ACCESS)
        return [x['ntiid'] for x in titles]

    @WithSharedApplicationMockDS(users=True, testapp=True)
    def test_restricted_bundles(self):
        """
        Validate our post-sync state, including access. This includes pointing
        to two restricted bundles (RestrictedBundle and RestrictedBundle2) and
        one unrestricted bundle (VisibleBundle). These point to three packages:
        two of which are restricted by acls (PackageB and PackageC) and one
        which is unrestricted (PackageA).
        """
        community_name = 'BundleCommunityTest'
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            Community.create_community(dataserver=self.ds,
                                       username=community_name)
        # Create a regular user and add him to the site community.
        basic_username = 'GeorgeBluth'
        admin_username = 'sjohnson@nextthought.com'
        with mock_dataserver.mock_db_trans(self.ds):
            user = self._create_user(basic_username)
            community = Community.get_community(username=community_name)
            user.record_dynamic_membership(community)
        user_environ = self._make_extra_environ(basic_username)

        # A,B in Visible; B,C in Restricted, C in Restricted2
        visible_ntiid = "tag:nextthought.com,2011-10:NTI-Bundle-VisibleBundle"
        restricted_ntiid = "tag:nextthought.com,2011-10:NTI-Bundle-RestrictedBundle"
        restricted2_ntiid = "tag:nextthought.com,2011-10:NTI-Bundle-RestrictedBundle2"
        package_a_ntiid = "tag:nextthought.com,2011-10:NTI-HTML-PackageA"
        package_b_ntiid = "tag:nextthought.com,2011-10:NTI-HTML-PackageB"
        package_c_ntiid = "tag:nextthought.com,2011-10:NTI-HTML-PackageC"
        all_packages = (package_a_ntiid, package_b_ntiid, package_c_ntiid)

        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            library = component.getUtility(IContentPackageBundleLibrary)
            bundles = tuple(library.getBundles())
            assert_that(bundles, has_length(3))

        # Admin can see all
        admin_bundle_ntiids = self._get_bundle_ntiids(admin_username, None)
        assert_that(admin_bundle_ntiids, contains_inanyorder(visible_ntiid,
                                                             restricted_ntiid,
                                                             restricted2_ntiid))
        for package in all_packages:
            self.testapp.get('/dataserver2/Objects/%s' % package)

        # Regular user cannot view restricted bundles
        # Note they can not view packageB even though it is in a visible ContentBundle;
        # this implies nothing about underlying package access.
        user_bundle_ntiids = self._get_bundle_ntiids(basic_username, user_environ)
        assert_that(user_bundle_ntiids, contains(visible_ntiid))
        self.testapp.get('/dataserver2/Objects/%s' % package_a_ntiid,
                         extra_environ=user_environ)
        for package in (package_b_ntiid, package_c_ntiid):
            self.testapp.get('/dataserver2/Objects/%s' % package,
                             extra_environ=user_environ,
                             status=403)

        # Now grant access to the community for all
        for bundle_ntiid in (restricted_ntiid, restricted2_ntiid, visible_ntiid):
            grant_href = '/dataserver2/ContentBundles/%s/@@%s?user=%s' \
                        % (bundle_ntiid,
                           VIEW_BUNDLE_GRANT_ACCESS,
                           community_name)
            self.testapp.post(grant_href)

        # Both users can see bundles as well as all packages
        for username, environ in ((admin_username, None),
                                  (basic_username, user_environ)):
            bundle_ntiids = self._get_bundle_ntiids(username, environ)
            assert_that(bundle_ntiids,
                        contains_inanyorder(visible_ntiid,
                                            restricted_ntiid,
                                            restricted2_ntiid),
                        username)
            for package in all_packages:
                self.testapp.get('/dataserver2/Objects/%s' % package,
                                 extra_environ=environ)

        # Now restrict access to all except restricted2
        # XXX: Note the visible package status does not change even if
        # remove access; is that what we want?
        for bundle_ntiid in (restricted_ntiid, visible_ntiid):
            remove_href = '/dataserver2/ContentBundles/%s/@@%s?user=%s' \
                        % (bundle_ntiid,
                           VIEW_BUNDLE_REMOVE_ACCESS,
                           community_name)
            self.testapp.post(remove_href)

        admin_bundle_ntiids = self._get_bundle_ntiids(admin_username, None)
        assert_that(admin_bundle_ntiids, contains_inanyorder(visible_ntiid,
                                                             restricted_ntiid,
                                                             restricted2_ntiid))
        for package in all_packages:
            self.testapp.get('/dataserver2/Objects/%s' % package)

        # Regular user cannot view restricted bundle, but can still
        # view packageC, via the still visible restricted2 bundle.
        user_bundle_ntiids = self._get_bundle_ntiids(basic_username, user_environ)
        assert_that(user_bundle_ntiids, contains_inanyorder(visible_ntiid,
                                                            restricted2_ntiid))

        for package in (package_a_ntiid, package_c_ntiid):
            self.testapp.get('/dataserver2/Objects/%s' % package,
                             extra_environ=user_environ)
        self.testapp.get('/dataserver2/Objects/%s' % package_b_ntiid,
                         extra_environ=user_environ,
                         status=403)

        # Now grant access to user to all
        for bundle_ntiid in (restricted_ntiid, restricted2_ntiid, visible_ntiid):
            grant_href = '/dataserver2/ContentBundles/%s/@@%s?user=%s' \
                        % (bundle_ntiid,
                           VIEW_BUNDLE_GRANT_ACCESS,
                           basic_username)
            self.testapp.post(grant_href)

        # User has access to all again
        bundle_ntiids = self._get_bundle_ntiids(basic_username, user_environ)
        assert_that(bundle_ntiids,
                    contains_inanyorder(visible_ntiid,
                                        restricted_ntiid,
                                        restricted2_ntiid))
        for package in all_packages:
            self.testapp.get('/dataserver2/Objects/%s' % package,
                             extra_environ=user_environ)

        # Now restrict access for user from all
        for bundle_ntiid in (restricted_ntiid, visible_ntiid, restricted2_ntiid):
            remove_href = '/dataserver2/ContentBundles/%s/@@%s?user=%s' \
                        % (bundle_ntiid,
                           VIEW_BUNDLE_REMOVE_ACCESS,
                           basic_username)
            self.testapp.post(remove_href)

        # Still has access to RestrictedBundle2 and PackageC via community
        user_bundle_ntiids = self._get_bundle_ntiids(basic_username, user_environ)
        assert_that(user_bundle_ntiids, contains_inanyorder(visible_ntiid,
                                                            restricted2_ntiid))

        for package in (package_a_ntiid, package_c_ntiid):
            self.testapp.get('/dataserver2/Objects/%s' % package,
                             extra_environ=user_environ)
        self.testapp.get('/dataserver2/Objects/%s' % package_b_ntiid,
                         extra_environ=user_environ,
                         status=403)


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
            package_role = role_for_content_package(package)
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
            package_role = role_for_content_package(package)
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
                source = SourceFile(name="assets.zip", data=fp.read())
            mock_src.is_callable().with_args().returns({"assets.zip":source})
            href = '/dataserver2/ContentBundles'
            bundle = PublishableContentPackageBundle(title=u'Bleach',
                                                     description=u'Manga bleach',
                                                     RestrictedAccess=True)
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
