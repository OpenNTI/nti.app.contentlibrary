#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import not_none

from nti.app.contentlibrary.forum import ContentForum
from nti.app.contentlibrary.forum import ContentBoard
from nti.app.contentlibrary.forum import ContentHeadlineTopic

from  nti.app.contentlibrary.tests import ContentLibraryApplicationTestLayer

from nti.app.forums.tests.base_forum_testing import AbstractTestApplicationForumsBaseMixin

from nti.app.testing.application_webtest import ApplicationLayerTest

_FORUM_NAME = ContentForum.__default_name__
_BOARD_NAME = ContentBoard.__default_name__

class TestApplicationBundlesForum(AbstractTestApplicationForumsBaseMixin,ApplicationLayerTest):
	__test__ = True

	layer = ContentLibraryApplicationTestLayer

	extra_environ_default_user = AbstractTestApplicationForumsBaseMixin.default_username
	default_community = 'TheCommunity'
	default_entityname = default_community
	
	# default_community = 'zope.security.management.system_user'
	# default_entityname = default_community
	forum_url_relative_to_user = _BOARD_NAME + '/' + _FORUM_NAME

	board_ntiid = None
	board_ntiid_checker = not_none()
	board_content_type = None

	forum_ntiid = None
	forum_topic_ntiid_base = None

	forum_content_type = 'application/vnd.nextthought.forums.contentforum+json'
	forum_headline_class_type = 'Post'
	forum_topic_content_type = None
	board_link_rel = forum_link_rel = _BOARD_NAME
	forum_title = _FORUM_NAME
	forum_type = ContentForum

	forum_topic_comment_content_type = 'application/vnd.nextthought.forums.contentforumcomment+json'

	check_sharedWith_community = False

	def setUp( self ):
		super(TestApplicationBundlesForum,self).setUp()
		self.forum_pretty_url = '/dataserver2/%2B%2Betc%2B%2Bbundles/bundles/tag%3Anextthought.com%2C2011-10%3ANTI-Bundle-ABundle/DiscussionBoard/Forum'
		self.forum_pretty_contents_url = self.forum_pretty_url + '/contents'
		self.board_pretty_url = self.forum_pretty_url[:-(len(_FORUM_NAME) + 1)]

		self.board_content_type = ContentBoard.mimeType + '+json'
		self.forum_topic_content_type = ContentHeadlineTopic.mimeType + '+json'

		self.forum_ntiid_url = None

	def test_user_can_POST_new_forum_entry_resulting_in_blog_being_sublocation( self ):
		pass # not applicable

	def _get_board_href_via_rel(self):
		# XXX: Where is the board decorated? On the bundle, right?
		return self.board_pretty_url
