from threading import Event
import os
import sys
import time
import colorsys

import paho.mqtt.client as mqtt

import xbmc
import xbmcaddon

__addon__ = xbmcaddon.Addon()
__addondir__ = xbmc.translatePath(__addon__.getAddonInfo('profile'))
__cwd__ = __addon__.getAddonInfo('path')
__resource__ = xbmc.translatePath(os.path.join(__cwd__, 'resources', 'lib'))

sys.path.append(__resource__)

from settings import Settings
from tools import get_version, xbmclog
#from ambilight_controller import AmbilightController
#from theater_controller import TheaterController
#from static_controller import StaticController
import bridge
import ui
import algorithm
import image
import threading

xbmclog("Kodi Hue: In .(argv={}) service started, version: {}".format(
    sys.argv, get_version()))

ev = Event()
capture = xbmc.RenderCapture()
fmt = capture.getImageFormat()
# BGRA or RGBA
fmtRGBA = fmt == 'RGBA'

mqttc = mqtt.Client()
mqttc.connect("openhab.lan")
mqttc.loop_start()

class MyMonitor(xbmc.Monitor):

    def __init__(self, settings):
        xbmc.Monitor.__init__(self)
        self.settings = settings

    def onSettingsChanged(self):
        hue.settings.readxml()
        xbmclog('Kodi Hue: In onSettingsChanged() {}'.format(hue.settings))
        hue.update_controllers()

    def onNotification(self, sender, method, data):
        xbmclog('Kodi Hue: In onNotification(sender={}, method={}, data={})'
                .format(sender, method, data))

class MyPlayer(xbmc.Player):
    duration = 0
    playingvideo = False
    playlistlen = 0
    movie = False

    def __init__(self):
        xbmclog('Kodi Hue: In MyPlayer.__init__()')
        xbmc.Player.__init__(self)

    def onPlayBackStarted(self):
        xbmclog('Kodi Hue: In MyPlayer.onPlayBackStarted()')
        playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
        self.playlistlen = playlist.size()
        self.playlistpos = playlist.getposition()
        self.playingvideo = True
        self.duration = self.getTotalTime()
        state_changed("started", self.duration)

    def onPlayBackPaused(self):
        xbmclog('Kodi Hue: In MyPlayer.onPlayBackPaused()')
        state_changed("paused", self.duration)
        if self.isPlayingVideo():
            self.playingvideo = False

    def onPlayBackResumed(self):
        xbmclog('Kodi Hue: In MyPlayer.onPlayBackResume()')
        state_changed("resumed", self.duration)
        if self.isPlayingVideo():
            self.playingvideo = True
            if self.duration == 0:
                self.duration = self.getTotalTime()

    def onPlayBackStopped(self):
        xbmclog('Kodi Hue: In MyPlayer.onPlayBackStopped()')
        state_changed("stopped", self.duration)
        self.playingvideo = False
        self.playlistlen = 0

    def onPlayBackEnded(self):
        xbmclog('Kodi Hue: In MyPlayer.onPlayBackEnded()')
        # If there are upcoming plays, ignore
        if self.playlistpos < self.playlistlen-1:
            return

        self.playingvideo = False
        state_changed("stopped", self.duration)


class Hue:
    #theater_controller = None
    #ambilight_controller = None
    #static_controller = None

    def __init__(self, settings, args):
        self.settings = settings
        self.connected = True

        try:
            params = dict(arg.split("=") for arg in args.split("&"))
        except Exception:
            params = {}

        if params == {}:
            # if there's a bridge IP, try to talk to it.
            if self.settings.bridge_ip not in ["-", "", None]:
                result = bridge.user_exists(
                    self.settings.bridge_ip,
                    self.settings.bridge_user
                )
                if result:
                    self.connected = True
                    self.update_controllers()
        elif params['action'] == "discover":
            self.update_controllers()
        elif params['action'] == "reset_settings":
            os.unlink(os.path.join(__addondir__, "settings.xml"))
        elif params['action'] == "setup_theater_lights":
            xbmc.executebuiltin('NotifyAll({}, {})'.format(
                __addon__.getAddonInfo('id'), 'start_setup_theater_lights'))
        elif params['action'] == "setup_theater_subgroup":
            xbmc.executebuiltin('NotifyAll({}, {})'.format(
                __addon__.getAddonInfo('id'), 'start_setup_theater_subgroup'))
        elif params['action'] == "setup_ambilight_lights":
            xbmc.executebuiltin('NotifyAll({}, {})'.format(
                __addon__.getAddonInfo('id'), 'start_setup_ambilight_lights'))
        elif params['action'] == "setup_static_lights":
            xbmc.executebuiltin('NotifyAll({}, {})'.format(
                __addon__.getAddonInfo('id'), 'start_setup_static_lights'))
        else:
            # not yet implemented
            pass

#        if self.connected:
#            if self.settings.misc_initialflash:

    def update_controllers(self):
        xbmclog(
            'Kodi Hue: In Hue.update_controllers() instantiated following '
            )


class ColourTransition(object):
        shouldStop = False
        haveLast = False
        lastColor = None
        mqtt = None
        duration = 0
        hsvRatios = None
        thread = None
        ev = None

        def launch(self, algorithm, mqttc):
            self.ev = Event()
            self.ev.set()
            self.mqtt = mqttc
            self.thread = threading.Thread(target = self.initialize, args = (algorithm, mqttc))
            self.thread.start()
        def shouldStop(self):
            return self.shouldStop

        def stop(self):
            self.ev.set()
            self.shouldStop = True

        def pause(self):
            print "Pause transition thread"
            self.ev.clear()

        def resume(self):
            self.ev.set()

        def initialize(self, algorithm, mqttc):
            while self.shouldStop():
                if not self.ev.isSet():
                    self.ev.wait()
                if self.hsvRatios != None:
                    #print "Thread transition %d" %(self.duration)
                    h, s, v = self.hsvRatios.hue(
                        True, hue.settings.ambilight_min, hue.settings.ambilight_max)
                    self.lastColor, self.duration = algorithm.transition_rgb(self.lastColor, self.haveLast, self.hsvRatios, self.mqtt)
                    if self.lastColor != None:
                        self.haveLast = True
                    else:
                        self.haveLast = False

                if self.duration > 0:
                    time.sleep(self.duration / 50)
                else:
                    time.sleep(0.05)
            print "HUE thread stop"


        def transition(self, hsv_ratios):
            #print "HUE Transition"
            self.hsvRatios = hsv_ratios[0]

        def waitThread(self):
            self.thread.join()

def run():
    have_last = False
    last_ratios = []
    player = MyPlayer()
    if player is None:
        xbmclog('Kodi Hue: In run() could not instantiate player')
        return
    transition = ColourTransition()
    transition.launch(algorithm, mqttc)

    xbmclog('Kodi Hue: In run()')
    while not monitor.abortRequested():
        if not ev.is_set():
            startReadOut = False
            vals = {}
            if player.playingvideo:  # only if there's actually video
                transition.resume()
                try:
                    vals = capture.getImage(200)
                    if len(vals) > 0 and player.playingvideo:
                        startReadOut = True
                    if startReadOut:
                        screen = image.Screenshot(
                            capture.getImage())
                        hsv_ratios = screen.spectrum_hsv(
                            screen.pixels,
                            hue.settings.ambilight_threshold_value,
                            hue.settings.ambilight_threshold_saturation,
                            hue.settings.color_bias,
                            1,
#                            len(hue.ambilight_controller.lights)
                        )
                        #h, s, v = hsv_ratios[0].hue(
                        #        True, hue.settings.ambilight_min, hue.settings.ambilight_max)
                        #algorithm.transition_rgb(last_ratios, have_last,
                        #        hsv_ratios[0], mqttc )
                        #last_ratios = [hsv_ratios[0].h, hsv_ratios[0].s, hsv_ratios[0].v]
                        #have_last = True
                        transition.transition(hsv_ratios)
                        xbmclog('Kodi Hue: HSV values')
#                        for i in range(len(hue.ambilight_controller.lights)):
#                            algorithm.transition_colorspace(
#                                hue, hue.ambilight_controller.lights.values()[i], hsv_ratios[i], )
                except ZeroDivisionError:
                    pass
        else:
            transition.pause()

        if monitor.waitForAbort(0.5):
            transition.stop()
            xbmclog('Kodi Hue: In run() deleting player')
            del player  # might help with slow exit.
    transition.waitThread()
    del transition

def state_changed(state, duration):
    xbmclog('Kodi Hue: In state_changed(state={}, duration={})'.format(
        state, duration))

    if (xbmc.getCondVisibility('Window.IsActive(screensaver-atv4.xml)') or
            xbmc.getCondVisibility('Window.IsActive(screensaver-video-main.xml)')):
        return

    if duration < hue.settings.misc_disableshort_threshold and hue.settings.misc_disableshort:
        return

    if state == "started":
        # start capture when playback starts
        capture_width = 32  # 100
        capture_height = capture_width / capture.getAspectRatio()
        if capture_height == 0:
            capture_height = capture_width  # fix for divide by zero.
        capture.capture(int(capture_width), int(capture_height))

    if state == "started" or state == "resumed":
        ev.set()
#        hue.theater_controller.on_playback_start()
#        hue.ambilight_controller.on_playback_start()
#        hue.static_controller.on_playback_start()
        ev.clear()

    elif state == "paused":
        ev.set()
#        hue.theater_controller.on_playback_pause()
#        hue.ambilight_controller.on_playback_pause()
#        hue.static_controller.on_playback_pause()

    elif state == "stopped":
        ev.set()
#        hue.theater_controller.on_playback_stop()
#        hue.ambilight_controller.on_playback_stop()
#        hue.static_controller.on_playback_stop()

if (__name__ == "__main__"):
    settings = Settings()
    monitor = MyMonitor(settings)

    args = None
    if len(sys.argv) == 2:
        args = sys.argv[1]
    hue = Hue(settings, args)
    while not hue.connected and not monitor.abortRequested():
        time.sleep(1)
    run()
