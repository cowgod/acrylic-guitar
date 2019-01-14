#!/usr/bin/python


try:
   import re
   import sys
   import time
   import pygame
   import random
   import logging
   import threading
   import pygame.midi
   import RPi.GPIO as GPIO

   import pprint # DEBUG
   import inspect


except RuntimeError:
   print("Error importing modules")
   sys.exit(1)


# DEBUG
def print_signature(func):
   argspec = inspect.getargspec(func)
   return func.__name__ + inspect.formatargspec(*argspec)



logging.basicConfig(level=logging.DEBUG, format='(%(threadName)-15s) %(message)s',)



# {{{ class DisplayMode:
class DisplayMode:
   # All LEDS off
   off = 0

   # Cycle through random colors. No MIDI input
   random_glow = 1

   # Flash random pre-defined colors, jumping directly to each. No MIDI input
   crazy_flash_jump = 2

   # Glow a color based on the lowest MIDI key currently on
   glow_lowest_midi_key_on = 3

   # Flash a color based on the lowest MIDI key currently on
   flash_lowest_midi_key_on = 4

   # Flash random pre-defined colors, fading between each. No MIDI input
   crazy_flash_fade = 5

   # Cycle through random colors, with intensity varying between
   # 50% and 100% based on average MIDI key velocity
   random_glow_midi_velocity = 6


   # {{{ def get_modes(self):
   @classmethod
   def get_modes(cls):
      return [
         cls.off,
         cls.random_glow,
         cls.crazy_flash_jump,
         cls.glow_lowest_midi_key_on,
         cls.flash_lowest_midi_key_on,
         cls.crazy_flash_fade,
         cls.random_glow_midi_velocity,
      ]
   # def get_modes(cls):


   # }}}
# class DisplayMode:


# }}}
# {{{ class MidiMessageType:
class MidiMessageType:
   # TODO: This is actually more complicated than this
   # http://www.midi.org/techspecs/midimessages.php
   note = 144
   control_change = 176
   # The Oxygen8 also sends two other CC messages to select a bank when
   # changing programs -- the full sequence for selecting patch 4 is:
   # [[[176, 0, 0, 0], 108813]]
   # [[[176, 32, 0, 0], 108813]]
   # [[[192, 3, 0, 0], 108814]]
   program_change = 192


# }}}
# {{{ class Color:
class Color:
   # {{{ def __init__(self, red = 0, green = 0, blue = 0):
   def __init__(self, red = 0, green = 0, blue = 0):
      self.red = red
      self.green = green
      self.blue = blue
   # def __init__(self, red = 0, green = 0, blue = 0):


   # }}}
# class Color:


# }}}
# {{{ class AcrylicGuitar:
class AcrylicGuitar:


   # Constructor
   # {{{ def __init__(self):
   def __init__(self):
      # Pin assignments (Board-numbering)
      self.PIN_R = 12
      self.PIN_G = 11
      self.PIN_B = 13

      self.PIN_LED = 15


      # PWM frequency in Hz
      self.PWM_FREQUENCY = 100


      # These are the system interfaces that shouldn't be used
      self.MIDI_INTERFACES_TO_IGNORE = ['Midi Through Port-0', 'Synth input port (2225:0)']


      # How many percentage points above and below the requested value should we glow
      self.GLOW_COLOR_DIFFUSION = 5


      # Interval (sec) between MIDI Reader loops
      self.MIDI_READER__INTERVAL = (1 / 100)

      # Minimum interval (sec) to wait between Display Manager loops
      self.DISPLAY_MANAGER__MIN_INTERVAL = (1 / 100)

      # Interval (sec) between individual color steps in glow modes
      self.DISPLAY_MANAGER__GLOW_INTERVAL = 0.01

      # Interval (sec) between colors in glow modes
      self.DISPLAY_MANAGER__GLOW_COLOR_SPEED = 1.5

      # Interval (sec) between colors in flash modes
      self.DISPLAY_MANAGER__FLASH_INTERVAL = 0.065

      # How long (sec) to take to fade note color to black
      self.DISPLAY_MANAGER__FLASH_NOTE_DURATION = 3.0



      self.MAX_VELOCITY = 127
      self.NUM_KEYS     = 127
      self.NUM_NOTES    =  12

      self.NOTE_NAMES = {}
      self.NOTE_NAMES['C']  =  0
      self.NOTE_NAMES['Cs'] =  1
      self.NOTE_NAMES['D']  =  2
      self.NOTE_NAMES['Ds'] =  3
      self.NOTE_NAMES['E']  =  4
      self.NOTE_NAMES['F']  =  5
      self.NOTE_NAMES['Fs'] =  6
      self.NOTE_NAMES['G']  =  7
      self.NOTE_NAMES['Gs'] =  8
      self.NOTE_NAMES['A']  =  9
      self.NOTE_NAMES['As'] = 10
      self.NOTE_NAMES['B']  = 11

      

      # Initialize colors
      self.colors = {}
      self.colors['black']   = {'red':   0, 'green':   0, 'blue':   0}
      self.colors['white']   = {'red': 100, 'green': 100, 'blue': 100}

      self.colors['red']     = {'red': 100, 'green':   0, 'blue':   0}
      self.colors['green']   = {'red':   0, 'green': 100, 'blue':   0}
      self.colors['blue']    = {'red':   0, 'green':   0, 'blue': 100}

      self.colors['cyan']    = {'red':   0, 'green': 100, 'blue': 100}
      self.colors['magenta'] = {'red': 100, 'green':   0, 'blue': 100}
      self.colors['yellow']  = {'red': 100, 'green': 100, 'blue':   0}

      self.colors['pink']    = {'red':  90, 'green':   9, 'blue':  35}
      self.colors['orange']  = {'red': 100, 'green':  13, 'blue':   0}


      self.current_color_name = 'black'
      self.current_color      = self.colors[self.current_color_name]


      self.keys = []
      for key in range(0, self.NUM_KEYS):
         self.keys.append(0)
      # for key in range(0, self.NUM_KEYS):

      self.notes = []
      for note in range(0, self.NUM_NOTES):
         self.notes.append(0)
      # for note in range(0, self.NUM_NOTES):

      self.max_key_velocity = 0
      self.lowest_key_on    = None
      self.lowest_note_on   = None


      #self.display_mode = DisplayMode.off
      self.display_mode = DisplayMode.random_glow


      # Initialize a lock to let us synchronize accessing the keys and notes instance variables
      self.midi_data_lock = threading.Lock()


      # Initialize an event to let the midi_reader thread tell
      # the display_manager thread that we've changed modes
      self.display_mode_change_event = threading.Event()

      # Initialize an event to let the midi_reader thread tell
      # the display_manager thread that we've changed notes
      self.note_change_event = threading.Event()


      # Initialize the variables to be used by __initialize_midi() and __initialize_display()
      self.__midi_interfaces = None
      self.red_led           = None
      self.green_led         = None
      self.blue_led          = None
      self.status_led        = None


      # Initialize the MIDI library
      self.__init_midi()
   # def __init__(self):


   # }}}
   # {{{ def __init_midi(self):
   def __init_midi(self):
      pygame.init()
      pygame.midi.init()

      self.__midi_interfaces = {}
   # def __init_midi(self):


   # }}}
   # {{{ def __init_display(self):
   def __init_display(self):
      #GPIO.setwarnings(False)
      GPIO.setmode(GPIO.BOARD)


      GPIO.setup([self.PIN_R, self.PIN_G, self.PIN_B], GPIO.OUT, initial=GPIO.LOW)

      self.red_led = GPIO.PWM(self.PIN_R, self.PWM_FREQUENCY)
      self.red_led.start(self.current_color['red'])

      self.green_led = GPIO.PWM(self.PIN_G, self.PWM_FREQUENCY)
      self.green_led.start(self.current_color['green'])

      self.blue_led = GPIO.PWM(self.PIN_B, self.PWM_FREQUENCY)
      self.blue_led.start(self.current_color['blue'])

      GPIO.setup(self.PIN_LED, GPIO.OUT)

      # Turn on status LED to indicate we're running
      GPIO.output(self.PIN_LED, GPIO.HIGH)
   # def __init__(self):


   # }}}


   # Action Methods
   # {{{ def display_color_name(self, color_name, update_current_color = True):
   def display_color_name(self, color_name, update_current_color = True):
      if color_name in self.colors:
         self.display_color(self.colors[color_name], update_current_color)
      else:
         raise RuntimeException("Invalid color name requested: '%s" % color_name)
      # if color_name in self.colors:
   # def display_color_name(self, color_name, update_current_color = True):


   # }}}
   # {{{ def display_color(self, color, update_current_color = True):
   def display_color(self, color, update_current_color = True):
      self.display_color_rgb(color['red'], color['green'], color['blue'], update_current_color)
   # def display_color(self, color, update_current_color = True):


   # }}}
   # {{{ def display_current_color(self):
   def display_current_color(self):
      self.display_color(self.current_color, False)
   # def display_current_color(self):


   # }}}
   # {{{ def display_color_rgb(self, red, green, blue, update_current_color = True):
   def display_color_rgb(self, red, green, blue, update_current_color = True):
      red   = constrain(float(red)  , 0.0, 100.0)
      green = constrain(float(green), 0.0, 100.0)
      blue  = constrain(float(blue) , 0.0, 100.0)

#      logging.debug("Displaying %d/%d/%d" % (red, green, blue))

      self.red_led.ChangeDutyCycle(red)
      self.green_led.ChangeDutyCycle(green)
      self.blue_led.ChangeDutyCycle(blue)

      if update_current_color:
         self.set_current_color_rgb(red, green, blue)
   # def display_color_rgb(self, red, green, blue, update_current_color = True):


   # }}}
   # {{{ def cleanup(self):
   def cleanup(self):
      if self.red_led:   self.red_led.stop()
      if self.green_led: self.green_led.stop()
      if self.blue_led:  self.blue_led.stop()

      for interface_index, interface in self.__midi_interfaces.iteritems():
         interface.close()

      GPIO.output(self.PIN_LED, GPIO.LOW)

      GPIO.cleanup()
   # def cleanup(self):


   # }}}

   # {{{ def get_color_boundaries_for_glow(self, color):
   def get_color_boundaries_for_glow(self, color):
      # If the color to glow is black, stay on pure black
      if color['red'] == 0 and color['green'] == 0 and color['blue'] == 0:
         min_color = self.colors['black']
         max_color = self.colors['black']
      else:
         min_color = {
            'red'  : constrain( (color['red']   - self.GLOW_COLOR_DIFFUSION), 0.0, 100.0),
            'green': constrain( (color['green'] - self.GLOW_COLOR_DIFFUSION), 0.0, 100.0),
            'blue' : constrain( (color['blue']  - self.GLOW_COLOR_DIFFUSION), 0.0, 100.0),
         }

         max_color = {
            'red'  : constrain( (color['red']   + self.GLOW_COLOR_DIFFUSION), 0.0, 100.0),
            'green': constrain( (color['green'] + self.GLOW_COLOR_DIFFUSION), 0.0, 100.0),
            'blue' : constrain( (color['blue']  + self.GLOW_COLOR_DIFFUSION), 0.0, 100.0),
         }
      # else:

      return [min_color, max_color]
   # def get_color_boundaries_for_glow(self, color):


   # }}}


   # Modifier methods
   # {{{ def set_current_color(self, color):
   def set_current_color(self, color):
      self.set_current_color_rgb(color['red'], color['green'], color['blue'])
   # def set_current_color(self, color):


   # }}}
   # {{{ def set_current_color_red(self, red):
   def set_current_color_red(self, red):
      self.set_current_color_rgb(red, self.current_color['green'], self.current_color['blue'])
   # def set_current_color_red(self, red):


   # }}}
   # {{{ def set_current_color_green(self, green):
   def set_current_color_green(self, green):
      self.set_current_color_rgb(self.current_color['red'], green, self.current_color['blue'])
   # def set_current_color_green(self, green):


   # }}}
   # {{{ def set_current_color_blue(self, blue):
   def set_current_color_blue(self, blue):
      self.set_current_color_rgb(self.current_color['red'], self.current_color['green'], blue)
   # def set_current_color_blue(self, blue):


   # }}}
   # {{{ def set_current_color_rgb(self, red, green, blue):
   def set_current_color_rgb(self, red, green, blue):
      self.current_color = {'red': red, 'green': green, 'blue': blue}
   # def set_current_color_rgb(self, red, green, blue):


   # }}}

   # {{{ def fade_to_color_name(self, end_color_name, time_to_fade, stop_events = []):
   def fade_to_color_name(self, end_color_name, time_to_fade, scale_to_midi_velocity = False, stop_events = []):
      end_color = self.colors[end_color_name if end_color_name in self.colors else 'black']

      return self.fade_from_color_to_color_rgb(
         self.current_color['red'], self.current_color['green'], self.current_color['blue'],
         end_color['red']  , end_color['green']  , end_color['blue']  ,
         time_to_fade, scale_to_midi_velocity, stop_events
      )
   # def fade_to_color_name(self, end_color_name, time_to_fade, stop_events = []):


   # }}}
   # {{{ def fade_to_color(self, end_color, time_to_fade, stop_events = []):
   def fade_to_color(self, end_color, time_to_fade, scale_to_midi_velocity = False, stop_events = []):
      return self.fade_from_color_to_color_rgb(
         self.current_color['red'], self.current_color['green'], self.current_color['blue'],
         end_color['red']  , end_color['green']  , end_color['blue']  ,
         time_to_fade, scale_to_midi_velocity, stop_events
      )
   # def fade_to_color(self, end_color, time_to_fade, stop_events = []):


   # }}}
   # {{{ def fade_from_color_to_color(self, start_color, end_color, time_to_fade, scale_to_midi_velocity = False, stop_events = []):
   def fade_from_color_to_color(self, start_color, end_color, time_to_fade, scale_to_midi_velocity = False, stop_events = []):
      return self.fade_from_color_to_color_rgb(
         start_color['red'], start_color['green'], start_color['blue'],
         end_color['red']  , end_color['green']  , end_color['blue']  ,
         time_to_fade, scale_to_midi_velocity, stop_events
      )
   # def fade_from_color_to_color(self, start_color, end_color, time_to_fade, scale_to_midi_velocity = False, stop_events = []):


   # }}}
   # {{{ def fade_from_color_to_color_rgb(self, start_red, start_green, start_blue, end_red, end_green, end_blue, time_to_fade, scale_to_midi_velocity = False, stop_events = []):
   def fade_from_color_to_color_rgb(self, start_red, start_green, start_blue, end_red, end_green, end_blue, time_to_fade, scale_to_midi_velocity = False, stop_events = []):
      # Fade from start color to end color in a certain number of seconds

      # Make sure we're working with floats
      start_red    = float(start_red)
      start_green  = float(start_green)
      start_blue   = float(start_blue)

      end_red      = float(end_red)
      end_green    = float(end_green)
      end_blue     = float(end_blue)

      time_to_fade = float(time_to_fade)


      # If the time_to_fade is zero, we don't need to bother fading
      if time_to_fade == 0:
         self.display_color_rgb(end_red, end_green, end_blue)
         return True


      red_increasing   = (end_red   > start_red)
      green_increasing = (end_green > start_green)
      blue_increasing  = (end_blue  > start_blue)

      red_decreasing   = (end_red   < start_red)
      green_decreasing = (end_green < start_green)
      blue_decreasing  = (end_blue  < start_blue)


      red_interval   = (end_red   - start_red)   / (time_to_fade / self.DISPLAY_MANAGER__GLOW_INTERVAL)
      green_interval = (end_green - start_green) / (time_to_fade / self.DISPLAY_MANAGER__GLOW_INTERVAL)
      blue_interval  = (end_blue  - start_blue)  / (time_to_fade / self.DISPLAY_MANAGER__GLOW_INTERVAL)


      color = {'red': float(start_red), 'green': float(start_green), 'blue': float(start_blue)}


#      logging.debug("FADE: (%d, %d, %d) => (%d, %d, %d) in %0.2f sec", start_red, start_green, start_blue, end_red, end_green, end_blue, time_to_fade)
#      logging.debug("INTERVALS: %0.2f / %0.2f/ %0.2f", red_interval, green_interval, blue_interval)
#      logging.debug("EVENTS: %s", str(stop_events))


      while True:
         # Display the new color
         color_to_display = color
         if scale_to_midi_velocity:
            color_to_display = AcrylicGuitar.scale_color_brightness(color, constrain((self.max_key_velocity / self.MAX_VELOCITY), 0.5, 1.0))

         self.display_color(color_to_display)
         time.sleep(self.DISPLAY_MANAGER__GLOW_INTERVAL)


         # Increment (or decrement) each number according to the calculated interval
         color['red']   = constrain(color['red']   + red_interval  , start_red  , end_red)
         color['green'] = constrain(color['green'] + green_interval, start_green, end_green)
         color['blue']  = constrain(color['blue']  + blue_interval , start_blue , end_blue)


         # See if any of the stop events are set
         for event in stop_events:
            if event.is_set():
               return False
            # if event.is_set():
         # for event in stop_events:


         # See if any of our values have reached their targets
         if red_increasing:
            if color['red'] >= end_red:
               break
         elif red_decreasing:
            if color['red'] <= end_red:
               break
         # elif red_decreasing:

         if green_increasing:
            if color['green'] >= end_green:
               break
         elif green_decreasing:
            if color['green'] <= end_green:
               break
         # elif green_decreasing:

         if blue_increasing:
            if color['blue'] >= end_blue:
               break
         elif blue_decreasing:
            if color['blue'] <= end_blue:
               break
         # elif blue_decreasing:
      # while True:


      # Explicitly display the final color just to be sure we end up exactly where we were headed
      self.display_color_rgb(end_red, end_green, end_blue)


      return True
   # def fade_from_color_to_color_rgb(self, start_red, start_green, start_blue, end_red, end_green, end_blue, time_to_fade, scale_to_midi_velocity = False, stop_events = []):


   # }}}


   # Display Mode methods
   # {{{ def turn_off(self, stop_event):
   def turn_off(self, stop_event):
      self.fade_to_color_name('black', self.DISPLAY_MANAGER__FLASH_INTERVAL, False, [stop_event, self.display_mode_change_event])

      while(not(stop_event.is_set() or self.display_mode_change_event.is_set())):
         time.sleep(self.DISPLAY_MANAGER__MIN_INTERVAL)
      # while(not(stop_event.is_set() or self.display_mode_change_event.is_set())):
   # def turn_off(self, stop_event):


   # }}}
   # {{{ def glow_color_cycle(self, stop_event, scale_to_midi_velocity = False):
   def glow_color_cycle(self, stop_event, scale_to_midi_velocity = False):
      while(not(stop_event.is_set() or self.display_mode_change_event.is_set())):
         self.fade_to_color_name('red'  , self.DISPLAY_MANAGER__GLOW_COLOR_SPEED, scale_to_midi_velocity, [stop_event, self.display_mode_change_event])
         if stop_event.is_set() or self.display_mode_change_event.is_set(): break

         self.fade_to_color_name('yellow', self.DISPLAY_MANAGER__GLOW_COLOR_SPEED, scale_to_midi_velocity, [stop_event, self.display_mode_change_event])
         if stop_event.is_set() or self.display_mode_change_event.is_set(): break

         self.fade_to_color_name('green', self.DISPLAY_MANAGER__GLOW_COLOR_SPEED, scale_to_midi_velocity, [stop_event, self.display_mode_change_event])
         if stop_event.is_set() or self.display_mode_change_event.is_set(): break

         self.fade_to_color_name('cyan', self.DISPLAY_MANAGER__GLOW_COLOR_SPEED, scale_to_midi_velocity, [stop_event, self.display_mode_change_event])
         if stop_event.is_set() or self.display_mode_change_event.is_set(): break

         self.fade_to_color_name('blue', self.DISPLAY_MANAGER__GLOW_COLOR_SPEED, scale_to_midi_velocity, [stop_event, self.display_mode_change_event])
         if stop_event.is_set() or self.display_mode_change_event.is_set(): break

         self.fade_to_color_name('magenta', self.DISPLAY_MANAGER__GLOW_COLOR_SPEED, scale_to_midi_velocity, [stop_event, self.display_mode_change_event])
         if stop_event.is_set() or self.display_mode_change_event.is_set(): break
      # while(not(stop_event.is_set() or self.display_mode_change_event.is_set())):
   # def glow_color_cycle(self, stop_event, scale_to_midi_velocity = False):


   # }}}
   # {{{ def crazy_flash(self, stop_event, fade_between_colors = False):
   def crazy_flash(self, stop_event, fade_between_colors = False):
      while(not(stop_event.is_set() or self.display_mode_change_event.is_set())):
         # Pick a new color at random, but be sure it's not black or the current color
         new_color_name = None
         while new_color_name in [None, 'black', self.current_color_name]:
            new_color_name = random.choice(list(self.colors.keys()))

         self.current_color_name = new_color_name

         if fade_between_colors:
            self.current_color_name = new_color_name
            self.fade_to_color_name(new_color_name, self.DISPLAY_MANAGER__FLASH_INTERVAL, False, [stop_event, self.display_mode_change_event])
         else:
            self.fade_to_color_name(new_color_name, 0, False, [stop_event, self.display_mode_change_event])
            time.sleep(self.DISPLAY_MANAGER__FLASH_INTERVAL)
         # else:
      # while(not(stop_event.is_set() or self.display_mode_change_event.is_set())):
   # def crazy_flash(self, stop_event, fade_between_colors = False):


   # }}}
   # {{{ def glow_color(self, stop_event):
   def glow_color(self, color, stop_event):
      min_color, max_color = self.get_color_boundaries_for_glow(color)

      while(not(stop_event.is_set() or self.display_mode_change_event.is_set())):
         self.fade_to_color(min_color, self.DISPLAY_MANAGER__GLOW_COLOR_SPEED, False, [stop_event, self.display_mode_change_event])
         if stop_event.is_set() or self.display_mode_change_event.is_set(): break

         self.fade_to_color(max_color, self.DISPLAY_MANAGER__GLOW_COLOR_SPEED, False, [stop_event, self.display_mode_change_event])
         if stop_event.is_set() or self.display_mode_change_event.is_set(): break
      # while(not(stop_event.is_set() or self.display_mode_change_event.is_set())):
   # def glow_color_cycle(self, stop_event):


   # }}}
   # {{{ def glow_lowest_note_color(self, stop_event):
   def glow_lowest_note_color(self, stop_event):
      started_mode = True

      while(not(stop_event.is_set() or self.display_mode_change_event.is_set())):
         # Keep track of whether we just started this mode or we just changed a note, so
         # we can fade quickly to the new color
         fade_quickly = started_mode or self.note_change_event.is_set()
         started_mode = False

         # We're reading the current note, so clear the event if it's set
         self.note_change_event.clear()

         # Grab a copy of it in case it gets updated while we're comparing
         lowest_note = self.lowest_note_on

         # Find the corresponding color for the note
         color = None
         if lowest_note == 0:
            color = self.colors['blue']
         elif lowest_note == 1:
            color = self.colors['orange']
         elif lowest_note == 2:
            color = self.colors['cyan']
         elif lowest_note == 3:
            color = self.colors['yellow']
         elif lowest_note == 4:
            color = self.colors['red']
         elif lowest_note == 5:
            color = self.colors['magenta']
         elif lowest_note == 6:
            color = self.colors['blue']
         elif lowest_note == 7:
            color = self.colors['pink']
         elif lowest_note == 8:
            color = self.colors['red']
         elif lowest_note == 9:
            color = self.colors['green']
         elif lowest_note == 10:
            color = self.colors['orange']
         elif lowest_note == 11:
            color = self.colors['pink']
         else:
            #color = {'red': 50, 'green': 25, 'blue': 25}
            color = self.colors['black']



         min_color, max_color = self.get_color_boundaries_for_glow(color)

         time_to_fade = self.DISPLAY_MANAGER__FLASH_INTERVAL if fade_quickly else self.DISPLAY_MANAGER__GLOW_COLOR_SPEED
         self.fade_to_color(min_color, time_to_fade, False, [stop_event, self.display_mode_change_event, self.note_change_event])
         if self.note_change_event.is_set(): continue
         if stop_event.is_set() or self.display_mode_change_event.is_set(): break

         self.fade_to_color(max_color, self.DISPLAY_MANAGER__GLOW_COLOR_SPEED, False, [stop_event, self.display_mode_change_event, self.note_change_event])
         if self.note_change_event.is_set(): continue
         if stop_event.is_set() or self.display_mode_change_event.is_set(): break
      # while(not(stop_event.is_set() or self.display_mode_change_event.is_set())):
   # def glow_lowest_note_color(self, stop_event):


   # }}}
   # {{{ def flash_lowest_note_color(self, stop_event):
   def flash_lowest_note_color(self, stop_event):
      started_mode = True

      while(not(stop_event.is_set() or self.display_mode_change_event.is_set())):
         # Keep track of whether we just started this mode or we just changed a note, so
         # we can fade quickly to the new color
         fade_quickly = started_mode or self.note_change_event.is_set()
         started_mode = False

         # We're reading the current note, so clear the event if it's set
         self.note_change_event.clear()

         # Grab a copy of it in case it gets updated while we're comparing
         lowest_note = self.lowest_note_on

         # Find the corresponding color for the note
         color = None
         if lowest_note == 0:
            color = self.colors['blue']
         elif lowest_note == 1:
            color = self.colors['orange']
         elif lowest_note == 2:
            color = self.colors['cyan']
         elif lowest_note == 3:
            color = self.colors['yellow']
         elif lowest_note == 4:
            color = self.colors['red']
         elif lowest_note == 5:
            color = self.colors['magenta']
         elif lowest_note == 6:
            color = self.colors['blue']
         elif lowest_note == 7:
            color = self.colors['pink']
         elif lowest_note == 8:
            color = self.colors['red']
         elif lowest_note == 9:
            color = self.colors['green']
         elif lowest_note == 10:
            color = self.colors['orange']
         elif lowest_note == 11:
            color = self.colors['pink']
         else:
            #color = {'red': 50, 'green': 25, 'blue': 25}
            color = self.colors['black']


         self.fade_to_color(color, self.DISPLAY_MANAGER__FLASH_INTERVAL, False, [stop_event, self.display_mode_change_event, self.note_change_event])
         self.fade_from_color_to_color(color, self.colors['black'], self.DISPLAY_MANAGER__FLASH_NOTE_DURATION, False, [stop_event, self.display_mode_change_event, self.note_change_event])
         if self.note_change_event.is_set(): continue
         if stop_event.is_set() or self.display_mode_change_event.is_set(): break

         while not self.note_change_event.is_set():
            time.sleep(self.DISPLAY_MANAGER__MIN_INTERVAL)
      # while(not(stop_event.is_set() or self.display_mode_change_event.is_set())):
   # def flash_lowest_note_color(self, stop_event):


   # }}}
      

   # Thread worker methods
   # {{{ def run(self):
   def run(self):
      threads = {}

      try:
         logging.debug("Identifying MIDI Interfaces...")
         midi_interfaces = self.__identify_midi_interfaces()

         for reader_number, interface in enumerate(midi_interfaces):
            logging.debug("Starting MIDI Reader %d on interface %d..." % (reader_number, interface))
            thread_name = "midi_reader__%d" % (reader_number)



            threads[thread_name] = {}
            threads[thread_name]['stopper'] = threading.Event()
            threads[thread_name]['thread']  = threading.Thread(name=thread_name, target=self.midi_reader, args=(interface, threads[thread_name]['stopper'],))
            threads[thread_name]['thread'].daemon = True
            threads[thread_name]['thread'].start()
         # for reader_number, interface in enumerate(midi_interfaces):


         logging.debug("Starting Display Manager...")
         threads['display_manager'] = {}
         threads['display_manager']['stopper'] = threading.Event()
         threads['display_manager']['thread']  = threading.Thread(name='display_manager', target=self.display_manager, args=(threads['display_manager']['stopper'],))
         threads['display_manager']['thread'].daemon = True
         threads['display_manager']['thread'].start()


         # Wait for child threads
         while True:
            time.sleep(1)

      except RuntimeError as e:
         logging.error("ERROR: %s", e)
      except KeyboardInterrupt:
         logging.debug("Caught Ctrl-C, shutting down")

         for thread_name in threads:
            logging.debug('Asking thread %s to exit', threads[thread_name]['thread'].getName())
            threads[thread_name]['stopper'].set()
            threads[thread_name]['thread'].join()
         # for thread_name in threads:

         ag.cleanup()
         sys.exit(0)
      # except KeyboardInterrupt:
   # def run(self):


   # }}}
   # {{{ def midi_reader(self, interface_index, stop_event):
   def midi_reader(self, interface_index, stop_event):
      self.__midi_interfaces[interface_index] = 0
      self.__open_midi_interface(interface_index)

      if not self.__midi_interfaces[interface_index]:
         raise RuntimeError("MIDI interface is not open")

      while(not stop_event.is_set()):
         if self.__midi_interfaces[interface_index].poll():
            message = self.__midi_interfaces[interface_index].read(1)

            logging.debug("MSG: %s", pprint.pformat(message))

            if message[0][0][0] == MidiMessageType.note:
               key_number   = constrain(message[0][0][1], 0, len(self.keys))
               key_velocity = constrain(message[0][0][2], 0, self.MAX_VELOCITY)
               note_number  = key_number % self.NUM_NOTES
               note_on      = (key_velocity > 0)

               logging.debug("NOTE: %s: %d (%d) - %d", 'ON' if note_on else 'off', key_number, note_number, key_velocity)

               with self.midi_data_lock:
                  # Update this key
                  self.keys[key_number]   = key_velocity
                  self.notes[note_number] = note_on

                  # Calculate various stats
                  self.max_key_velocity = max(self.keys)

                  try:
                     self.lowest_key_on = [i for i, e in enumerate(self.keys) if e != 0][0]
                  except IndexError:
                     self.lowest_key_on = None
                  # except IndexError:

                  old_lowest_note_on    = self.lowest_note_on

                  # If the lowest note changed, set the event
                  self.lowest_note_on   = (self.lowest_key_on % self.NUM_NOTES) if self.lowest_key_on != None else None
                  if self.lowest_note_on != old_lowest_note_on:
                     self.note_change_event.set()
               # with self.midi_data_lock:

            elif message[0][0][0] == MidiMessageType.program_change:
               logging.debug("PC: %d", message[0][0][1])

               if message[0][0][1] in DisplayMode.get_modes():
                  logging.debug("   Setting new display mode")

                  with self.midi_data_lock:
                     self.display_mode = message[0][0][1]
                  # with self.midi_data_lock:

                  self.display_mode_change_event.set()
               # if message[0][0][1] in DisplayMode.get_modes():
            elif message[0][0][0] == MidiMessageType.control_change:
               logging.debug("CC: %d", message[0][0][2])

               if message[0][0][2] in DisplayMode.get_modes():
                  logging.debug("   Setting new display mode")

                  with self.midi_data_lock:
                     self.display_mode = message[0][0][2]
                  # with self.midi_data_lock:

                  self.display_mode_change_event.set()
               # if message[0][0][1] in DisplayMode.get_modes():
            # if
         # if self.__midi_interfaces[interface_index].poll():

         # Slow the polling down to a reasonable rate
         time.sleep(self.MIDI_READER__INTERVAL)
      # while(not stop_event.is_set()):

      logging.debug("Asked to stop, returning...")
      return
   # def midi_reader(self, interface_index, stop_event):


   # }}}
   # {{{ def display_manager(self, stop_event):
   def display_manager(self, stop_event):
      self.__init_display()

      logging.debug("Started Display Manager")

      while(not stop_event.is_set()):
         self.display_mode_change_event.clear()

         logging.debug("Determining current display mode")


         # Enter a display mode and stay there until we're asked to switch modes or exit
         # {{{ if   self.display_mode == DisplayMode.off:
         if   self.display_mode == DisplayMode.off:
            # All LEDS off
            logging.debug("   => Off")
            self.turn_off(stop_event)


         # }}}
         # {{{ elif self.display_mode == DisplayMode.random_glow:
         elif self.display_mode == DisplayMode.random_glow:
            # Cycle through random colors. No MIDI input
            logging.debug("   => Random Glow")
            self.glow_color_cycle(stop_event, False)


         # }}}
         # {{{ elif self.display_mode == DisplayMode.crazy_flash_jump:
         elif self.display_mode == DisplayMode.crazy_flash_jump:
            # Flash random colors, jumping directly to each. No MIDI input
            logging.debug("   => Crazy Flash (Jump)")
            self.crazy_flash(stop_event)


         # }}}
         # {{{ elif self.display_mode == DisplayMode.glow_lowest_midi_key_on:
         elif self.display_mode == DisplayMode.glow_lowest_midi_key_on:
            # Glow a color based on the lowest MIDI key currently on
            logging.debug("   => Glow lowest MIDI key")
            self.glow_lowest_note_color(stop_event)


         # }}}
         # {{{ elif self.display_mode == DisplayMode.flash_lowest_midi_key_on:
         elif self.display_mode == DisplayMode.flash_lowest_midi_key_on:
            # Flash a color based on the lowest MIDI key currently on
            logging.debug("   => Flash lowest MIDI key")
            self.flash_lowest_note_color(stop_event)


         # }}}
         # {{{ elif self.display_mode == DisplayMode.crazy_flash_fade:
         elif self.display_mode == DisplayMode.crazy_flash_fade:
            # Flash random colors, fading between each. No MIDI input
            logging.debug("   => Crazy Flash (Fade)")
            self.crazy_flash(stop_event, True)


         # }}}
         # {{{ elif self.display_mode == DisplayMode.random_glow_midi_velocity:
         elif self.display_mode == DisplayMode.random_glow_midi_velocity:
            # Cycle through random colors, with intensity varying between 50% and 100% based on average MIDI key velocity
            logging.debug("   => Random Glow (MIDI Velocity)")
            self.glow_color_cycle(stop_event, True)


         # }}}
         # {{{ else:
         else:
            logging.debug("Unrecognized display mode (%d) set.", self.display_mode)
            self.display_mode = DisplayMode.off
            continue


         # }}}
      # while(not stop_event.is_set()):


      logging.debug("Asked to stop, returning...")
      return
   # def display_manager(self, stop_event):


   # }}}


   # Private methods
   # {{{ def __identify_midi_interfaces(self):
   def __identify_midi_interfaces(self):
      interfaces = []

      for i in range(0, pygame.midi.get_count()):
         interface = pygame.midi.get_device_info(i)

         # If this isn't an input, we're not interested
         if interface[2] != 1:
            continue

         # If this is one of the system MIDI interfaces, ignore it
         if interface[1] in self.MIDI_INTERFACES_TO_IGNORE:
            continue

         # We found an interface to open!
         interfaces.append(i)

      if not interfaces:
         raise RuntimeError("No MIDI devices found!")

      return interfaces
   # def __identify_midi_interfaces(self):


   # }}}
   # {{{ def __open_midi_interface(self, interface_index):
   def __open_midi_interface(self, interface_index):
      interface = pygame.midi.get_device_info(interface_index)

      if not interface:
         raise RuntimeError("MIDI device %d not found!".format(interface_index))

      # If this isn't an input, we're not interested
      if interface[2] != 1:
         return False

      # If this is one of the system MIDI interfaces, ignore it
      if interface[1] in self.MIDI_INTERFACES_TO_IGNORE:
         return False

      # We found an interface to open!
      logging.debug("Opening MIDI device %d (%s):" % (interface_index, interface[1]))
      self.__midi_interfaces[interface_index] = pygame.midi.Input(interface_index, 100)

      return True
   # def __open_midi_interface(self, interface_index):


   # }}}


   # Class methods
   # {{{ def scale_color_brightness(cls, color, scale = 1.0):
   @classmethod
   def scale_color_brightness(cls, color, scale = 1.0):
      scale = constrain(scale, 0.0, 1.0)

      color['red']   = constrain((color['red']   * scale), 0.0, 100.0)
      color['green'] = constrain((color['green'] * scale), 0.0, 100.0)
      color['blue']  = constrain((color['blue']  * scale), 0.0, 100.0)

      return(color)
   # def scale_color_brightness(cls, color, scale = 1.0):


   # }}}
# class AcrylicGuitar:


# }}}

# {{{ def constrain(n, minn, maxn):
def constrain(n, minn, maxn):
   # Swap min and max if they're inverted
   if minn > maxn:
      temp = maxn
      maxn = minn
      minn = temp

   if n < minn:
      return minn
   elif n > maxn:
      return maxn
   else:
      return n
# def constrain(n, minn, maxn):


# }}}


try:
   ag = AcrylicGuitar()
   ag.run()

except RuntimeError as e:
   logging.error("ERROR: %s", e)
except KeyboardInterrupt:
   pass
# except KeyboardInterrupt:



