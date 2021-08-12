#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# ping-watchdog.py
#
# Purpose: reboot the machine if pinging host failed
#
# Copyright (c) 2021 by bgeneto <b g e n e t o at g m a i l  dot c o m>
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

__author__ = "bgeneto"
__maintainer__ = "bgeneto"
__contact__ = "bgeneto at gmail"
__copyright__ = "Copyright 2021, bgeneto"
__license__ = "GPLv3"
__status__ = "Production"
__date__ = "2021/08/12"
__version__ = "1.0.3"

import configparser
import logging
import os
import re
import sys
import time
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def script_full_path_name():
    '''
    Return the full path and the name of this script
    '''
    script_name = os.path.splitext(os.path.basename(sys.argv[0]))[0]
    script_dir = os.path.dirname(sys.argv[0])
    if script_dir == '':
        script_dir = '.'
    script_path_name = os.path.abspath(os.path.join(script_dir, script_name))
    return script_path_name


class MyLog:
    '''
    Take care of log config/format and log rotation
    '''

    log_msg = '(ping-watchdog) ping failed. requesting reboot'

    def __init__(self, log_max_size=0, fn=None):
        self.log_max_size = log_max_size
        self.log_file = fn
        if not fn:
            self.log_file = script_full_path_name() + '.log'
        else:
            if os.path.isdir(fn):
                script_name = os.path.splitext(
                    os.path.basename(sys.argv[0]))[0]
                self.log_file = os.path.join(
                    os.path.abspath(fn), script_name + '.log')

        self._log_setup()
        self._log_rotate()

    def _log_setup(self):
        '''
        Setup both file and console logging
        '''
        # setup console logging first
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(message)s')
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        logger.setLevel(logging.DEBUG)

        # setup file logging
        fh = logging.FileHandler(self.log_file, mode='a')
        fh.setLevel(logging.FATAL)
        formatter = logging.Formatter('%(asctime)s | %(message)s')
        fh.setFormatter(formatter)
        logger.addHandler(fh)

    def _log_rotate(self):
        '''
        Truncate/empty log file if oversized
        '''
        if int(self.log_max_size) > 0:
            fsize = os.path.getsize(self.log_file)
            if fsize > self.log_max_size:
                logger.debug('log file too large. trucating log file')
                with open(self.log_file, 'w') as f:
                    pass
            else:
                logger.debug('log rotation not required')
        else:
            logger.debug('log rotation disabled')

    @staticmethod
    def notify():
        '''
        send system log notification message
        '''
        logger.fatal(MyLog.log_msg)
        if os.name != 'nt':
            os.system('logger "%s"' % MyLog.log_msg)


class MyConfig():
    '''
    config file factory
    '''

    def __init__(self, items, fn=None):
        # config items are dictonaries
        self.items = items
        self.config = None
        # define config file extension based on OS
        self.config_file_ext = '.ini'
        if os.name != 'nt':
            self.config_file_ext = '.conf'

        self.config_file = fn
        if not fn:
            self.config_file = script_full_path_name() + self.config_file_ext
        else:
            if os.path.isdir(fn):
                script_name = os.path.splitext(
                    os.path.basename(sys.argv[0]))[0]
                self.config_file = os.path.join(
                    os.path.abspath(fn), script_name + self.config_file_ext)

        # create or read config file
        self._create_read_config()

    def _create_read_config(self):
        '''
        Create or read a configuration file
        '''
        self.config = configparser.ConfigParser()
        # create config file if not already exists
        if not os.path.isfile(self.config_file):
            logger.debug("config file not found")
            logger.debug("creating default config file")
            for section, settings in self.items.items():
                self.config.add_section(section)
                for setting, value in settings.items():
                    self.set_config_value(section, setting, value)
            # write to config file
            with open(self.config_file, "w") as f:
                try:
                    self.config.write(f)
                except Exception as _:
                    logger.fatal(
                        "unable to create default config file. check permissions")
                    sys.exit(1)
        # config file exists. read from config file
        else:
            self.config.read(self.config_file)
        return self.config

    def get_config_value(self, section, setting):
        '''
        Return a setting value
        '''
        if not self.config:
            self.config = self.read_config()

        value = self.config.get(self.main_section, setting)

        return value

    def set_config_value(self, section, setting, value):
        '''
        Attribute a setting value
        '''
        if self.config:
            self.config.set(section, setting, str(value))

    def __str__(self):
        return str(self.items)


class Pushover:
    def __init__(self, key, token):
        self.key = key
        self.token = token

    def notify(self):
        """Send a pushover message"""
        import http.client
        import urllib
        import socket

        if len(self.key) < 30 or len(self.token) < 30:
            logger.debug('pushover not properly configured')
            return

        text = "ping failed. performing reboot for %s" % socket.gethostname()
        content = {"message": text, "user": self.key, "token": self.token}
        sent = True
        try:
            conn = http.client.HTTPSConnection("api.pushover.net:443")
            conn.request("POST", "/1/messages.json",
                         urllib.parse.urlencode(content),
                         {"Content-type": "application/x-www-form-urlencoded"})
            response = conn.getresponse()
            if int(response.status) != 200:
                sent = False
        except:
            sent = False

        if not sent:
            logger.debug('failed sending pushover notification')
        else:
            logger.debug('push notification sent')


def is_tool(name):
    """Check whether `name` is on PATH and marked as executable."""

    from shutil import which
    return which(name) is not None


def ping_attempts(cfg):
    '''Perform ping attempts'''
    if not is_tool('ping'):
        logger.fatal('ping command not found')
        sys.exit(1)

    output = '/dev/null'
    ping_cmd = 'ping -c 1 -W'
    if os.name == 'nt':
        ping_cmd = 'ping -n 1 -w'
        output = 'NUL'

    failed_attempts = 0
    for _ in range(0, 2 * int(cfg.config['ping']['attempts'])):
        logger.debug('pinging %s' % cfg.config['ping']['host'])
        result = os.system('%s %i %s > %s 2>&1' %
                           (ping_cmd, int(cfg.config['ping']['timeout']), cfg.config['ping']['host'], output))
        if result != 0:
            failed_attempts += 1

    return failed_attempts


def ping_host(cfg):
    count = 0
    while count < int(cfg.config['ping']['retries']):
        if count > 0:
            logger.debug("waiting %ss for the next ping retry" %
                         cfg.config['ping']['retry_wait'])
            time.sleep(int(cfg.config['ping']['retry_wait']))
        failed_attempts = ping_attempts(cfg)
        logger.debug("ping failed attempts: %s" % failed_attempts)
        if failed_attempts <= int(cfg.config['ping']['attempts']):
            return True
        count += 1

    return False


def num_reboots_24h(cfg):
    '''
    Return number of reboots in the last 24h
    '''
    dt_lst = []
    with open(cfg.config['log']['log_file'], 'r') as f:
        lines = f.readlines()
        for line in lines:
            try:
                dt, rest = line.split('|')
                if rest.find(MyLog.log_msg) != -1:
                    dt, *_ = dt.split(',')  # discard milisecs
                    dt, *_ = dt.split('.')  # discard milisecs
                    dt_lst.append(datetime.strptime(dt, '%Y-%m-%d %H:%M:%S'))
            except Exception:
                continue

    yesterday = datetime.today() - timedelta(hours=24)
    count = 0
    for log_date in dt_lst:
        if log_date > yesterday:
            count = count + 1

    return count


def send_reboot_cmd(cfg):
    '''send reboot command'''
    # reboot command according to OS
    cmd = cfg.config['reboot']['reboot_cmd_nix']
    if os.name == 'nt':
        cmd = cfg.config['reboot']['reboot_cmd_win']

    # perform reboot
    result = os.system(cmd)

    if result != 0:
        return False

    return True


def notify_and_reboot(cfg):
    # check reboot threshold
    reboots = num_reboots_24h(cfg)
    logger.debug("number of reboot attemps in the last 24h: %s " % reboots)
    if reboots >= int(cfg.config['reboot']['max_reboots_per_day']):
        logger.fatal("reboot canceled. max reboots allowed in 24h reached")
    # send notification and perform reboot
    else:
        # send system/log and push notification before reboot command
        MyLog.notify()
        # send push notification
        push = Pushover(cfg.config['pushover']['pushover_user_key'],
                        cfg.config['pushover']['pushover_api_token'])
        push.notify()
        # finally reboot
        if not send_reboot_cmd(cfg):
            logger.fatal("reboot command failed")


def main():
    # setup log file
    log_file = ''  # leave empty for default value
    log_max_size = 2 * 1024 * 1024  # empty log file if larger than 2MB
    log = MyLog(log_max_size, log_file)

    # setup config file
    config_file = ''  # leave empty for default value
    config_items = {
        "ping": {
            "host": "127.0.0.1",
            "attempts": "4",
            "timeout": "2",
            "retries": "2",
            "retry_wait": "60"
        },
        "reboot": {
            "max_reboots_per_day": "3",
            "reboot_cmd_nix": "sudo /sbin/shutdown --no-wall --reboot +2",
            "reboot_cmd_win": "shutdown /r /t 120"
        },
        "pushover": {
            "pushover_user_key": "",
            "pushover_api_token": ""
        },
        "log": {
            "log_file": log.log_file,
            "log_max_size": log.log_max_size
        }
    }

    config = MyConfig(config_items, config_file)

    if ping_host(config):
        logger.fatal("no reboot required")
    else:
        notify_and_reboot(config)


if __name__ == '__main__':
    main()
