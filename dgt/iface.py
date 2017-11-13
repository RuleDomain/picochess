# Copyright (C) 2013-2017 Jean-Francois Romang (jromang@posteo.de)
#                         Shivkumar Shivaji ()
#                         Jürgen Précour (LocutusOfPenguin@posteo.de)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

from chess import Board
from utilities import hours_minutes_seconds, DisplayDgt, DispatchDgt
import logging
import queue
from dgt.util import ClockIcons, ClockSide
from dgt.api import Dgt
from threading import Thread
from dgt.translate import DgtTranslate
from dgt.board import DgtBoard


class DgtIface(DisplayDgt, Thread):

    """an Interface class for DgtHw, DgtPi, DgtVr."""

    def __init__(self, dgttranslate: DgtTranslate, dgtboard: DgtBoard):
        super(DgtIface, self).__init__()

        self.dgtboard = dgtboard
        self.dgttranslate = dgttranslate

        self.clock_running = False
        self.enable_dgt_3000 = False
        self.time_left = None
        self.time_right = None
        self.case_res = True

    def display_text_on_clock(self, message):
        """override this function."""
        raise NotImplementedError()

    def display_move_on_clock(self, message):
        """override this function."""
        raise NotImplementedError()

    def display_time_on_clock(self, message):
        """override this function."""
        raise NotImplementedError()

    def light_squares_on_revelation(self, squares):
        """override this function."""
        raise NotImplementedError()

    def clear_light_on_revelation(self):
        """override this function."""
        raise NotImplementedError()

    def stop_clock(self, devs):
        """override this function."""
        raise NotImplementedError()

    def _resume_clock(self, side):
        """override this function."""
        raise NotImplementedError()

    def start_clock(self, time_left, time_right, side, devs):
        """override this function."""
        raise NotImplementedError()

    def getName(self):
        """override this function."""
        raise NotImplementedError()

    def get_san(self, message, is_xl=False):
        """create a chess.board plus a text ready to display on clock."""
        bit_board = Board(message.fen)
        if bit_board.is_legal(message.move):
            move_text = bit_board.san(message.move)
        else:
            logging.warning('[%s] illegal move %s found - fen: %s', self.getName(), message.move, message.fen)
            move_text = 'er{}' if is_xl else 'err {}'
            move_text = move_text.format(message.move.uci()[:4])

        if message.side == ClockSide.RIGHT:
            move_text = move_text.rjust(6 if is_xl else 8)
        text = self.dgttranslate.move(move_text)
        return bit_board, text

    def _process_message(self, message):
        if self.getName() not in message.devs:
            return True

        logging.debug('(%s) handle DgtApi: %s started', ','.join(message.devs), message)
        self.case_res = True

        if False:  # switch-case
            pass
        elif isinstance(message, Dgt.DISPLAY_MOVE):
            self.case_res = self.display_move_on_clock(message)
        elif isinstance(message, Dgt.DISPLAY_TEXT):
            self.case_res = self.display_text_on_clock(message)
        elif isinstance(message, Dgt.DISPLAY_TIME):
            self.case_res = self.display_time_on_clock(message)
        elif isinstance(message, Dgt.LIGHT_CLEAR):
            self.case_res = self.clear_light_on_revelation()
        elif isinstance(message, Dgt.LIGHT_SQUARES):
            self.case_res = self.light_squares_on_revelation(message.uci_move)
        elif isinstance(message, Dgt.CLOCK_STOP):
            logging.debug('(%s) clock sending stop time to clock l:%s r:%s',
                          ','.join(message.devs), self.time_left, self.time_right)
            if self.clock_running:
                self.case_res = self.stop_clock(message.devs)
            else:
                logging.debug('(%s) clock is already stopped', ','.join(message.devs))
        elif isinstance(message, Dgt.CLOCK_START):
            # log times
            l_hms = hours_minutes_seconds(message.time_left)
            r_hms = hours_minutes_seconds(message.time_right)
            logging.debug('(%s) clock received last time from clock l:%s r:%s',
                          ','.join(message.devs), self.time_left, self.time_right)
            logging.debug('(%s) clock sending start time to clock l:%s r:%s', ','.join(message.devs), l_hms, r_hms)
            self.case_res = self.start_clock(message.time_left, message.time_right, message.side, message.devs)
        elif isinstance(message, Dgt.CLOCK_VERSION):
            text = self.dgttranslate.text('Y21_picochess', devs=message.devs)
            text.rd = ClockIcons.DOT
            DispatchDgt.fire(text)
            DispatchDgt.fire(Dgt.DISPLAY_TIME(force=True, wait=True, devs=message.devs))
            if 'i2c' in message.devs:
                logging.debug('(i2c) clock found => starting the board connection')
                self.dgtboard.run()  # finally start the serial board connection - see picochess.py
            else:
                if message.main == 2:
                    self.enable_dgt_3000 = True
        elif isinstance(message, Dgt.CLOCK_TIME):
            logging.debug('(%s) clock received current time from clock l:%s r:%s',
                          ','.join(message.devs), message.time_left, message.time_right)
            self.time_left = message.time_left
            self.time_right = message.time_right
        else:  # switch-default
            pass
        logging.debug('(%s) handle DgtApi: %s ended', ','.join(message.devs), message)
        return self.case_res

    def _create_task(self, msg):
        res = self._process_message(msg)
        if not res:
            logging.warning('DgtApi command %s failed result: %s', msg, res)

    def run(self):
        """called from threading.Thread by its start() function."""
        logging.info('[%s] dgt_queue ready', self.getName())
        while True:
            # Check if we have something to display
            try:
                message = self.dgt_queue.get()
                self._create_task(message)
            except queue.Empty:
                pass
