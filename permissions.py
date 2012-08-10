#! /usr/bin/python

import os
import json


class AuthHandler():
    '''Stores hostmask and permission group info for usernames, writes the data
       to a json config file'''

    def __init__(self, filename):
        self.filename = filename
        self.config = {}
        self._load_config()

    def add_user(self, username, hostmask, group):
        username = username.lower()
        group = group.lower()

        self.config[username] = {'groups'    : [group],
                                 'hostmasks': [hostmask]
                                 }
        self._save_config()
        
    def add_user_group(self, username, group):
        self.config[username]['groups'].append(group)
        self._save_config()
    
    def add_user_hostmask(self, username, hostmask):
        username = username.lower()
        self.config[username]['hostmasks'].append(hostmask)
        self._save_config()

    def get_group_list(self):
        groupList = []
        for user in self.config:
            groupList.extend([i for i in self.config[user]['groups'] if i not in groups])
        return groupList

    def get_user_permissions(self, username, hostmask):
        knownHostmasks = self.config.get(username, {}).get('hostmasks', [])
        if hostmask in knownHostmasks:
            return self.config.get(username).get('groups')
        else:
            return None

    def remove_group(self, user, groupName):
        if user in self.config:
            if groupName in self.config[user]['groups']:
                self.config[user]['groups'].remove(groupName)
                self._save_config()
                                            
    def remove_user(self, username):
        username = username.lower()
        try:
            self.config.pop(username)
            self._save_config()
        except KeyError:
            return False

    def remove_user_hostmask(self, username, hostmask):
        username = username.lower()
        try:
            self.config[username]['hostmasks'].remove(hostmask)
            self._save_config()
        except KeyError:
            return False
        
    def _load_config(self):
        try:
            if os.path.isfile(self.filename):
                self.config = json.load(open(self.filename))

        except ValueError:
            self.config = {}

    def _save_config(self):
        f = open(self.filename, 'w')
        f.write(json.dumps(self.config, indent = 4))
        f.close()


    




