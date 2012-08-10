#! /usr/bin/python

import time
import re
import datetime
import json

# non stdlib external
import wikitools

class WikiHandler():
    def __init__(self, apiURL, username, password):
        self.apiURL = apiURL
        self.username = username
        self.password = password
        self.lastTimestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        
    def connect(self):
        self.wiki = wikitools.Wiki(self.apiURL)
        self.wiki.login(self.username, self.password)
        
    def recentChanges(self):
        
        if not self.lastTimestamp:
            self.lastTimestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        
        params = {'action' : 'query',
                  'list'   : 'recentchanges',
                  'rclimit': '25',
                  'rcstart': self.lastTimestamp,
                  'rcdir'  : 'newer',
                  'rcprop' : 'user|timestamp|title|comment|loginfo'
                  }
    
        response = wikitools.APIRequest(self.wiki, params).query(querycontinue = False)
        recentChanges = response['query']['recentchanges']
        if recentChanges:
            self.lastTimestamp = self.newTimeStamp(recentChanges[len(recentChanges)-1]['timestamp'])

        return [self.makeMessage(change) for change in recentChanges]

    def pageText(self, title):
        try:
            page = wikitools.Page(title)
            response = page.getWikiText()
            return response
        except wikitools.page.NoPage:
            return None
        
    def userEdits(self, username):
        params = {'action' : 'query',
                  'list'   : 'usercontribs',
                  'ucuser' : username
                  }
        response = wikitools.APIRequest(self.wiki, params).query(querycontinue = False)
        
        return response['query']['usercontribs']
        
    def deletePage(self, title, reason = 'spam'):
        page = wikitools.Page(self.wiki, title)
        page.delete(reason)
        return "Page {pageName} deleted".format(pageName = title)
        
    def deleteAllPages(self, user):
        edits = self.userEdits(user)
        for edit in edits:
            if 'new' in edit.keys():
                self.deletePage(edit['title'])
        
                
    def blockUser(self, user, reason = 'spambot'):
        userObject = wikitools.User(self.wiki, user)
        userObject.block(reason = reason, autoblock = True)
        return "User {username} blocked".format(username = user)
        
    def blockAndRemovePages(self, user):
        self.deleteAllPages(user)
        self.blockUser(user)
        return "User {username} blocked, pages deleted".format(username = user)

    def newTimeStamp(self, oldTimestamp):
        oldTime = datetime.datetime.strptime(oldTimestamp, "%Y-%m-%dT%H:%M:%SZ")
        newTime = oldTime + datetime.timedelta(seconds = 1)
        return datetime.datetime.strftime(newTime, "%Y-%m-%dT%H:%M:%SZ")
        
    def makeMessage(self, change):
        message = None
        if not change['comment']:
            change['comment'] = '-'
        
        if change['type'] == 'new':
            message = "%s made new page titled %s with comment: %s" % (change['user'], change['title'], change['comment'])
        
        if change['type'] == 'edit':
            message = "%s edited %s with comment: %s" % (change['user'], change['title'], change['comment']) 
                
        if change['type'] == 'log':
            if change['logtype'] == 'newusers':
                message = "New user: %s" % change['user']
                
            if change['logtype'] == 'block':
                message = '%s blocked user %s with comment %s' % (change['user'], change['title'].split(":", 1)[1],
                                                                  change['comment'])
            
            if change['logtype'] == 'delete':
                message = '%s deleted page %s with comment %s' % (change['user'], change['title'], change['comment'])
                
        return message if message else None
