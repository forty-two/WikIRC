#! /usr/bin/python

import json
import time

# non stdlib internal
import permissions
import wiki

# non stdlib external
from twisted.words.protocols import irc
from twisted.internet import reactor, protocol, task, threads, defer


class IRCBot(irc.IRCClient):
    
    def __init__(self, nickname):
        print "In ircbot"
        self.nickname = nickname
        self.realname = "WikIRC 0.2"
        self.versionName = "WikIRC - https://github.com/forty-two/WikIRC"
        self.versionNum = 0.2
        self.lineRate = 1
        self.checkLoop = task.LoopingCall(self.checkWiki)
        print "Created checkloop"
        self.authChecker = permissions.AuthHandler("WikIRC_user_permissions.json")
        self.commandPermissions = {'admin': ['*']}

    def checkWiki(self):
        deferredCheck = threads.deferToThread(self.factory.wikiHandler.recentChanges)
        deferredCheck.addCallbacks(self.checkWikiCallback, self.errorCallback)

    def checkWikiCallback(self, changes):
        print "Wiki checked at {}".format(time.ctime())
        for change in changes:
            if change:
                self.msg(self.factory.channel, change.encode('UTF-8', 'ignore'))
    
    def connectionMade(self):
        irc.IRCClient.connectionMade(self)
        

    def connectionLost(self, reason):
        self.checkLoop.stop()
        irc.IRCClient.connectionLost(self, reason)

    def signedOn(self):
        self.join(self.factory.channel)
        print("Succesfully signed into IRC server")
        

    def joined(self, channel):
        print("Succesfully joined channel %s" % channel)
        self.checkLoop.start(60)

    def isAuthorised(self, command, username, hostmask):
        userPermissions = self.authChecker.get_user_permissions(username, hostmask)
        print username
        print hostmask
        print userPermissions
        if userPermissions:
            for group in userPermissions:
                if command in self.commandPermissions.get(group, []):
                    return True
                if "*" in self.commandPermissions.get(group, []):
                    return True
        return False

    def handleCommands(self, user, hostmask, command, options):
        wikiHandlers = {'block'         : self.factory.wikiHandler.blockUser,
                        'blockdelete'   : self.factory.wikiHandler.blockAndRemovePages,
                        'bd'            : self.factory.wikiHandler.blockAndRemovePages,
                        'delete'        : self.factory.wikiHandler.deletePage,
                        'revert'        : self.factory.wikiHandler.revertPage,
                        }
        localHandlers = {'addhostmask'   : self.addUserHostmask,
                         'adduser'       : self.addUser,
                         'addusergroup'  : self.addUserGroup,
                         'wikihelp'      : self.helpMessage,
                         'permshelp'     : self.permsHelpMessage,
                         'removehostmask': self.removeUserHostmask,
                         'removegroup'   : self.removePermissionGroup,
                         'removeuser'    : self.removeUser,
                        }

        if self.isAuthorised(command, user, hostmask):
            if command in wikiHandlers:
                wikiRequest = threads.deferToThread(wikiHandlers[command], *options)
                wikiRequest.addCallbacks(self.commandsCallback, self.errorCallback)
            elif command in localHandlers:
                self.commandsCallback(localHandlers[command](*options))
            # activate following if desired, but will respond to anything that appears to be a command (e.g. other bots commands)
            # else:
            #     self.msg(self.factory.channel, "Command {} not known".format(command))

    def errorCallback(self, error):
        self.msg(self.factory.channel, "An error occurred while processing this request")
        error.printTraceback()

    def commandsCallback(self, response):
        response = response.encode('UTF-8', 'ignore')
        print('Command callback activated for response {}'.format(response))
        self.msg(self.factory.channel, response)


    def addUserHostmask(self, *args):
        if len(args) == 2:
            self.authChecker.add_user_hostmask(args[0], args[1])
            return "Added hostmask %s to user %s" % (args[1], args[0])
        else:
            return "Incorrect usage, use .addhostmask username hostmask"
        
    def addUser(self, *args):
        if len(args) == 3:
            self.authChecker.add_user(args[0], args[1], args[2])
            return "Created user %s" % (args[0])
        else:
            return "Incorrect usage, use .adduser username hostmask group"
            
    def addUserGroup(self, *args):
        if len(args) == 2:
            self.authChecker.add_user_group(args[0], args[1])
            return "Added user %s to group %s" % (args[0], args[1])
        else:
            return "Incorrect usage, use .addusergroup username group"

            
    def helpMessage(self, *args):
        return "Commands avaliable: .block username, .blockdelete username, .delete pagename, .permshelp"
        
    def permsHelpMessage(self, *args):
        return "Commands availible: .adduser username hostname group, .addhostmask username hostmask, .removeuser username, .removehostmask username hostmask"
                             
        
    def removeUserHostmask(self, *args):
        if len(args) == 2:
            self.authChecker.remove_user_hostmask(args[0], args[1])
            return "Removed hostmask %s from user %s" % (args[1], args[0])
        else:
            return "Incorrect usage, use .removehostmask username hostmask"
            
    def removePermissionGroup(self, *args):
        if len(args) == 2:
            self.authChecker.remove_group(args[0], args[1])
            return "Removed permission group %s from user %s" % (args[1], args[0])
        else:
            return "Incorrect usage, use .removegroup username groupName"
    
    def removeUser(self, *args):
        if len(args) == 1:
            self.authChecker.remove_user(args[0])
            return "Removed user %s" % args[0]
        else:
            return "Incorrect usage, use .removeuser username"

    def privmsg(self, user, channel, msg):
        msg = msg.decode('UTF-8', 'ignore')
        userName = user.split('!', 1)[0]
        userHostmask = user.split('@', 1)[1]
        
        # Check to see if they're sending a private message
        if channel == self.nickname:
            msg = "Commands in the public channel only please"
            self.msg(userName, msg)
            return

        # Otherwise check to see if it is a command
        print msg
        if msg.startswith('.'):
            print "sending command"
            msg = msg.split(' ')
            command = msg[0].strip('.')
            if len(msg) > 1:
                options = msg[1:]
            else:
                options = []
            self.handleCommands(userName, userHostmask, command, options)

class WikIRCFactory(protocol.ClientFactory):
    def __init__(self, nickname, channel, apiURL, wikiUser, wikiPass):
        print "in WikIRCFactory"
        self.nickname = nickname
        self.channel = channel
        self.wikiHandler = wiki.WikiHandler(apiURL, wikiUser, wikiPass)
        self.wikiHandler.connect()

        
    def buildProtocol(self, addr):
        p = IRCBot(self.nickname)
        p.factory = self
        return p

    def clientConnectionLost(self, connector, reason):
        """If we get disconnected, reconnect to server."""
        connector.connect()

    def clientConnectionFailed(self, connector, reason):
        print "connection failed:", reason
        reactor.stop()    

