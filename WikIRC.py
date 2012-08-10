#! /usr/bin/python

import json
import sys

# non stdlib internals
import irc
import wiki

from twisted.internet import reactor

def loadConfig():
    try:
        configFile = open('config.json')
        config = json.load(configFile)
        # data must not be unicode, twisted throws a fit if it is
        for key in config:
            config[key] = config[key].encode('ascii', 'ignore')
        return config
    except:
        return None
    
def writeDefaultConfig():
    defaultConfig = {'wiki_API_URL' : 'http://your.wiki.address/api.php',
                     'wiki_username': 'user_name_for_bot',
                     'wiki_password': 'wiki_account_password',
                     'IRC_server'   : 'irc.gamesurge.net',
                     'IRC_nickname' : 'WikIRC',
                     'IRC_channel'  : 'WikIRC_testing_channel',
                     }
    configFile = open('config.json', 'w')
    configFile.write(json.dumps(defaultConfig, indent = 4, encoding = 'ASCII'))

def main():
    config = loadConfig()
    if not config:
        writeDefaultConfig()
        print("----------")
        print("Config file not found, default file generated")
        print("Program now exiting")
        print("----------")

        sys.exit()
     
    f = irc.WikIRCFactory(config['IRC_nickname'], config['IRC_channel'], config['wiki_API_URL'],
                                 config['wiki_username'], config['wiki_password'])
    reactor.connectTCP(config['IRC_server'], 6667, f)
    reactor.run()

if __name__ == '__main__':
    main()
