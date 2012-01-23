#! /usr/bin/python

import time
import threading
import os
import sys
import re
import Queue
import datetime
import json

# non stdlib external
import wikitools

                
class wikiChecker(threading.Thread):
    def __init__(self, parent):
        self.parent = parent
        self.outputQueue = parent.outputQueue
        self.lastTimestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        self.continueRunning = True
        
        threading.Thread.__init__(self)
        
    def run(self):
        while self.continueRunning:
            self.parent.accessLock.acquire()
            recentChanges = self.parent.recentChanges(self.lastTimestamp)
            self.parent.accessLock.release()
            if recentChanges:
                for change in recentChanges:
                    self.makeMessage(change)
                self.lastTimestamp = self.newTimeStamp(recentChanges[len(recentChanges)-1]['timestamp'])
            print "Checked wiki at "+time.ctime()
            time.sleep(60)
            
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
                
        if message:
            self.parent.outputQueue.put(message)      

class wikiCommandChecker(threading.Thread):
    def __init__(self, parent):
        self.parent = parent
        self.inputQueue = parent.inputQueue
        self.outputQueue = parent.outputQueue
        self.continueRunning = True
        self.handlers = {'block'      : self.parent.blockUser,
                         'blockdelete': self.parent.blockAndRemovePages,
                         'delete'     : self.parent.deletePage,
                         }
        threading.Thread.__init__(self)
        
    def run(self):
        while self.continueRunning:
            try:
                input = json.loads(self.inputQueue.get())
                if input.get('command') in self.handlers:
                    try:
                        self.parent.accessLock.acquire()
                        self.handlers[input['command']](*input.get('options'))
                        self.parent.accessLock.release()
                    except Exception as e:
                        print e
                        self.outputQueue.put('Sorry, exception occurred. Please check command and try again')
            except ValueError:
                print("Incorrect value passed to wiki input, use json")
        

class WikiHandler():
    def __init__(self, apiURL, username, password, inputQueue, outputQueue):
        self.apiURL = apiURL
        self.username = username
        self.password = password
        self.outputQueue = outputQueue
        self.inputQueue = inputQueue
        self.accessLock = threading.Lock()
        
        
    def connect(self):
        self.wiki = wikitools.Wiki(self.apiURL)
        self.wiki.login(self.username, self.password)
        
    def startChecking(self):
        self.wikiCheckingThread = wikiChecker(self)
        self.wikiCheckingThread.start()
        
        self.inputCheckingThread = wikiCommandChecker(self)
        self.inputCheckingThread.start()
        
    def stopChecking(self):
        self.wikiCheckingThread.continueRunning = False
        self.inputCheckingThread.continueRunning = False
        
    def recentChanges(self, timestamp = None):
        
        if not timestamp:
            timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        
        params = {'action' : 'query',
                  'list'   : 'recentchanges',
                  'rclimit': '25',
                  'rcstart': timestamp,
                  'rcdir'  : 'newer',
                  'rcprop' : 'user|timestamp|title|comment|loginfo'
                  }
    
        response = wikitools.APIRequest(self.wiki, params).query(querycontinue = False)
        
        return response['query']['recentchanges']

    def pageText(self, title):
        try:
            page = wikitools.Page(title)
            response = page.getWikiText()
            return response
        except wikitools.page.NoPage:
            return ""
        
    def userEdits(self, username):
        params = {'action' : 'query',
                  'list'   : 'usercontribs',
                  'ucuser' : username
                  }
        response = wikitools.APIRequest(self.wiki, params).query(querycontinue = False)
        
        return response['query']['usercontribs']
        
    def deletePage(self, title, reason = 'spam'):
        page = wikitools.Page(self.wiki, title)
        self.outputQueue.put("Page {pageName} deleted".format(pageName = title))
        return page.delete(reason)
        
    def deleteAllPages(self, user):
        edits = self.userEdits(user)
        for edit in edits:
            if 'new' in edit.keys():
                self.deletePage(edit['title'])
        
                
    def blockUser(self, user, reason = 'spambot'):
        userObject = wikitools.User(self.wiki, user)
        userObject.block(reason = reason, autoblock = True)
        self.outputQueue.put("User {username} blocked".format(username = user))
        
    def blockAndRemovePages(self, user):
        self.deleteAllPages(user)
        self.blockUser(user)
        self.outputQueue.put("User {username} blocked, pages deleted".format(username = user))
