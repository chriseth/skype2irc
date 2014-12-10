#! /usr/bin/env python
# -*- coding: utf-8 -*-

# IRC ⟷  Skype Gateway Bot: Connects Skype Chats to IRC Channels
# Copyright (C) 2014  Märt Põder <tramm@p6drad-teel.net>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# *** This bot deliberately prefers IRC to Skype! ***

# Snippets from
#
#  Feebas Skype Bot (C) duxlol 2011 http://sourceforge.net/projects/feebas/
#  IRC on a Higher Level http://www.devshed.com/c/a/Python/IRC-on-a-Higher-Level/
#  Time until a date http://stackoverflow.com/questions/1580227/find-time-until-a-date-in-python
#  Skype message edit code from Kiantis fork https://github.com/Kiantis/skype2irc

import sys, signal
import time, datetime
import string, textwrap

from ircbot import SingleServerIRCBot
from irclib import ServerNotConnectedError
from threading import Timer

version = "0.3"

if len(sys.argv) >= 2:
    # provide path to configuration file as a command line parameter

    execfile(sys.argv[1])

else:
    # default configuration for testing purposes    

    servers = [
    ("irc.freenode.net", 6667),
    ("hitchcock.freenode.net", 6667),
    ("leguin.freenode.net", 6667),
    ("verne.freenode.net", 6667),
    ("roddenberry.freenode.net", 6667),
    ]

    nick = "SkypeGateway"
    botname = "IRC ⟷  Skype".decode('UTF-8')
    password = None
    vhost = False

    mirrors = [
            {
            '#some-irc-channel',
            'Xu4SrIzfxcScKxzooKaqnQmcdnKdm3n8AmSjrxmnuPykdronX2HFFwn7B2yL-MAUvISnLoD2fx6aFXPNbo3bJsJAOjumU5_uOU8CFyakSneQMnrljGypZ_aGiN6I6OS40eajIsSea7nhDLF3wA',
            'NL0aHgMl6tP1O3flwrBCLO2jmaFtFIlW52Fg62ml6BGF3zRg6ejroDYfGb1yUlvg627ghkTwZdZvS6FgLiCGXWPDT32u0dfXZwFrTGkIBo6oxwRo0zjy-2oECB1Mb3bFuDiEWlnqo7qcxP4'
            }
    ]

    colors = False

max_irc_msg_len = 442
ping_interval = 2*60
reconnect_interval = 30

# to avoid flood excess
max_seq_msgs = 2
delay_btw_msgs = 0.35
delay_btw_seqs = 0.15

preferred_encodings = ["UTF-8", "CP1252", "ISO-8859-1"]

name_start = "<".decode('UTF-8') # "◀"
name_end = ">".decode('UTF-8') # "▶"
emote_char = "*".decode('UTF-8') # "✱"

topics = ""

bot = None
skypeChannels = {}
blobs = {}
lastsaid = {}
edmsgs = {}

pinger = None
bot = None

wrapper = textwrap.TextWrapper(width=max_irc_msg_len - 2)
wrapper.break_on_hyphens = False

# Time consts
SECOND = 1
MINUTE = 60 * SECOND
HOUR = 60 * MINUTE
DAY = 24 * HOUR
MONTH = 30 * DAY

def isIrcChannel(channel):
    return channel.startswith('#')

def get_relative_time(dt, display_full = True):
    """Returns relative time compared to now from timestamp"""
    now = datetime.datetime.now()
    delta_time = now - dt

    delta =  delta_time.days * DAY + delta_time.seconds 
    minutes = delta / MINUTE
    hours = delta / HOUR
    days = delta / DAY

    if delta <= 0:
        return "in the future" if display_full else "!"
    if delta < 1 * MINUTE: 
      if delta == 1:
          return "moment ago" if display_full else "1s"
      else:
          return str(delta) + (" seconds ago" if display_full else "s")
    if delta < 2 * MINUTE:    
        return "a minute ago" if display_full else "1m"
    if delta < 45 * MINUTE:    
        return str(minutes) + (" minutes ago" if display_full else "m")
    if delta < 90 * MINUTE:
        return "an hour ago" if display_full else "1h"
    if delta < 24 * HOUR:
        return str(hours) + (" hours ago" if display_full else "h")
    if delta < 48 * HOUR:
        return "yesterday" if display_full else "1d"
    if delta < 30 * DAY:    
        return str(days) + (" days ago" if display_full else "d")
    if delta < 12 * MONTH:
        months = delta / MONTH
        if months <= 1:
            return "one month ago" if display_full else "1m"
        else:
            return str(months) + (" months ago" if display_full else "m")
    else:
      years = days / 365.0
      if  years <= 1:
          return "one year ago" if display_full else "1y"
      else:
          return str(years) + (" years ago" if display_full else "y")

def cut_title(title):
    """Cuts Skype chat title to be ok"""
    newtitle = ""
    for chunk in title.split():
        newtitle += chunk.strip(string.punctuation) + " "
        if len(newtitle) > 10:
            break
    return newtitle.strip()

def get_nick_color(s):
    colors = ["\x0305", "\x0304", "\x0303", "\x0309", "\x0302", "\x0312",
              "\x0306",   "\x0313", "\x0310", "\x0311", "\x0307"]
    num = 0
    for i in s:
        num += ord(i)
    num = num % 11
    return colors[num]

def get_nick_decorated(nick):
    """Decorate nicks for better visibility in IRC (currently bold or
    colors based on nick)"""
    if colors:
        return get_nick_color(nick) + nick + '\017'
    else:
        return nick #"\x02" + nick + "\x02"

def broadcast(text, sourceChannel):
    for channelSet in mirrors:
        if sourceChannel in channelSet:
            for chan in channelSet - {sourceChannel}:
                if isIrcChannel(chan):
                    bot.say(chan, text)
                else:
                    skypeChannels[chan].SendMessage(text)

def skype_says(chat, msg, edited = False):
    """Translate Skype messages to IRC"""
    raw = msg.Body
    msgtype = msg.Type
    senderDisplay = msg.FromDisplayName
    senderHandle = msg.FromHandle

    if edited:
        edit_label = " ✎".decode('UTF-8') + get_relative_time(msg.Datetime, display_full = False)
    else:
        edit_label = ""
    if msgtype == 'EMOTED':
        broadcast(emote_char + " " + get_nick_decorated(senderHandle) + edit_label + " " + raw, chat)
    elif msgtype == 'SAID':
        broadcast(name_start + get_nick_decorated(senderHandle) + edit_label + name_end + " " + raw, chat)

def OnMessageStatus(Message, Status):
    """Skype message object listener"""
    chat = Message.Chat

    # Only react to defined chats
    if chat in blobs and blobs[chat] in skypeChannels:
        if Status == 'RECEIVED':
            skype_says(blobs[chat], Message)

def OnNotify(n):
    """Skype notification listener"""
    print("skype notifcy: %s" % repr(n))
    params = n.split()
    if len(params) >= 4 and params[0] == "CHATMESSAGE":
        if params[2] == "EDITED_TIMESTAMP":
            edmsgs[params[1]] = True
        elif params[1] in edmsgs and params[2] == "BODY":
            msg = skype.Message(params[1])
            if msg:
                chat = msg.Chat
                if chat in blobs and blobs[chat] in skypeChannels:
                    skype_says(blobs[chat], msg, edited = True)
            del edmsgs[params[1]]

def decode_irc(raw, preferred_encs = preferred_encodings):
    """Heuristic IRC charset decoder"""
    changed = False
    for enc in preferred_encs:
        try:
            res = raw.decode(enc)
            changed = True
            break
        except:
            pass
    if not changed:
        try:
            import chardet
            enc = chardet.detect(raw)['encoding']
            res = raw.decode(enc)
        except:
            res = raw.decode(enc, 'ignore')
            #enc += "+IGNORE"
    return res

def signal_handler(signal, frame):
    print "Ctrl+C pressed!"
    if pinger is not None:
        print "Cancelling the pinger..."
        pinger.cancel()
    if bot is not None:
        print "Killing the bot..."
        for dh in bot.ircobj.handlers["disconnect"]:
            bot.ircobj.remove_global_handler("disconnect", dh[1])
        if len(bot.ircobj.handlers["disconnect"]) == 0:
            print "Finished."
            bot.die()

class MirrorBot(SingleServerIRCBot):
    """Create IRC bot class"""

    def __init__(self):
        SingleServerIRCBot.__init__(self, servers, nick, (botname + " " + topics).encode("UTF-8"), reconnect_interval)

    def start(self):
        """Override default start function to avoid starting/stalling the bot with no connection"""
        while not self.connection.is_connected():
            self._connect()
            if not self.connection.is_connected():
                time.sleep(self.reconnection_interval)
                self.server_list.append(self.server_list.pop(0))
        SingleServerIRCBot.start(self)

    def on_nicknameinuse(self, connection, event):
        """Overcome nick collisions"""
        newnick = connection.get_nickname() + "_"
        print "Nickname in use, adding underscore", newnick
        connection.nick(newnick)

    def routine_ping(self, first_run = False):
        """Ping server to know when try to reconnect to a new server."""
        global pinger
        if not first_run and not self.pong_received:
            print "Ping reply timeout, disconnecting from", self.connection.get_server_name()
            self.disconnect()
            return
        self.pong_received = False
        self.connection.ping(self.connection.get_server_name())
        pinger = Timer(ping_interval, self.routine_ping, ())
        pinger.start()

    def on_pong(self, connection, event):
        """React to pong"""
        self.pong_received = True

    def say(self, target, msg, do_say = True):
        """Send messages to channels/nicks"""
        target = target.lower()
        try:
            lines = msg.encode("UTF-8").split("\n")
            cur = 0
            for line in lines:
                for irc_msg in wrapper.wrap(line.strip("\r")):
                    print target, irc_msg
                    irc_msg += "\r\n"
                    if target not in lastsaid.keys():
                        lastsaid[target] = 0
                    while time.time()-lastsaid[target] < delay_btw_msgs:
                        time.sleep(0.2)
                    lastsaid[target] = time.time()
                    if do_say:
                        self.connection.privmsg(target, irc_msg)
                    else:
                        self.connection.notice(target, irc_msg)
                    cur += 1
                    if cur % max_seq_msgs == 0:
                        time.sleep(delay_btw_seqs) # to avoid flood excess
        except ServerNotConnectedError:
            print "{" +target + " " + msg+"} SKIPPED!"
			
    def notice(self, target, msg):
        """Send notices to channels/nicks"""
        self.say(self, target, msg, False)

    def on_welcome(self, connection, event):
        """Do stuff when welcomed to server"""
        print "Connected to", self.connection.get_server_name()
        if password is not None:
            bot.say("NickServ", "identify " + password)
        if vhost:
            bot.say("HostServ", "ON")
        # ensure handler is present exactly once by removing it before adding
        self.connection.remove_global_handler("ctcp", self.handle_ctcp)            
        self.connection.add_global_handler("ctcp", self.handle_ctcp)
        for channelSet in mirrors:
            for channel in channelSet:
                if isIrcChannel(channel):
                    connection.join(channel)
                    print "Joined " + channel
        self.routine_ping(first_run = True)

    def on_pubmsg(self, connection, event):
        """React to channel messages"""
        args = event.arguments()
        source = event.source().split('!')[0]
        target = event.target().lower()
        cmds = args[0].split()
        msg = name_start + source + name_end + " "
        for raw in args:
            msg += decode_irc(raw) + "\n"
        broadcast(msg.rstrip("\n"), target)

    def handle_ctcp(self, connection, event):
        """Handle CTCP events for emoting"""
        args = event.arguments()
        source = event.source().split('!')[0]
        target = event.target().lower()
        if args[0] == 'ACTION' and len(args) == 2:
            # An emote/action message has been sent to us
            broadcast(emote_char + " " + source + " " + decode_irc(args[1]) + "\n", target)

# *** Start everything up! ***

signal.signal(signal.SIGINT, signal_handler)

print "Running", botname, "Gateway Bot", version
try:
    import Skype4Py
except:
    print 'Failed to locate Skype4Py API! Quitting...'
    sys.exit()
try:
    skype = Skype4Py.Skype();
except:
    print 'Cannot open Skype API! Quitting...'
    sys.exit()

if skype.Client.IsRunning:
    print 'Skype process found!'
elif not skype.Client.IsRunning:
    try:
        print 'Starting Skype process...'
        skype.Client.Start()
    except:
        print 'Failed to start Skype process! Quitting...'
        sys.exit()

try:
    skype.Attach();
    skype.OnMessageStatus = OnMessageStatus
    skype.OnNotify = OnNotify
except:
    print 'Failed to connect! You have to log in to your Skype instance and enable access to Skype for Skype4Py! Quitting...'
    sys.exit()

print 'Skype API initialised.'

topics = "["
for channelSet in mirrors:
    for channel in channelSet:
        if isIrcChannel(channel): continue
        print channel
        chat = skype.FindChatUsingBlob(channel)
        topic = chat.FriendlyName
        print "Joined \"" + topic + "\""
        topics += cut_title(topic) + "|"
        skypeChannels[channel] = chat
        blobs[chat] = channel
topics = topics.rstrip("|") + "]"

bot = MirrorBot()
print "Starting IRC bot..."
bot.start()
