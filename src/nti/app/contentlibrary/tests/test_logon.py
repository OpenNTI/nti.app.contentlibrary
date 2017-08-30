#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import contains
from hamcrest import has_length
from hamcrest import assert_that

from zope import component

from nti.app.contentlibrary.logon import update_users_content_roles

from nti.dataserver import authorization as nauth

from nti.dataserver.interfaces import IGroupMember

from nti.dataserver.users.users import User

from nti.app.contentlibrary.tests import ExLibraryApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.dataserver.tests.mock_dataserver import WithMockDSTrans


class TestLogonViews(ApplicationLayerTest):

    layer = ExLibraryApplicationTestLayer

    @WithMockDSTrans
    def test_update_provider_content_access_not_in_library(self):
        user = User.create_user(self.ds, 
                                username=u'jason.madden@nextthought.com', 
                                password=u'temp001')
        content_roles = component.getAdapter(user, IGroupMember, 
                                             nauth.CONTENT_ROLE_PREFIX)
        # initially empty
        assert_that(list(content_roles.groups), is_([]))

        # add some from this provider
        idurl = 'http://openid.nextthought.com/jmadden'
        local_roles = ('ABCD',)
        update_users_content_roles(user, idurl, local_roles)
        assert_that(content_roles.groups, 
                    contains(*[nauth.role_for_providers_content('nextthought', x) for x in local_roles]))

        # add some more from this provider
        local_roles += ('DEFG',)
        update_users_content_roles(user, idurl, local_roles)

        assert_that(content_roles.groups, 
                    contains(*[nauth.role_for_providers_content('nextthought', x) for x in local_roles]))

        # Suppose that this user has some other roles too from a different
        # provider
        aops_roles = [nauth.role_for_providers_content('aops', '1234')]
        complete_roles = aops_roles + \
            [nauth.role_for_providers_content('nextthought', x) for x in local_roles]
        assert_that(complete_roles, has_length(3))
        content_roles.setGroups(complete_roles)

        # If we update NTI again...
        update_users_content_roles(user, idurl, local_roles)
        # nothing changes.
        assert_that(content_roles.groups, contains(*complete_roles))

        # We can change up the NTI roles...
        local_roles = ('HIJK',)
        update_users_content_roles(user, idurl, local_roles)
        complete_roles = aops_roles + \
            [nauth.role_for_providers_content('nextthought', x) for x in local_roles]
        # and the aops roles are intact
        assert_that(complete_roles, has_length(2))
        assert_that(content_roles.groups, contains(*complete_roles))

        # We can remove the NTI roles
        update_users_content_roles(user, idurl, None)
        # leaving the other roles behind
        assert_that(content_roles.groups, contains(*aops_roles))

    @WithMockDSTrans
    def test_update_provider_content_access_in_library(self):
        # """If we supply the title of a work, the works actual NTIID gets used."""
        # There are two things with the same title in the library, but different ntiids
        # label="COSMETOLOGY" ntiid="tag:nextthought.com,2011-10:MN-HTML-MiladyCosmetology.cosmetology"
        # label="COSMETOLOGY"
        # ntiid="tag:nextthought.com,2011-10:MN-HTML-uncensored.cosmetology"

        user = User.create_user(self.ds, 
                                username=u'jason.madden@nextthought.com', 
                                password=u'temp001')
        content_roles = component.getAdapter(user, IGroupMember, 
                                             nauth.CONTENT_ROLE_PREFIX)

        # initially empty
        assert_that(list(content_roles.groups), is_([]))

        # Provider of course has to match
        idurl = 'http://openid.mn.com/jmadden'
        # The role is the title of the work
        local_roles = ('cosmetology',)

        update_users_content_roles(user, idurl, local_roles)
        assert_that(content_roles.groups, 
                    contains(nauth.role_for_providers_content('mn', 'MiladyCosmetology.cosmetology'),
                             nauth.role_for_providers_content('mn', 'Uncensored.cosmetology')))
