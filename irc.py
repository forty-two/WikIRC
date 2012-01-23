#! /usr/bin/python

import json
import threading
import time

# non stdlib internal
import permissions

# non stdlib external
from twisted.words.protocols import irc
from twisted.internet import reactor, protocol


class IRCReadInThread(threading.Thread):
    def __init__(self, inputQueue, IRCInstance):
        self.inputQueue = inputQueue
        self.IRCInstance = IRCInstance
        self.channel = IRCInstance.factory.channel
        self.continueRunning = True
        threading.Thread.__init__(self)
        
    def run(self):
        while self.continueRunning:
            message = self.inputQueue.get()
            if message is "quit":
                self.continueRunning = False
            else:
                self.IRCInstance.say(self.channel, message.encode('ascii', 'ignore'), length = 510)
                time.sleep(1)
            

class CommandHandler:
    def __init__(self, IRCInstance, inputQueue, outputQueue):
        self.IRCInstance = IRCInstance
        self.channel = self.IRCInstance.factory.channel
        self.inputQueue = inputQueue
        self.outputQueue = outputQueue
        self.authChecker = permissions.AuthHandler("WikIRC_user_permissions.json")
        
        self.handlers = {'addhostmask'   : self.addUserHostmask,
                         'adduser'       : self.addUser,
                         'addusergroup'  : self.addUserGroup,
                         'block'         : self.blockUser,
                         'blockdelete'   : self.blockdeleteUser,
                         'delete'        : self.deletePage,
                         'wikihelp'      : self.helpMessage,
                         'permshelp'     : self.permsHelpMessage,
                         'removehostmask': self.removeUserHostmask,
                         'removegroup'   : self.removePermissionGroup,
                         'removeuser'    : self.removeUser,
                         }
        
        self.commandPermissions = {'admin': ['*']}
        
    def handleCommand(self, username, hostmask, command, options):
        print "handling command: "+command
        command = command.lower()
        options = options.split(' ')
        if command in self.handlers:
            print "command in handlers"
            
            if self.isAuthorised(command, username, hostmask):
                self.handlers[command](*options)
            else:
                self.IRCInstance.say(self.channel, "Incorrect permission group for this command.")
            
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

    def addUserHostmask(self, *args):
        if len(args) == 2:
            self.authChecker.add_user_hostmask(args[0], args[1])
            self.IRCInstance.say(self.channel, "Added hostmask %s to user %s" % (args[1], args[0]))
        else:
            self.IRCInstance.say(self.channel, "Incorrect usage, use .addhostmask username hostmask")
        
    def addUser(self, *args):
        if len(args) == 3:
            self.authChecker.add_user(args[0], args[1], args[2])
            self.IRCInstance.say(self.channel, "Created user %s" % (args[0]))
        else:
            self.IRCInstance.say(self.channel, "Incorrect usage, use .adduser username hostmask group")
            
    def addUserGroup(self, *args):
        if len(args) == 2:
            self.authChecker.add_user_group(args[0], args[1])
            self.IRCInstance.say(self.channel, "Added user %s to group %s" % (args[0], args[1]))
        else:
            self.IRCInstance.say(self.channel, "Incorrect usage, use .addusergroup username group")
            
    def blockUser(self, *args):
        if len(args) == 1:
            data  = {'command' : 'block',
                     'options': args
                     }
            self.outputQueue.put(json.dumps(data))
        else:
            self.IRCInstance.say(self.channel, "Incorrect usage, use .block username")
            
    def blockdeleteUser(self, *args):
        if len(args) == 1:
            data = {'command' : 'blockdelete',
                    'options': args
                    }
            self.outputQueue.put(json.dumps(data))
        else:
            self.IRCInstance.say(self.channel, "Incorrect usage, use .blockdelete username")
            
    def deletePage(self, *args):
        if len(args) == 1:
            data = {'command' : 'delete',
                    'options': args
                    }
            self.outputQueue.put(json.dumps(data))
        else:
            self.IRCInstance.say(self.channel, "Incorrect usage, use .delete pagename")
            
    def helpMessage(self, *args):
        self.IRCInstance.say(self.channel, "Commands avaliable: .block username, .blockdelete username,"
                             " .delete pagename, .permshelp")
        
    def permsHelpMessage(self, *args):
        self.IRCInstance.say(self.channel, "Commands availible: .adduser username hostname group, "
                             ".addhostmask username hostmask, .removeuser username, "
                             ".removehostmask username hostmask"
                             )
        
    def removeUserHostmask(self, *args):
        if len(args) == 2:
            self.authChecker.remove_user_hostmask(args[0], args[1])
            self.IRCInstance.say(self.channel, "Removed hostmask %s from user %s" % (args[0], args[1]))
        else:
            self.IRCInstance.say(self.channel, "Incorrect usage, use .removehostmask username hostmask")
            
    def removePermissionGroup(self, *args):
        if len(args) == 1:
            self.authChecker.remove_group(args[0])
            self.IRCInstance.say(self.channel, "Removed permission group %s" % args[0])
        else:
            self.IRCInstance.say(self.channel, "Incorrect usage, use .removegroup groupName")
    
    def removeUser(self, *args):
        if len(args) == 1:
            self.authChecker.remove_user(args[0])
            self.IRCInstance.say(self.channel, "Removed user %s" % args[0])
        else:
            self.IRCInstance.say(self.channel, "Incorrect usage, use .removeuser username")


class IRCBot(irc.IRCClient):
    
    def __init__(self, nickname):
        self.nickname = nickname
    
    def connectionMade(self):
        irc.IRCClient.connectionMade(self)
        

    def connectionLost(self, reason):
        irc.IRCClient.connectionLost(self, reason)

    # callbacks for events

    def startIOHandlers(self):
        self.commandHandler = CommandHandler(self, self.factory.inputQueue, self.factory.outputQueue)
        self.queueOutputThread = IRCReadInThread(self.factory.inputQueue, self)
        self.queueOutputThread.start()

    def signedOn(self):
        self.join(self.factory.channel)
        print("Succesfully signed into IRC server")
        self.startIOHandlers()

    def joined(self, channel):
        print("Succesfully joined channel %s" % channel)

    def privmsg(self, user, channel, msg):
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
            msg = msg.split(' ', 1)
            command = msg[0].strip('.')
            if len(msg) > 1:
                options = msg[1]
            else:
                options = ""
            self.commandHandler.handleCommand(userName, userHostmask, command, options)

class IRCFactory(protocol.ClientFactory):


    def __init__(self, nickname, channel, inputQueue, outputQueue):
        self.nickname = nickname
        self.channel = channel
        self.inputQueue = inputQueue
        self.outputQueue = outputQueue
        print "in IRCFactory"
        
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




def start(inputQueue, outputQueue, nickname, channel, server, port = 6667):
    factory = IRCFactory(nickname, channel, inputQueue, outputQueue)

    # connect factory to this host and port
    reactor.connectTCP(server, port, factory)

    # run bot
    reactor.run()
