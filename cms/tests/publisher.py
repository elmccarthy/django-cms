# -*- coding: utf-8 -*-
from __future__ import with_statement
from cms.api import create_page, add_plugin
from cms.management.commands import publisher_publish
from cms.models import CMSPlugin
from cms.models.pagemodel import Page
from cms.test_utils.testcases import CMSTestCase
from cms.test_utils.util.context_managers import (SettingsOverride,
    StdoutOverride)
from django.contrib.auth.models import User
from django.core.management.base import CommandError


class PublisherTests(CMSTestCase):
    """
    A test case to exercise publisher
    """
    
    def test_simple_publisher(self):
        """
        Creates the stuff needed for these tests.
        Please keep this up-to-date (the docstring!)

                A
               / \
              B  C
        """
        # Create a simple tree of 3 pages
        pageA = create_page("Page A", "nav_playground.html", "en",
                            published= True, in_navigation= True)
        pageB = create_page("Page B", "nav_playground.html", "en", 
                            parent=pageA, published=True, in_navigation=True)
        pageC = create_page("Page C", "nav_playground.html", "en",
                            parent=pageA, published=False, in_navigation=True)
        # Assert A and B are published, C unpublished
        self.assertTrue(pageA.published)
        self.assertTrue(pageB.published)
        self.assertTrue(not pageC.published)
        self.assertTrue(len(Page.objects.published()), 2)
        
        # Let's publish C now.
        pageC.publish()
        
        # Assert all are published
        self.assertTrue(pageA.published)
        self.assertTrue(pageB.published)
        self.assertTrue(pageC.published)
        self.assertTrue(len(Page.objects.published()), 3)
        
    def test_command_line_should_raise_without_superuser(self):
        raised = False
        try:
            com = publisher_publish.Command()
            com.handle_noargs()
        except CommandError:
            raised = True
        self.assertTrue(raised)

    def test_command_line_publishes_zero_pages_on_empty_db(self):
        # we need to create a superuser (the db is empty)
        User.objects.create_superuser('djangocms', 'cms@example.com', '123456')
        
        pages_from_output = 0
        published_from_output = 0
        
        with StdoutOverride() as buffer:
            # Now we don't expect it to raise, but we need to redirect IO
            com = publisher_publish.Command()
            com.handle_noargs()
            lines = buffer.getvalue().split('\n') #NB: readlines() doesn't work
            
        for line in lines:
            if 'Total' in line:
                pages_from_output = int(line.split(':')[1])
            elif 'Published' in line:
                published_from_output = int(line.split(':')[1])
                
        self.assertEqual(pages_from_output,0)
        self.assertEqual(published_from_output,0)

    def test_command_line_ignores_draft_page(self):
        # we need to create a superuser (the db is empty)
        User.objects.create_superuser('djangocms', 'cms@example.com', '123456')

        create_page("The page!", "nav_playground.html", "en", published=False,
                    in_navigation=True)

        pages_from_output = 0
        published_from_output = 0

        with StdoutOverride() as buffer:
            # Now we don't expect it to raise, but we need to redirect IO
            com = publisher_publish.Command()
            com.handle_noargs()
            lines = buffer.getvalue().split('\n') #NB: readlines() doesn't work

        for line in lines:
            if 'Total' in line:
                pages_from_output = int(line.split(':')[1])
            elif 'Published' in line:
                published_from_output = int(line.split(':')[1])

        self.assertEqual(pages_from_output,0)
        self.assertEqual(published_from_output,0)

        self.assertEqual(Page.objects.public().count(), 0)

    def test_command_line_publishes_one_page(self):
        """
        Publisher always creates two Page objects for every CMS page,
        one is_draft and one is_public.

        The public version of the page can be either published or not.

        This bit of code uses sometimes manager methods and sometimes manual
        filters on purpose (this helps test the managers)
        """
        # we need to create a superuser (the db is empty)
        User.objects.create_superuser('djangocms', 'cms@example.com', '123456')
        
        # Now, let's create a page. That actually creates 2 Page objects
        create_page("The page!", "nav_playground.html", "en", published=True, 
                    in_navigation=True)
        draft = Page.objects.drafts()[0]
        draft.reverse_id = 'a_test' # we have to change *something*
        draft.save()
        
        pages_from_output = 0
        published_from_output = 0
        
        with StdoutOverride() as buffer:
            # Now we don't expect it to raise, but we need to redirect IO
            com = publisher_publish.Command()
            com.handle_noargs()
            lines = buffer.getvalue().split('\n') #NB: readlines() doesn't work
            
        for line in lines:
            if 'Total' in line:
                pages_from_output = int(line.split(':')[1])
            elif 'Published' in line:
                published_from_output = int(line.split(':')[1])
                
        self.assertEqual(pages_from_output,1)
        self.assertEqual(published_from_output,1)
        # Sanity check the database (we should have one draft and one public)
        not_drafts = len(Page.objects.filter(publisher_is_draft=False))
        drafts = len(Page.objects.filter(publisher_is_draft=True))
        self.assertEquals(not_drafts,1)
        self.assertEquals(drafts,1)
        
        # Now check that the non-draft has the attribute we set to the draft.
        non_draft = Page.objects.public()[0]
        self.assertEquals(non_draft.reverse_id, 'a_test')
        
    def test_unpublish(self):
        page = create_page("Page", "nav_playground.html", "en", published=True,
                           in_navigation=True)
        self.assertEqual(Page.objects.filter(title_set__title="Page").count(), 2)

        page.unpublish()
        self.assertEqual(page.published, False)
        self.assertObjectDoesNotExist(Page.objects.public(), title_set__title="Page")
        self.assertEqual(Page.objects.filter(title_set__title="Page").count(), 1)

        page.publish()
        self.assertEqual(page.published, True)
        self.assertObjectExist(Page.objects.public(), title_set__title="Page")
        self.assertEqual(Page.objects.filter(title_set__title="Page").count(), 2)

    def test_revert_contents(self):
        user = self.get_superuser()
        page = create_page("Page", "nav_playground.html", "en", published=True,
                           created_by=user)
        placeholder = page.placeholders.get(slot=u"body")
        deleted_plugin = add_plugin(placeholder, u"TextPlugin", u"en", body="Deleted content")
        text_plugin = add_plugin(placeholder, u"TextPlugin", u"en", body="Public content")
        page.publish()

        # Modify and delete plugins
        text_plugin.body = "<p>Draft content</p>"
        text_plugin.save()
        deleted_plugin.delete()
        self.assertEquals(CMSPlugin.objects.count(), 3)

        # Now let's revert and restore
        page.revert()
        self.assertEquals(page.publisher_state, Page.PUBLISHER_STATE_DEFAULT)
        self.assertEquals(page.pagemoderatorstate_set.count(), 0)

        self.assertEquals(CMSPlugin.objects.count(), 4)
        plugins = CMSPlugin.objects.filter(placeholder__page=page)
        self.assertEquals(plugins.count(), 2)

        plugins = [plugin.get_plugin_instance()[0] for plugin in plugins]
        self.assertEquals(plugins[0].body, "Deleted content")
        self.assertEquals(plugins[1].body, "Public content")

    def test_revert_move(self):
        parent = create_page("Parent", "nav_playground.html", "en", published=True)
        parent_url = parent.get_absolute_url()
        page = create_page("Page", "nav_playground.html", "en", published=True,
                           parent=parent)
        other = create_page("Other", "nav_playground.html", "en", published=True)
        other_url = other.get_absolute_url()

        child = create_page("Child", "nav_playground.html", "en", published=True,
                            parent=page)
        self.assertEqual(page.get_absolute_url(), parent_url + "page/")
        self.assertEqual(child.get_absolute_url(), parent_url + "page/child/")

        # Now let's move it (and the child)
        page.move_page(other)
        page = self.reload(page)
        child = self.reload(child)
        self.assertEqual(page.get_absolute_url(), other_url + "page/")
        self.assertEqual(child.get_absolute_url(), other_url + "page/child/")
        # Public version is still in the same url
        self.assertEqual(page.publisher_public.get_absolute_url(), parent_url + "page/")
        self.assertEqual(child.publisher_public.get_absolute_url(), parent_url + "page/child/")

        # Use revert to bring things back to normal
        page.revert()
        page = self.reload(page)
        child = self.reload(child)
        self.assertEqual(page.get_absolute_url(), other_url + "page/")
        self.assertEqual(child.get_absolute_url(), other_url + "page/child/")

    def test_publish_works_with_descendants(self):
        """
        For help understanding what this tests for, see:
        http://articles.sitepoint.com/print/hierarchical-data-database

        Creates this published structure:
                            home
                          /      \
                       item1   item2
                              /     \
                         subitem1 subitem2
        """
        home_page = create_page("home", "nav_playground.html", "en",
                                published=True, in_navigation=False)
            
        create_page("item1", "nav_playground.html", "en", parent=home_page,
                    published=True)
        item2 = create_page("item2", "nav_playground.html", "en", parent=home_page,
                            published=True)

        create_page("subitem1", "nav_playground.html", "en", parent=item2,
                    published=True)
        create_page("subitem2", "nav_playground.html", "en", parent=item2,
                    published=True)
            
        not_drafts = list(Page.objects.filter(publisher_is_draft=False).order_by('lft'))
        drafts = list(Page.objects.filter(publisher_is_draft=True).order_by('lft'))
        
        self.assertEquals(len(not_drafts), 5)
        self.assertEquals(len(drafts), 5)
        
        for idx, draft in enumerate(drafts):
            public = not_drafts[idx]
            # Check that a node doesn't become a root node magically
            self.assertEqual(bool(public.parent_id), bool(draft.parent_id))
            if public.parent :
                # Let's assert the MPTT tree is consistent
                self.assertTrue(public.lft > public.parent.lft)
                self.assertTrue(public.rght < public.parent.rght)
                self.assertEquals(public.tree_id, public.parent.tree_id)
                self.assertTrue(public.parent in public.get_ancestors())
                self.assertTrue(public in public.parent.get_descendants())
                self.assertTrue(public in public.parent.get_children())
            if draft.parent:
                # Same principle for the draft tree
                self.assertTrue(draft.lft > draft.parent.lft)
                self.assertTrue(draft.rght < draft.parent.rght)
                self.assertEquals(draft.tree_id, draft.parent.tree_id)
                self.assertTrue(draft.parent in draft.get_ancestors())
                self.assertTrue(draft in draft.parent.get_descendants())
                self.assertTrue(draft in draft.parent.get_children())

        # Now call publish again. The structure should not change.
        item2.publish()
            
        not_drafts = list(Page.objects.filter(publisher_is_draft=False).order_by('lft'))
        drafts = list(Page.objects.filter(publisher_is_draft=True).order_by('lft'))
        
        self.assertEquals(len(not_drafts), 5)
        self.assertEquals(len(drafts), 5)

        for idx, draft in enumerate(drafts):
            public = not_drafts[idx]
            # Check that a node doesn't become a root node magically
            self.assertEqual(bool(public.parent_id), bool(draft.parent_id))
            if public.parent :
                # Let's assert the MPTT tree is consistent
                self.assertTrue(public.lft > public.parent.lft)
                self.assertTrue(public.rght < public.parent.rght)
                self.assertEquals(public.tree_id, public.parent.tree_id)
                self.assertTrue(public.parent in public.get_ancestors())
                self.assertTrue(public in public.parent.get_descendants())
                self.assertTrue(public in public.parent.get_children())
            if draft.parent:
                # Same principle for the draft tree
                self.assertTrue(draft.lft > draft.parent.lft)
                self.assertTrue(draft.rght < draft.parent.rght)
                self.assertEquals(draft.tree_id, draft.parent.tree_id)
                self.assertTrue(draft.parent in draft.get_ancestors())
                self.assertTrue(draft in draft.parent.get_descendants())
                self.assertTrue(draft in draft.parent.get_children())

