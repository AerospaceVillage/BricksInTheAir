# Code for managing twitch user list
# Created for defcon28 Aerospace Village

import time # needed for sleep
import threading # needed for userThread
import random # needed for zone generation
import asyncio # needed for async ops

from pykeyboard import PyKeyboard   # needed for OBS Studio hotkey scene changes
import os

from BrickUser import BrickUser

class UserList:
    """ List of active users """

    def __init__(self, cfg, dispMan, bia, bot):
        """ init method """

        self.cfg = cfg
        self.dispMan = dispMan
        self.bia = bia
        self.bot = bot
        #self.userList = [BrickUser("dan", cfg), BrickUser("Amanda", cfg), BrickUser("cybertestpilot", cfg)]
        self.userList = []
        self.currentUser = None
        self.limit = cfg["cue"]["limit"]
        self.time_allowed = cfg["cue"]["time"]
        self.current_user_lock = threading.Lock()
        self.cue_lock = threading.Lock()
        self.threadRunning = True
        self.tick = self.time_allowed
        self.newUser = True

        self.thread = None

        # OBS Studio specific variables
        self.keyboard = PyKeyboard()
        self.transition_hotkey = cfg["default"]["transition_hotkey"]
        self.transition_hotkey_list = self.scene_hotkey_to_useable_list(self.transition_hotkey)
        self.default_scene_hotkey = cfg["default"]["scene_hotkey"]
        self.window_focus_name = cfg["default"]["window_focus_name"]
        self.default_image = cfg["default"]["image"]

    def addUser(self, name):
        """ Checks if user already exists, and if not adds them to the list.  \nReturns True if name is added, False otherwise """

        self.cue_lock.acquire()
        for user in self.userList:
            if (user.matchName(name)):
                self.cue_lock.release()
                return False

        #if user list is empty
        if not self.userList:
            print("adding new user:" + name)
            newUser = BrickUser(name, self.cfg)
            #self.cue_lock.acquire()
            self.userList.append(newUser)
            self.cue_lock.release()
            self.setCurrentUser(newUser)
            #self.triggerChanges()
            return True

        if len(self.userList) < self.limit:
            print("adding new user to current list:" + name)
            #self.cue_lock.acquire()
            self.userList.append(BrickUser(name, self.cfg))
            print(self.userList)
            self.cue_lock.release()
            #self.triggerChanges()
            return True
        else:
            self.cue_lock.release()
            return False

    def removeUser(self, name):
        ''' Checks if user already exists and removes them from the list.  \nReturns true if removed, false otherwise '''
        self.cue_lock.acquire()
        print("remove name: " + name)
        print(self.userList)
        for user in self.userList:
            if (user.matchName(name)):
                self.userList.remove(user)

                print("found the user, returning true")
                self.cue_lock.release()

                self.current_user_lock.acquire()
                if user == self.currentUser:
                    # need to remove/adjust who currentUser actually is
                    if len(self.userList) > 0:
                        self.currentUser = self.userList[0]
                    else:
                        self.currentUser = None

                self.current_user_lock.release()
                self.triggerChanges(False)
                return True
        self.cue_lock.release()
        return False

    def triggerChanges(self, prologue=True, cmd=None):
        #print("triggerChanges************************")

        self.current_user_lock.acquire()
        # run prologoue for this specific user
        if self.currentUser != None:
            scene_hotkey = self.currentUser.get_scene_hotkey()
            if scene_hotkey != None:
                self.press_hotkeys(scene_hotkey)

            if prologue:
                self.bia.run_prolouge(self.currentUser)
            self.bia.set_engine_speed(self.currentUser.getEngineSpeed(), True)
            self.dispMan.updateImage(self.currentUser.getImage())

        else:
            scene_hotkey = self.default_scene_hotkey
            if scene_hotkey != None:
                self.press_hotkeys(scene_hotkey)
            self.dispMan.updateImage(self.default_image)
            self.bia.set_engine_speed(0, True)

        self.dispMan.updateUserList(self.getUserList())

        if cmd != None:
            self.dispMan.updateCmdMsg(cmd)
        self.current_user_lock.release()


    def startUserThread(self):
        """ Starts the user thread """
        print("Start userList thread")

        self.thread = threading.Thread(target=self.userThread, args=(), daemon=True)
        self.thread.start()

    def restartUserThread(self):
        print("restarting UserList Thread")

        #self.threadRunning = False
        #time.sleep(1)
        #self.startUserThread()


    def userThread(self):
        """ Runs through list and updates the current user every X seconds """
        while self.threadRunning:
            # print("********************************servicing userthread")

            if len(self.userList) > 0:
                self.cue_lock.acquire()
                user = self.userList[0]
                self.cue_lock.release()

                self.setCurrentUser(user)
                self.triggerChanges()

                self.newUser = False    # variable used to track if trigger should be invoked

                time.sleep(self.time_allowed)

                if self.currentUser != None:
                    if (self.currentUser.updateTimeout() > 0):
                        self.currentUserToEndOfLine()
                        """
                        time.sleep(1)
                        if self.tick < 0:
                            if (user.updateTimeout() > 0):
                                self.currentUserToEndOfLine()
                            self.tick = self.time_allowed

                        elif self.tick >= 0:
                            print("decrement userList.tick")
                            self.tick -= 1

                        """
                    else:
                        print("removing user for inactivity: " + str(user))
                        userName = user.getName()
                        self.userList.remove(user)

                        if len(self.userList) >= 1:
                            self.setCurrentUser(self.userList[0])
                        else:
                            self.setCurrentUser(None)

                        self.triggerChanges(False)

                        try:
                            msg = "Removing " + userName + " for inactivity."
                            asyncio.run(self.bot._ws.send_privmsg(self.bot.initial_channels[0], msg))
                        except Exception as err:
                            print("Erorr attempting to notify bot of user removal.")
                            print(repr(err))


            else:
                # No active users
                self.bia.set_engine_speed(0, True)
                time.sleep(1)
                try:
                    #self.triggerChanges()
                    self.setCurrentUser(None)
                except Exception as err:
                    #print("error inializing dispMan")
                    print(repr(err))

        print("")


    def getCurrentUser(self):
        """ Grabs the current user as dictated by userThread """
        with self.current_user_lock:
            return self.currentUser

    def setCurrentUser(self, user):
        """ Grabs the current user as dictated by userThread """
        with self.current_user_lock:
            self.currentUser = user

        self.triggerChanges(True)

    def getUserList(self):
        """ Returns the list of current Users """
        #print("userList:" + str(self.userList))
        with self.cue_lock:
            return self.userList

    def currentUserToEndOfLine(self):
        self.cue_lock.acquire()
        if len(self.userList) >= 1:
            self.userList.append(self.userList.pop(0))

            self.cue_lock.release()
            self.setCurrentUser(self.userList[0])


    def getNextUserList(self, nextCount):
        ''' Returns the next X users in the list formated by Name : time \nnextCount : how long the next user list should be '''

        msg = ""
        #self.cue_lock.acquire()
        for x in self.userList:
            msg += x.getName() + "\n"
        #self.cue_lock.release()
        print("active user list: " + msg)
        return msg

    def emptyUserList(self):
        self.cue_lock.acquire()
        self.userList.clear()
        self.cue_lock.release()
        self.setCurrentUser(None)
        self.triggerChanges()

    def scene_hotkey_to_useable_list(self, scene_hotkey_str):
        scene_list = None
        try:
            scene_list = scene_hotkey_str.split("+")

            for index, value in enumerate(scene_list):
                if scene_list[index].lower() == "shift":
                    scene_list[index] = self.keyboard.shift_key
        except Exception as err:
            print("UserList.scene_hotkey_to_useable_list() error")
            print(repr(err))

        return scene_list

    def press_hotkeys(self, scene_hotkey):
        try:
            os.system("xdotool search --name \"" + self.window_focus_name + "\" | xargs xdotool windowactivate")
        except Exception as err:
            print("UserList.triggerChanges() error")
            print(repr(err))

        scene_change = self.scene_hotkey_to_useable_list(scene_hotkey)
        if scene_change != None:
            #print(scene_change)
            self.keyboard.press_keys(scene_change)
        if self.transition_hotkey_list != None:
            self.keyboard.press_keys(self.transition_hotkey_list)