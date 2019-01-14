#!/usr/bin/python


import re
import sys
import pygame
import pygame.midi
import pprint


MIDI_INTERFACES_TO_IGNORE = ['Midi Through Port-0', 'Synth input port (2225:0)']


pygame.init()
pygame.midi.init()


midi = 0

try:
   for i in range(0, pygame.midi.get_count()):
      interface = pygame.midi.get_device_info(i)

      # If this isn't an input, we're not interested
      if interface[2] != 1:
         continue

      # If this is one of the system MIDI interfaces, ignore it
      if interface[1] in MIDI_INTERFACES_TO_IGNORE:
         continue

      # We found an interface to open!
      print("Opening MIDI device %d (%s):" % (i, interface[1]))
      midi = pygame.midi.Input(i, 100)
      break
   else:
      raise RuntimeError("MIDI device not found!")


   while 1:
      if midi.poll():
         message = midi.read(1)
         pprint.pprint(message)
except RuntimeError as e:
   print "ERROR: ", e
except KeyboardInterrupt:
   pass


pygame.midi.quit()
sys.exit(0)





