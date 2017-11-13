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

from configobj import ConfigObj
from collections import OrderedDict
from utilities import Observable, DispatchDgt, get_tags, version
from dgt.util import TimeMode, TimeModeLoop, Top, TopLoop, Mode, ModeLoop, Language, LanguageLoop, BeepLevel, BeepLoop
from dgt.util import System, SystemLoop, Display, DisplayLoop, ClockIcons
from dgt.util import Voice, VoiceLoop

from dgt.api import Dgt, Event

from timecontrol import TimeControl
from dgt.translate import DgtTranslate
import chess
import os
import logging


class MenuState(object):

    """Keep the current DgtMenu State."""

    TOP = 100000

    MODE = 200000
    MODE_TYPE = 210000  # normal, observe, ...

    POS = 300000
    POS_COL = 310000
    POS_REV = 311000
    POS_UCI = 311100
    POS_READ = 311110

    TIME = 400000
    TIME_BLITZ = 410000  # blitz, fischer, fixed
    TIME_BLITZ_CTRL = 411000  # time_control objs
    TIME_FISCH = 420000
    TIME_FISCH_CTRL = 421000
    TIME_FIXED = 430000
    TIME_FIXED_CTRL = 431000

    BOOK = 500000
    BOOK_NAME = 510000

    ENG = 600000
    ENG_NAME = 610000
    ENG_NAME_LEVEL = 611000

    SYS = 700000
    SYS_VERS = 710000
    SYS_IP = 720000
    SYS_IP_INT = 721000
    SYS_IP_EXT = 722000
    SYS_SOUND = 730000
    SYS_SOUND_TYPE = 731000  # never, always, some
    SYS_LANG = 740000
    SYS_LANG_NAME = 741000  # de, en, ...
    SYS_LOG = 750000

    SYS_VOICE = 760000
    SYS_VOICE_TYPE = 761000  # user, computer, speed
    SYS_VOICE_USER = 761001  # user (subset from above)
    SYS_VOICE_COMP = 761002  # computer (subset from above)

    SYS_VOICE_TYPE_MUTE = 761100  # on, off
    SYS_VOICE_TYPE_MUTE_LANG = 761110  # de, en, ...
    SYS_VOICE_TYPE_MUTE_LANG_SPEAK = 761111  # al, christina, ...
    SYS_VOICE_SPEED = 761200
    SYS_VOICE_SPEED_FACTOR = 761210  # 0-7

    SYS_DISP = 770000
    SYS_DISP_CNFRM = 771000
    SYS_DISP_CNFRM_YESNO = 771100  # yes,no
    SYS_DISP_PONDER = 772000
    SYS_DISP_PONDER_INTERVAL = 772100  # 1-8

    SYS_BATTERY = 780000


class DgtMenu(object):

    """Handle the Dgt Menu."""

    def __init__(self, disable_confirm: bool, ponder_interval: int, speed_voice: int, dgttranslate: DgtTranslate):
        super(DgtMenu, self).__init__()

        self.current_text = None  # save the current text
        self.menu_system_display_confirm = disable_confirm
        self.menu_system_display_ponderinterval = ponder_interval
        self.dgttranslate = dgttranslate
        self.state = MenuState.TOP

        self.dgt_fen = '8/8/8/8/8/8/8/8'
        self.int_ip = None
        self.ext_ip = None
        self.flip_board = False

        self.menu_position_whitetomove = True
        self.menu_position_reverse = False
        self.menu_position_uci960 = False

        self.menu_top = Top.MODE
        self.menu_mode = Mode.NORMAL

        self.menu_engine_level = None
        self.engine_has_960 = False
        self.engine_restart = False
        self.menu_engine_name = 0
        self.installed_engines = None

        self.menu_book = 0
        self.all_books = None

        self.menu_system = System.VERSION
        self.menu_system_sound_beep = self.dgttranslate.beep

        langs = {'en': Language.EN, 'de': Language.DE, 'nl': Language.NL,
                 'fr': Language.FR, 'es': Language.ES, 'it': Language.IT}
        self.menu_system_language_name = langs[self.dgttranslate.language]

        self.voices_conf = ConfigObj('talker' + os.sep + 'voices' + os.sep + 'voices.ini')
        self.menu_system_voice = Voice.COMP
        self.menu_system_voice_type = Voice.COMP
        self.menu_system_voice_mute = False
        try:
            self.menu_system_voice_lang = self.voices_conf.keys().index(self.dgttranslate.language)
        except ValueError:
            self.menu_system_voice_lang = 0

        self.menu_system_voice_speak = 0
        self.menu_system_voice_factor = speed_voice

        self.menu_system_display = Display.PONDER

        self.menu_time_mode = TimeMode.BLITZ

        self.menu_time_fixed = 0
        self.menu_time_blitz = 2  # Default time control: Blitz, 5min
        self.menu_time_fisch = 0
        self.tc_fixed_list = [' 1', ' 3', ' 5', '10', '15', '30', '60', '90']
        self.tc_blitz_list = [' 1', ' 3', ' 5', '10', '15', '30', '60', '90']
        self.tc_fisch_list = [' 1  1', ' 3  2', ' 4  2', ' 5  3', '10  5', '15 10', '30 15', '60 30']
        self.tc_fixed_map = OrderedDict([
            ('rnbqkbnr/pppppppp/Q7/8/8/8/PPPPPPPP/RNBQKBNR', TimeControl(TimeMode.FIXED, fixed=1)),
            ('rnbqkbnr/pppppppp/1Q6/8/8/8/PPPPPPPP/RNBQKBNR', TimeControl(TimeMode.FIXED, fixed=3)),
            ('rnbqkbnr/pppppppp/2Q5/8/8/8/PPPPPPPP/RNBQKBNR', TimeControl(TimeMode.FIXED, fixed=5)),
            ('rnbqkbnr/pppppppp/3Q4/8/8/8/PPPPPPPP/RNBQKBNR', TimeControl(TimeMode.FIXED, fixed=10)),
            ('rnbqkbnr/pppppppp/4Q3/8/8/8/PPPPPPPP/RNBQKBNR', TimeControl(TimeMode.FIXED, fixed=15)),
            ('rnbqkbnr/pppppppp/5Q2/8/8/8/PPPPPPPP/RNBQKBNR', TimeControl(TimeMode.FIXED, fixed=30)),
            ('rnbqkbnr/pppppppp/6Q1/8/8/8/PPPPPPPP/RNBQKBNR', TimeControl(TimeMode.FIXED, fixed=60)),
            ('rnbqkbnr/pppppppp/7Q/8/8/8/PPPPPPPP/RNBQKBNR', TimeControl(TimeMode.FIXED, fixed=90))])
        self.tc_blitz_map = OrderedDict([
            ('rnbqkbnr/pppppppp/8/8/Q7/8/PPPPPPPP/RNBQKBNR', TimeControl(TimeMode.BLITZ, blitz=1)),
            ('rnbqkbnr/pppppppp/8/8/1Q6/8/PPPPPPPP/RNBQKBNR', TimeControl(TimeMode.BLITZ, blitz=3)),
            ('rnbqkbnr/pppppppp/8/8/2Q5/8/PPPPPPPP/RNBQKBNR', TimeControl(TimeMode.BLITZ, blitz=5)),
            ('rnbqkbnr/pppppppp/8/8/3Q4/8/PPPPPPPP/RNBQKBNR', TimeControl(TimeMode.BLITZ, blitz=10)),
            ('rnbqkbnr/pppppppp/8/8/4Q3/8/PPPPPPPP/RNBQKBNR', TimeControl(TimeMode.BLITZ, blitz=15)),
            ('rnbqkbnr/pppppppp/8/8/5Q2/8/PPPPPPPP/RNBQKBNR', TimeControl(TimeMode.BLITZ, blitz=30)),
            ('rnbqkbnr/pppppppp/8/8/6Q1/8/PPPPPPPP/RNBQKBNR', TimeControl(TimeMode.BLITZ, blitz=60)),
            ('rnbqkbnr/pppppppp/8/8/7Q/8/PPPPPPPP/RNBQKBNR', TimeControl(TimeMode.BLITZ, blitz=90))])
        self.tc_fisch_map = OrderedDict([
            ('rnbqkbnr/pppppppp/8/8/8/Q7/PPPPPPPP/RNBQKBNR', TimeControl(TimeMode.FISCHER, blitz=1, fischer=1)),
            ('rnbqkbnr/pppppppp/8/8/8/1Q6/PPPPPPPP/RNBQKBNR', TimeControl(TimeMode.FISCHER, blitz=3, fischer=2)),
            ('rnbqkbnr/pppppppp/8/8/8/2Q5/PPPPPPPP/RNBQKBNR', TimeControl(TimeMode.FISCHER, blitz=4, fischer=2)),
            ('rnbqkbnr/pppppppp/8/8/8/3Q4/PPPPPPPP/RNBQKBNR', TimeControl(TimeMode.FISCHER, blitz=5, fischer=3)),
            ('rnbqkbnr/pppppppp/8/8/8/4Q3/PPPPPPPP/RNBQKBNR', TimeControl(TimeMode.FISCHER, blitz=10, fischer=5)),
            ('rnbqkbnr/pppppppp/8/8/8/5Q2/PPPPPPPP/RNBQKBNR', TimeControl(TimeMode.FISCHER, blitz=15, fischer=10)),
            ('rnbqkbnr/pppppppp/8/8/8/6Q1/PPPPPPPP/RNBQKBNR', TimeControl(TimeMode.FISCHER, blitz=30, fischer=15)),
            ('rnbqkbnr/pppppppp/8/8/8/7Q/PPPPPPPP/RNBQKBNR', TimeControl(TimeMode.FISCHER, blitz=60, fischer=30))])
        # setup the result vars for api (dgtdisplay)
        self.save_choices()
        # During "picochess" is displayed, some special actions allowed
        self.picochess_displayed = set()
        self.updt_top = False  # inside the update-menu?
        self.updt_devs = set()  # list of devices which are inside the update-menu
        self.updt_tags = []
        self.updt_version = 0  # index to current version

        self.battery = '-NA'  # standard value: NotAvailable (discharging)

    def inside_updt_menu(self):
        return self.updt_top

    def disable_picochess_displayed(self, dev):
        self.picochess_displayed.discard(dev)

    def enable_picochess_displayed(self, dev):
        self.picochess_displayed.add(dev)
        self.updt_tags = get_tags()
        try:
            self.updt_version = [item[1] for item in self.updt_tags].index(version)
        except ValueError:
            self.updt_version = len(self.updt_tags) - 1

    def inside_picochess_time(self, dev):
        return dev in self.picochess_displayed

    def save_choices(self):
        """Save the user choices to the result vars."""
        self.state = MenuState.TOP

        self.res_mode = self.menu_mode

        self.res_position_whitetomove = self.menu_position_whitetomove
        self.res_position_reverse = self.menu_position_reverse
        self.res_position_uci960 = self.menu_position_uci960

        self.res_time_mode = self.menu_time_mode
        self.res_time_fixed = self.menu_time_fixed
        self.res_time_blitz = self.menu_time_blitz
        self.res_time_fisch = self.menu_time_fisch

        self.res_book_name = self.menu_book

        self.res_engine_name = self.menu_engine_name
        self.res_engine_level = self.menu_engine_level

        self.res_system_display_confirm = self.menu_system_display_confirm
        self.res_system_display_ponderinterval = self.menu_system_display_ponderinterval
        return False

    def set_engine_restart(self, flag: bool):
        """Set the flag."""
        self.engine_restart = flag

    def get_engine_restart(self):
        """Get the flag."""
        return self.engine_restart

    def get_flip_board(self):
        """Get the flag."""
        return self.flip_board

    def get_engine_has_960(self):
        """Get the flag."""
        return self.engine_has_960

    def set_engine_has_960(self, flag: bool):
        """Set the flag."""
        self.engine_has_960 = flag

    def get_dgt_fen(self):
        """Get the flag."""
        return self.dgt_fen

    def set_dgt_fen(self, fen: str):
        """Set the flag."""
        self.dgt_fen = fen

    def get_mode(self):
        """Get the flag."""
        return self.res_mode

    def set_mode(self, mode: Mode):
        """Set the flag."""
        self.res_mode = self.menu_mode = mode

    def get_engine(self):
        """Get the flag."""
        return self.installed_engines[self.res_engine_name]

    def set_engine_index(self, index: int):
        """Set the flag."""
        self.res_engine_name = self.menu_engine_name = index

    def get_engine_level(self):
        """Get the flag."""
        return self.res_engine_level

    def set_engine_level(self, level: int):
        """Set the flag."""
        self.res_engine_level = self.menu_engine_level = level

    def get_confirm(self):
        """Get the flag."""
        return self.res_system_display_confirm

    def set_book(self, index: int):
        """Set the flag."""
        self.res_book_name = self.menu_book = index

    def set_time_mode(self, mode: TimeMode):
        """Set the flag."""
        self.res_time_mode = self.menu_time_mode = mode

    def set_time_fixed(self, index: int):
        """Set the flag."""
        self.res_time_fixed = self.menu_time_fixed = index

    def get_time_fixed(self):
        """Get the flag."""
        return self.res_time_fixed

    def set_time_blitz(self, index: int):
        """Set the flag."""
        self.res_time_blitz = self.menu_time_blitz = index

    def get_time_blitz(self):
        """Get the flag."""
        return self.res_time_blitz

    def set_time_fisch(self, index: int):
        """Set the flag."""
        self.res_time_fisch = self.menu_time_fisch = index

    def get_time_fisch(self):
        """Get the flag."""
        return self.res_time_fisch

    def set_position_reverse_to_flipboard(self):
        """Set the flag."""
        self.flip_board = not self.flip_board  # Flip the board
        self.res_position_reverse = self.flip_board

    def get_ponderinterval(self):
        """Get the flag."""
        return self.res_system_display_ponderinterval

    def get(self):
        """Get the current state."""
        return self.state

    def enter_top_menu(self):
        """Set the menu state."""
        self.state = MenuState.TOP
        self.current_text = None
        return False

    def enter_mode_menu(self):
        """Set the menu state."""
        self.state = MenuState.MODE
        text = self.dgttranslate.text(Top.MODE.value)
        return text

    def enter_mode_type_menu(self):
        """Set the menu state."""
        self.state = MenuState.MODE_TYPE
        text = self.dgttranslate.text(self.menu_mode.value)
        return text

    def enter_pos_menu(self):
        """Set the menu state."""
        self.state = MenuState.POS
        text = self.dgttranslate.text(Top.POSITION.value)
        return text

    def enter_pos_color_menu(self):
        """Set the menu state."""
        self.state = MenuState.POS_COL
        text = self.dgttranslate.text('B00_sidewhite' if self.menu_position_whitetomove else 'B00_sideblack')
        return text

    def enter_pos_rev_menu(self):
        """Set the menu state."""
        self.state = MenuState.POS_REV
        text = self.dgttranslate.text('B00_bw' if self.menu_position_reverse else 'B00_wb')
        return text

    def enter_pos_uci_menu(self):
        """Set the menu state."""
        self.state = MenuState.POS_UCI
        text = self.dgttranslate.text('B00_960yes' if self.menu_position_uci960 else 'B00_960no')
        return text

    def enter_pos_read_menu(self):
        """Set the menu state."""
        self.state = MenuState.POS_READ
        text = self.dgttranslate.text('B00_scanboard')
        return text

    def enter_time_menu(self):
        """Set the menu state."""
        self.state = MenuState.TIME
        text = self.dgttranslate.text(Top.TIME.value)
        return text

    def enter_time_blitz_menu(self):
        """Set the menu state."""
        self.state = MenuState.TIME_BLITZ
        text = self.dgttranslate.text(self.menu_time_mode.value)
        return text

    def enter_time_blitz_ctrl_menu(self):
        """Set the menu state."""
        self.state = MenuState.TIME_BLITZ_CTRL
        text = self.dgttranslate.text('B00_tc_blitz', self.tc_blitz_list[self.menu_time_blitz])
        return text

    def enter_time_fisch_menu(self):
        """Set the menu state."""
        self.state = MenuState.TIME_FISCH
        text = self.dgttranslate.text(self.menu_time_mode.value)
        return text

    def enter_time_fisch_ctrl_menu(self):
        """Set the menu state."""
        self.state = MenuState.TIME_FISCH_CTRL
        text = self.dgttranslate.text('B00_tc_fisch', self.tc_fisch_list[self.menu_time_fisch])
        return text

    def enter_time_fixed_menu(self):
        """Set the menu state."""
        self.state = MenuState.TIME_FIXED
        text = self.dgttranslate.text(self.menu_time_mode.value)
        return text

    def enter_time_fixed_ctrl_menu(self):
        """Set the menu state."""
        self.state = MenuState.TIME_FIXED_CTRL
        text = self.dgttranslate.text('B00_tc_fixed', self.tc_fixed_list[self.menu_time_fixed])
        return text

    def enter_book_menu(self):
        """Set the menu state."""
        self.state = MenuState.BOOK
        text = self.dgttranslate.text(Top.BOOK.value)
        return text

    def enter_book_name_menu(self):
        """Set the menu state."""
        self.state = MenuState.BOOK_NAME
        text = self.all_books[self.menu_book]['text']
        text.beep = self.dgttranslate.bl(BeepLevel.BUTTON)
        return text

    def enter_eng_menu(self):
        """Set the menu state."""
        self.state = MenuState.ENG
        text = self.dgttranslate.text(Top.ENGINE.value)
        return text

    def enter_eng_name_menu(self):
        """Set the menu state."""
        self.state = MenuState.ENG_NAME
        text = self.installed_engines[self.menu_engine_name]['text']
        text.beep = self.dgttranslate.bl(BeepLevel.BUTTON)
        return text

    def enter_eng_name_level_menu(self):
        """Set the menu state."""
        self.state = MenuState.ENG_NAME_LEVEL
        eng = self.installed_engines[self.menu_engine_name]
        level_dict = eng['level_dict']
        if level_dict:
            if self.menu_engine_level is None or len(level_dict) <= self.menu_engine_level:
                self.menu_engine_level = len(level_dict) - 1
            msg = sorted(level_dict)[self.menu_engine_level]
            text = self.dgttranslate.text('B00_level', msg)
        else:
            text = self.save_choices()
        return text

    def enter_sys_menu(self):
        """Set the menu state."""
        self.state = MenuState.SYS
        text = self.dgttranslate.text(Top.SYSTEM.value)
        return text

    def enter_sys_vers_menu(self):
        """Set the menu state."""
        self.state = MenuState.SYS_VERS
        text = self.dgttranslate.text(self.menu_system.value)
        return text

    def enter_sys_ip_menu(self):
        """Set the menu state."""
        self.state = MenuState.SYS_IP
        text = self.dgttranslate.text(self.menu_system.value)
        return text

    def enter_sys_sound_menu(self):
        """Set the menu state."""
        self.state = MenuState.SYS_SOUND
        text = self.dgttranslate.text(self.menu_system.value)
        return text

    def enter_sys_sound_type_menu(self):
        """Set the menu state."""
        self.state = MenuState.SYS_SOUND_TYPE
        text = self.dgttranslate.text(self.menu_system_sound_beep.value)
        return text

    def enter_sys_lang_menu(self):
        """Set the menu state."""
        self.state = MenuState.SYS_LANG
        text = self.dgttranslate.text(self.menu_system.value)
        return text

    def enter_sys_lang_name_menu(self):
        """Set the menu state."""
        self.state = MenuState.SYS_LANG_NAME
        text = self.dgttranslate.text(self.menu_system_language_name.value)
        return text

    def enter_sys_log_menu(self):
        """Set the menu state."""
        self.state = MenuState.SYS_LOG
        text = self.dgttranslate.text(self.menu_system.value)
        return text

    def enter_sys_voice_menu(self):
        """Set the menu state."""
        self.state = MenuState.SYS_VOICE
        text = self.dgttranslate.text(self.menu_system.value)
        return text

    def enter_sys_voice_type_menu(self):
        """Set the menu state."""
        if self.menu_system_voice_type == Voice.USER:
            return self.enter_sys_voice_user_menu()
        else:
            return self.enter_sys_voice_comp_menu()

    def enter_sys_voice_user_menu(self):
        """Set the menu state."""
        self.state = MenuState.SYS_VOICE_USER
        text = self.dgttranslate.text(Voice.USER.value)
        return text

    def enter_sys_voice_comp_menu(self):
        """Set the menu state."""
        self.state = MenuState.SYS_VOICE_COMP
        text = self.dgttranslate.text(Voice.COMP.value)
        return text

    def enter_sys_voice_type_mute_menu(self):
        """Set the menu state."""
        self.state = MenuState.SYS_VOICE_TYPE_MUTE
        msg = 'on' if self.menu_system_voice_mute else 'off'
        text = self.dgttranslate.text('B00_voice_' + msg)
        return text

    def enter_sys_voice_type_mute_lang_menu(self):
        """Set the menu state."""
        self.state = MenuState.SYS_VOICE_TYPE_MUTE_LANG
        vkey = self.voices_conf.keys()[self.menu_system_voice_lang]
        text = self.dgttranslate.text('B00_language_' + vkey + '_menu')
        return text

    def enter_sys_voice_type_mute_lang_speak_menu(self):
        """Set the menu state."""
        self.state = MenuState.SYS_VOICE_TYPE_MUTE_LANG_SPEAK
        vkey = self.voices_conf.keys()[self.menu_system_voice_lang]
        speakers = self.voices_conf[vkey]
        speaker = speakers[list(speakers)[self.menu_system_voice_speak]]
        text = Dgt.DISPLAY_TEXT(l=speaker['large'], m=speaker['medium'], s=speaker['small'])
        text.beep = self.dgttranslate.bl(BeepLevel.BUTTON)
        text.wait = False
        text.maxtime = 0
        text.devs = {'ser', 'i2c', 'web'}
        return text

    def enter_sys_voice_speed_menu(self):
        """Set the menu state."""
        self.state = MenuState.SYS_VOICE_SPEED
        text = self.dgttranslate.text(Voice.SPEED.value)
        return text

    def enter_sys_voice_speed_factor_menu(self):
        """Set the menu state."""
        self.state = MenuState.SYS_VOICE_SPEED_FACTOR
        text = self.dgttranslate.text('B00_voice_speed', str(self.menu_system_voice_factor))
        return text

    def enter_sys_disp_menu(self):
        """Set the menu state."""
        self.state = MenuState.SYS_DISP
        text = self.dgttranslate.text(self.menu_system.value)
        return text

    def enter_sys_disp_cnfrm_menu(self):
        """Set the menu state."""
        self.state = MenuState.SYS_DISP_CNFRM
        text = self.dgttranslate.text(Display.CONFIRM.value)
        return text

    def enter_sys_disp_cnfrm_yesno_menu(self):
        """Set the menu state."""
        self.state = MenuState.SYS_DISP_CNFRM_YESNO
        msg = 'off' if self.menu_system_display_confirm else 'on'
        text = self.dgttranslate.text('B00_confirm_' + msg)
        return text

    def enter_sys_disp_ponder_menu(self):
        """Set the menu state."""
        self.state = MenuState.SYS_DISP_PONDER
        text = self.dgttranslate.text(Display.PONDER.value)
        return text

    def enter_sys_disp_ponder_interval_menu(self):
        """Set the menu state."""
        self.state = MenuState.SYS_DISP_PONDER_INTERVAL
        text = self.dgttranslate.text('B00_ponder_interval', str(self.menu_system_display_ponderinterval))
        return text

    def enter_sys_battery_menu(self):
        """Set the menu state."""
        self.state = MenuState.SYS_BATTERY
        text = self.dgttranslate.text(self.menu_system.value)
        return text

    def main_up(self):
        """Change the menu state after UP action."""
        text = self.dgttranslate.text('Y00_errormenu')
        if False:  # switch-case
            pass
        elif self.state == MenuState.TOP:
            pass
        elif self.state == MenuState.MODE:
            text = self.enter_top_menu()

        elif self.state == MenuState.MODE_TYPE:
            text = self.enter_mode_menu()

        elif self.state == MenuState.POS:
            text = self.enter_top_menu()

        elif self.state == MenuState.POS_COL:
            text = self.enter_pos_menu()

        elif self.state == MenuState.POS_REV:
            text = self.enter_pos_color_menu()

        elif self.state == MenuState.POS_UCI:
            text = self.enter_pos_rev_menu()

        elif self.state == MenuState.POS_READ:
            text = self.enter_pos_uci_menu()

        elif self.state == MenuState.TIME:
            text = self.enter_top_menu()

        elif self.state == MenuState.TIME_BLITZ:
            text = self.enter_time_menu()

        elif self.state == MenuState.TIME_BLITZ_CTRL:
            text = self.enter_time_blitz_menu()

        elif self.state ==MenuState.TIME_FISCH:
            text = self.enter_time_menu()

        elif self.state == MenuState.TIME_FISCH_CTRL:
            text = self.enter_time_fisch_menu()

        elif self.state == MenuState.TIME_FIXED:
            text = self.enter_time_menu()

        elif self.state == MenuState.TIME_FIXED_CTRL:
            text = self.enter_time_fixed_menu()

        elif self.state == MenuState.BOOK:
            text = self.enter_top_menu()

        elif self.state == MenuState.BOOK_NAME:
            text = self.enter_book_menu()

        elif self.state == MenuState.ENG:
            text = self.enter_top_menu()

        elif self.state == MenuState.ENG_NAME:
            text = self.enter_eng_menu()

        elif self.state == MenuState.ENG_NAME_LEVEL:
            text = self.enter_eng_name_menu()

        elif self.state == MenuState.SYS:
            text = self.enter_top_menu()

        elif self.state == MenuState.SYS_VERS:
            text = self.enter_sys_menu()

        elif self.state == MenuState.SYS_IP:
            text = self.enter_sys_menu()

        elif self.state == MenuState.SYS_SOUND:
            text = self.enter_sys_menu()

        elif self.state == MenuState.SYS_SOUND_TYPE:
            text = self.enter_sys_sound_menu()

        elif self.state == MenuState.SYS_LANG:
            text = self.enter_sys_menu()

        elif self.state == MenuState.SYS_LANG_NAME:
            text = self.enter_sys_lang_menu()

        elif self.state == MenuState.SYS_LOG:
            text = self.enter_sys_menu()

        elif self.state == MenuState.SYS_VOICE:
            text = self.enter_sys_menu()

        elif self.state == MenuState.SYS_VOICE_USER:
            text = self.enter_sys_voice_menu()

        elif self.state == MenuState.SYS_VOICE_COMP:
            text = self.enter_sys_voice_menu()

        elif self.state == MenuState.SYS_VOICE_TYPE_MUTE:
            text = self.enter_sys_voice_type_menu()

        elif self.state == MenuState.SYS_VOICE_TYPE_MUTE_LANG:
            text = self.enter_sys_voice_type_mute_menu()

        elif self.state == MenuState.SYS_VOICE_TYPE_MUTE_LANG_SPEAK:
            text = self.enter_sys_voice_type_mute_lang_menu()

        elif self.state == MenuState.SYS_VOICE_SPEED:
            text = self.enter_sys_voice_menu()

        elif self.state == MenuState.SYS_VOICE_SPEED_FACTOR:
            text = self.enter_sys_voice_speed_menu()

        elif self.state == MenuState.SYS_DISP:
            text = self.enter_sys_menu()

        elif self.state == MenuState.SYS_DISP_CNFRM:
            text = self.enter_sys_disp_menu()

        elif self.state == MenuState.SYS_DISP_CNFRM_YESNO:
            text = self.enter_sys_disp_cnfrm_menu()

        elif self.state == MenuState.SYS_DISP_PONDER:
            text = self.enter_sys_disp_menu()

        elif self.state == MenuState.SYS_DISP_PONDER_INTERVAL:
            text = self.enter_sys_disp_ponder_menu()

        elif self.state == MenuState.SYS_BATTERY:
            text = self.enter_sys_menu()

        else:  # Default
            pass
        self.current_text = text
        return text

    def main_down(self):
        """Change the menu state after DOWN action."""
        text = self.dgttranslate.text('Y00_errormenu')
        if False:  # switch-case
            pass
        elif self.state == MenuState.TOP:
            if self.menu_top == Top.MODE:
                text = self.enter_mode_menu()
            if self.menu_top == Top.POSITION:
                text = self.enter_pos_menu()
            if self.menu_top == Top.TIME:
                text = self.enter_time_menu()
            if self.menu_top == Top.BOOK:
                text = self.enter_book_menu()
            if self.menu_top == Top.ENGINE:
                text = self.enter_eng_menu()
            if self.menu_top == Top.SYSTEM:
                text = self.enter_sys_menu()

        elif self.state == MenuState.MODE:
            text = self.enter_mode_type_menu()

        elif self.state == MenuState.MODE_TYPE:
            # do action!
            text = self.dgttranslate.text('B10_okmode')
            event = Event.SET_INTERACTION_MODE(mode=self.menu_mode, mode_text=text, show_ok=True)
            Observable.fire(event)
            text = self.save_choices()

        elif self.state == MenuState.POS:
            text = self.enter_pos_color_menu()

        elif self.state == MenuState.POS_COL:
            text = self.enter_pos_rev_menu()

        elif self.state == MenuState.POS_REV:
            text = self.enter_pos_uci_menu()

        elif self.state == MenuState.POS_UCI:
            text = self.enter_pos_read_menu()

        elif self.state == MenuState.POS_READ:
            # do action!
            to_move = 'w' if self.menu_position_whitetomove else 'b'
            fen = self.dgt_fen
            if self.flip_board != self.menu_position_reverse:
                logging.debug('flipping the board')
                fen = fen[::-1]
            fen += " {0} KQkq - 0 1".format(to_move)
            bit_board = chess.Board(fen, self.menu_position_uci960)
            # ask python-chess to correct the castling string
            bit_board.set_fen(bit_board.fen())
            if bit_board.is_valid():
                self.flip_board = self.menu_position_reverse
                event = Event.SETUP_POSITION(fen=bit_board.fen(), uci960=self.menu_position_uci960)
                Observable.fire(event)
                # self._reset_moves_and_score() done in "START_NEW_GAME"
                text = self.save_choices()
            else:
                DispatchDgt.fire(self.dgttranslate.text('Y05_illegalpos'))
                text = self.dgttranslate.text('B00_scanboard')

        elif self.state == MenuState.TIME:
            if self.menu_time_mode == TimeMode.BLITZ:
                text = self.enter_time_blitz_menu()
            if self.menu_time_mode == TimeMode.FISCHER:
                text = self.enter_time_fisch_menu()
            if self.menu_time_mode == TimeMode.FIXED:
                text = self.enter_time_fixed_menu()

        elif self.state == MenuState.TIME_BLITZ:
            text = self.enter_time_blitz_ctrl_menu()

        elif self.state == MenuState.TIME_BLITZ_CTRL:
            # do action!
            time_text = self.dgttranslate.text('B10_oktime')
            timectrl = self.tc_blitz_map[list(self.tc_blitz_map)[self.menu_time_blitz]]  # type: TimeControl
            event = Event.SET_TIME_CONTROL(tc_init=timectrl.get_parameters(), time_text=time_text, show_ok=True)
            Observable.fire(event)
            text = self.save_choices()

        elif self.state == MenuState.TIME_FISCH:
            text = self.enter_time_fisch_ctrl_menu()

        elif self.state == MenuState.TIME_FISCH_CTRL:
            # do action!
            time_text = self.dgttranslate.text('B10_oktime')
            timectrl = self.tc_fisch_map[list(self.tc_fisch_map)[self.menu_time_fisch]]  # type: TimeControl
            event = Event.SET_TIME_CONTROL(tc_init=timectrl.get_parameters(), time_text=time_text, show_ok=True)
            Observable.fire(event)
            text = self.save_choices()

        elif self.state == MenuState.TIME_FIXED:
            text = self.enter_time_fixed_ctrl_menu()

        elif self.state == MenuState.TIME_FIXED_CTRL:
            # do action!
            time_text = self.dgttranslate.text('B10_oktime')
            timectrl = self.tc_fixed_map[list(self.tc_fixed_map)[self.menu_time_fixed]]  # type: TimeControl
            event = Event.SET_TIME_CONTROL(tc_init=timectrl.get_parameters(), time_text=time_text, show_ok=True)
            Observable.fire(event)
            text = self.save_choices()

        elif self.state == MenuState.BOOK:
            text = self.enter_book_name_menu()

        elif self.state == MenuState.BOOK_NAME:
            # do action!
            book_text = self.dgttranslate.text('B10_okbook')
            event = Event.SET_OPENING_BOOK(book=self.all_books[self.menu_book], book_text=book_text, show_ok=True)
            Observable.fire(event)
            text = self.save_choices()

        elif self.state == MenuState.ENG:
            text = self.enter_eng_name_menu()

        elif self.state == MenuState.ENG_NAME:
            # maybe do action!
            text = self.enter_eng_name_level_menu()
            if not text:
                config = ConfigObj('picochess.ini')
                config['engine-level'] = None
                config.write()
                eng = self.installed_engines[self.menu_engine_name]
                eng_text = self.dgttranslate.text('B10_okengine')
                event = Event.NEW_ENGINE(eng=eng, eng_text=eng_text, options={}, show_ok=True)
                Observable.fire(event)
                self.engine_restart = True

        elif self.state == MenuState.ENG_NAME_LEVEL:
            # do action!
            eng = self.installed_engines[self.menu_engine_name]
            level_dict = eng['level_dict']
            if level_dict:
                msg = sorted(level_dict)[self.menu_engine_level]
                options = level_dict[msg]
                config = ConfigObj('picochess.ini')
                config['engine-level'] = msg
                config.write()
                event = Event.LEVEL(options={}, level_text=self.dgttranslate.text('B10_level', msg))
                Observable.fire(event)
            else:
                options = {}
            eng_text = self.dgttranslate.text('B10_okengine')
            event = Event.NEW_ENGINE(eng=eng, eng_text=eng_text, options=options, show_ok=True)
            Observable.fire(event)
            self.engine_restart = True
            text = self.save_choices()

        elif self.state == MenuState.SYS:
            if self.menu_system == System.VERSION:
                text = self.enter_sys_vers_menu()
            if self.menu_system == System.IPADR:
                text = self.enter_sys_ip_menu()
            if self.menu_system == System.SOUND:
                text = self.enter_sys_sound_menu()
            if self.menu_system == System.LANGUAGE:
                text = self.enter_sys_lang_menu()
            if self.menu_system == System.LOGFILE:
                text = self.enter_sys_log_menu()
            if self.menu_system == System.VOICE:
                text = self.enter_sys_voice_menu()
            if self.menu_system == System.DISPLAY:
                text = self.enter_sys_disp_menu()
            if self.menu_system == System.BATTERY:
                text = self.enter_sys_battery_menu()

        elif self.state == MenuState.SYS_VERS:
            # do action!
            text = self.dgttranslate.text('B10_picochess')
            text.rd = ClockIcons.DOT
            text.wait = False
            DispatchDgt.fire(text)
            text = self.save_choices()

        elif self.state == MenuState.SYS_IP:
            # do action!
            if self.int_ip:
                msg = ' '.join(self.int_ip.split('.')[:2])
                text = self.dgttranslate.text('B07_default', msg)
                if len(msg) == 7:  # delete the " " for XL incase its "123 456"
                    text.s = msg[:3] + msg[4:]
                DispatchDgt.fire(text)
                msg = ' '.join(self.int_ip.split('.')[2:])
                text = self.dgttranslate.text('N07_default', msg)
                if len(msg) == 7:  # delete the " " for XL incase its "123 456"
                    text.s = msg[:3] + msg[4:]
                text.wait = True
            else:
                text = self.dgttranslate.text('B10_noipadr')
            DispatchDgt.fire(text)
            text = self.save_choices()

        elif self.state == MenuState.SYS_SOUND:
            text = self.enter_sys_sound_type_menu()

        elif self.state == MenuState.SYS_SOUND_TYPE:
            # do action!
            self.dgttranslate.set_beep(self.menu_system_sound_beep)
            config = ConfigObj('picochess.ini')
            config['beep-config'] = self.dgttranslate.beep_to_config(self.menu_system_sound_beep)
            config.write()
            text = self.dgttranslate.text('B10_okbeep')
            DispatchDgt.fire(text)
            text = self.save_choices()

        elif self.state == MenuState.SYS_LANG:
            text = self.enter_sys_lang_name_menu()

        elif self.state == MenuState.SYS_LANG_NAME:
            # do action!
            langs = {Language.EN: 'en', Language.DE: 'de', Language.NL: 'nl',
                     Language.FR: 'fr', Language.ES: 'es', Language.IT: 'it'}
            language = langs[self.menu_system_language_name]
            self.dgttranslate.set_language(language)
            config = ConfigObj('picochess.ini')
            config['language'] = language
            config.write()
            text = self.dgttranslate.text('B10_oklang')
            DispatchDgt.fire(text)
            text = self.save_choices()

        elif self.state == MenuState.SYS_LOG:
            # do action!
            Observable.fire(Event.EMAIL_LOG())
            text = self.dgttranslate.text('B10_oklogfile')  # @todo give pos/neg feedback
            DispatchDgt.fire(text)
            text = self.save_choices()

        elif self.state == MenuState.SYS_VOICE:
            if self.menu_system_voice == Voice.USER:
                text = self.enter_sys_voice_user_menu()
            if self.menu_system_voice == Voice.COMP:
                text = self.enter_sys_voice_comp_menu()
            if self.menu_system_voice == Voice.SPEED:
                text = self.enter_sys_voice_speed_menu()

        elif self.state == MenuState.SYS_VOICE_USER:
            self.menu_system_voice_type = Voice.USER
            text = self.enter_sys_voice_type_mute_menu()

        elif self.state == MenuState.SYS_VOICE_COMP:
            self.menu_system_voice_type = Voice.COMP
            text = self.enter_sys_voice_type_mute_menu()

        elif self.state == MenuState.SYS_VOICE_TYPE_MUTE:
            # maybe do action!
            if self.menu_system_voice_mute:
                text = self.enter_sys_voice_type_mute_lang_menu()
            else:
                config = ConfigObj('picochess.ini')
                ckey = 'user' if self.menu_system_voice_type == Voice.USER else 'computer'
                if ckey + '-voice' in config:
                    del config[ckey + '-voice']
                    config.write()
                event = Event.SET_VOICE(type=self.menu_system_voice_type, lang='en', speaker='mute', speed=2)
                Observable.fire(event)
                text = self.dgttranslate.text('B10_okvoice')
                DispatchDgt.fire(text)
                text = self.save_choices()

        elif self.state == MenuState.SYS_VOICE_TYPE_MUTE_LANG:
            text = self.enter_sys_voice_type_mute_lang_speak_menu()

        elif self.state == MenuState.SYS_VOICE_TYPE_MUTE_LANG_SPEAK:
            # do action!
            vkey = self.voices_conf.keys()[self.menu_system_voice_lang]
            speakers = self.voices_conf[vkey].keys()
            config = ConfigObj('picochess.ini')
            ckey = 'user' if self.menu_system_voice_type == Voice.USER else 'computer'
            skey = speakers[self.menu_system_voice_speak]
            config[ckey + '-voice'] = vkey + ':' + skey
            config.write()
            event = Event.SET_VOICE(type=self.menu_system_voice_type, lang=vkey, speaker=skey,
                                    speed=self.menu_system_voice_factor)
            Observable.fire(event)
            text = self.dgttranslate.text('B10_okvoice')
            DispatchDgt.fire(text)
            text = self.save_choices()

        elif self.state == MenuState.SYS_VOICE_SPEED:
            self.menu_system_voice_type = Voice.SPEED
            text = self.enter_sys_voice_speed_factor_menu()

        elif self.state == MenuState.SYS_VOICE_SPEED_FACTOR:
            # do action!
            vkey = self.voices_conf.keys()[self.menu_system_voice_lang]
            speakers = self.voices_conf[vkey].keys()
            config = ConfigObj('picochess.ini')
            skey = speakers[self.menu_system_voice_speak]
            config['speed-voice'] = self.menu_system_voice_factor
            config.write()
            event = Event.SET_VOICE(type=self.menu_system_voice_type, lang=vkey, speaker=skey,
                                    speed=self.menu_system_voice_factor)
            Observable.fire(event)
            text = self.dgttranslate.text('B10_okspeed')
            DispatchDgt.fire(text)
            text = self.save_choices()

        elif self.state == MenuState.SYS_DISP:
            if self.menu_system_display == Display.PONDER:
                text = self.enter_sys_disp_ponder_menu()
            if self.menu_system_display == Display.CONFIRM:
                text = self.enter_sys_disp_cnfrm_menu()

        elif self.state == MenuState.SYS_DISP_CNFRM:
            text = self.enter_sys_disp_cnfrm_yesno_menu()

        elif self.state == MenuState.SYS_DISP_CNFRM_YESNO:
            # do action!
            config = ConfigObj('picochess.ini')
            if self.menu_system_display_confirm:
                config['disable-confirm-message'] = self.menu_system_display_confirm
            elif 'disable-confirm-message' in config:
                del config['disable-confirm-message']
            config.write()
            text = self.dgttranslate.text('B10_okconfirm')
            DispatchDgt.fire(text)
            text = self.save_choices()

        elif self.state == MenuState.SYS_DISP_PONDER:
            text = self.enter_sys_disp_ponder_interval_menu()

        elif self.state == MenuState.SYS_DISP_PONDER_INTERVAL:
            # do action!
            config = ConfigObj('picochess.ini')
            config['ponder-interval'] = self.menu_system_display_ponderinterval
            config.write()
            text = self.dgttranslate.text('B10_okponder')
            DispatchDgt.fire(text)
            text = self.save_choices()

        elif self.state == MenuState.SYS_BATTERY:
            # do action!
            text = self.dgttranslate.text('B10_bat_percent', self.battery)
            DispatchDgt.fire(text)
            text = self.save_choices()

        else:  # Default
            pass
        self.current_text = text
        return text

    def main_left(self):
        """Change the menu state after LEFT action."""
        text = self.dgttranslate.text('Y00_errormenu')
        if False:  # switch-case
            pass
        elif self.state == MenuState.TOP:
            pass

        elif self.state == MenuState.MODE:
            self.state = MenuState.SYS
            self.menu_top = TopLoop.prev(self.menu_top)
            text = self.dgttranslate.text(self.menu_top.value)

        elif self.state == MenuState.MODE_TYPE:
            self.menu_mode = ModeLoop.prev(self.menu_mode)
            text = self.dgttranslate.text(self.menu_mode.value)

        elif self.state == MenuState.POS:
            self.state = MenuState.MODE
            self.menu_top = TopLoop.prev(self.menu_top)
            text = self.dgttranslate.text(self.menu_top.value)

        elif self.state == MenuState.POS_COL:
            self.menu_position_whitetomove = not self.menu_position_whitetomove
            text = self.dgttranslate.text('B00_sidewhite' if self.menu_position_whitetomove else 'B00_sideblack')

        elif self.state == MenuState.POS_REV:
            self.menu_position_reverse = not self.menu_position_reverse
            text = self.dgttranslate.text('B00_bw' if self.menu_position_reverse else 'B00_wb')

        elif self.state == MenuState.POS_UCI:
            if self.engine_has_960:
                self.menu_position_uci960 = not self.menu_position_uci960
                text = self.dgttranslate.text('B00_960yes' if self.menu_position_uci960 else 'B00_960no')
            else:
                text = self.dgttranslate.text('Y00_error960')

        elif self.state == MenuState.POS_READ:
            pass

        elif self.state == MenuState.TIME:
            self.state = MenuState.POS
            self.menu_top = TopLoop.prev(self.menu_top)
            text = self.dgttranslate.text(self.menu_top.value)

        elif self.state == MenuState.TIME_BLITZ:
            self.state = MenuState.TIME_FIXED
            self.menu_time_mode = TimeModeLoop.prev(self.menu_time_mode)
            text = self.dgttranslate.text(self.menu_time_mode.value)

        elif self.state == MenuState.TIME_BLITZ_CTRL:
            self.menu_time_blitz = (self.menu_time_blitz - 1) % len(self.tc_blitz_map)
            text = self.dgttranslate.text('B00_tc_blitz', self.tc_blitz_list[self.menu_time_blitz])

        elif self.state == MenuState.TIME_FISCH:
            self.state = MenuState.TIME_BLITZ
            self.menu_time_mode = TimeModeLoop.prev(self.menu_time_mode)
            text = self.dgttranslate.text(self.menu_time_mode.value)

        elif self.state == MenuState.TIME_FISCH_CTRL:
            self.menu_time_fisch = (self.menu_time_fisch - 1) % len(self.tc_fisch_map)
            text = self.dgttranslate.text('B00_tc_fisch', self.tc_fisch_list[self.menu_time_fisch])

        elif self.state == MenuState.TIME_FIXED:
            self.state = MenuState.TIME_FISCH
            self.menu_time_mode = TimeModeLoop.prev(self.menu_time_mode)
            text = self.dgttranslate.text(self.menu_time_mode.value)

        elif self.state == MenuState.TIME_FIXED_CTRL:
            self.menu_time_fixed = (self.menu_time_fixed - 1) % len(self.tc_fixed_map)
            text = self.dgttranslate.text('B00_tc_fixed', self.tc_fixed_list[self.menu_time_fixed])

        elif self.state == MenuState.BOOK:
            self.state = MenuState.TIME
            self.menu_top = TopLoop.prev(self.menu_top)
            text = self.dgttranslate.text(self.menu_top.value)

        elif self.state == MenuState.BOOK_NAME:
            self.menu_book = (self.menu_book - 1) % len(self.all_books)
            text = self.all_books[self.menu_book]['text']
            text.beep = self.dgttranslate.bl(BeepLevel.BUTTON)

        elif self.state == MenuState.ENG:
            self.state = MenuState.BOOK
            self.menu_top = TopLoop.prev(self.menu_top)
            text = self.dgttranslate.text(self.menu_top.value)

        elif self.state == MenuState.ENG_NAME:
            self.menu_engine_name = (self.menu_engine_name - 1) % len(self.installed_engines)
            text = self.installed_engines[self.menu_engine_name]['text']
            text.beep = self.dgttranslate.bl(BeepLevel.BUTTON)

        elif self.state == MenuState.ENG_NAME_LEVEL:
            level_dict = self.installed_engines[self.menu_engine_name]['level_dict']
            self.menu_engine_level = (self.menu_engine_level - 1) % len(level_dict)
            msg = sorted(level_dict)[self.menu_engine_level]
            text = self.dgttranslate.text('B00_level', msg)

        elif self.state == MenuState.SYS:
            self.state = MenuState.ENG
            self.menu_top = TopLoop.prev(self.menu_top)
            text = self.dgttranslate.text(self.menu_top.value)

        elif self.state == MenuState.SYS_VERS:
            self.state = MenuState.SYS_BATTERY
            self.menu_system = SystemLoop.prev(self.menu_system)
            text = self.dgttranslate.text(self.menu_system.value)

        elif self.state == MenuState.SYS_IP:
            self.state = MenuState.SYS_VERS
            self.menu_system = SystemLoop.prev(self.menu_system)
            text = self.dgttranslate.text(self.menu_system.value)

        elif self.state == MenuState.SYS_SOUND:
            self.state = MenuState.SYS_IP
            self.menu_system = SystemLoop.prev(self.menu_system)
            text = self.dgttranslate.text(self.menu_system.value)

        elif self.state == MenuState.SYS_SOUND_TYPE:
            self.menu_system_sound_beep = BeepLoop.prev(self.menu_system_sound_beep)
            text = self.dgttranslate.text(self.menu_system_sound_beep.value)

        elif self.state == MenuState.SYS_LANG:
            self.state = MenuState.SYS_SOUND
            self.menu_system = SystemLoop.prev(self.menu_system)
            text = self.dgttranslate.text(self.menu_system.value)

        elif self.state == MenuState.SYS_LANG_NAME:
            self.menu_system_language_name = LanguageLoop.prev(self.menu_system_language_name)
            text = self.dgttranslate.text(self.menu_system_language_name.value)

        elif self.state == MenuState.SYS_LOG:
            self.state = MenuState.SYS_LANG
            self.menu_system = SystemLoop.prev(self.menu_system)
            text = self.dgttranslate.text(self.menu_system.value)

        elif self.state == MenuState.SYS_VOICE:
            self.state = MenuState.SYS_LOG
            self.menu_system = SystemLoop.prev(self.menu_system)
            text = self.dgttranslate.text(self.menu_system.value)

        elif self.state == MenuState.SYS_VOICE_USER:
            self.state = MenuState.SYS_VOICE_COMP
            self.menu_system_voice = VoiceLoop.prev(self.menu_system_voice)
            text = self.dgttranslate.text(self.menu_system_voice.value)

        elif self.state == MenuState.SYS_VOICE_COMP:
            self.state = MenuState.SYS_VOICE_SPEED
            self.menu_system_voice = VoiceLoop.prev(self.menu_system_voice)
            text = self.dgttranslate.text(self.menu_system_voice.value)

        elif self.state == MenuState.SYS_VOICE_TYPE_MUTE:
            self.menu_system_voice_mute = not self.menu_system_voice_mute
            msg = 'on' if self.menu_system_voice_mute else 'off'
            text = self.dgttranslate.text('B00_voice_' + msg)

        elif self.state == MenuState.SYS_VOICE_TYPE_MUTE_LANG:
            self.menu_system_voice_lang = (self.menu_system_voice_lang - 1) % len(self.voices_conf)
            vkey = self.voices_conf.keys()[self.menu_system_voice_lang]
            text = self.dgttranslate.text('B00_language_' + vkey + '_menu')  # voice using same as language

        elif self.state == MenuState.SYS_VOICE_TYPE_MUTE_LANG_SPEAK:
            vkey = self.voices_conf.keys()[self.menu_system_voice_lang]
            speakers = self.voices_conf[vkey]
            self.menu_system_voice_speak = (self.menu_system_voice_speak - 1) % len(speakers)
            speaker = speakers[list(speakers)[self.menu_system_voice_speak]]
            text = Dgt.DISPLAY_TEXT(l=speaker['large'], m=speaker['medium'], s=speaker['small'])
            text.beep = self.dgttranslate.bl(BeepLevel.BUTTON)
            text.wait = False
            text.maxtime = 0
            text.devs = {'ser', 'i2c', 'web'}

        elif self.state == MenuState.SYS_VOICE_SPEED:
            self.state = MenuState.SYS_VOICE_USER
            self.menu_system_voice = VoiceLoop.prev(self.menu_system_voice)
            text = self.dgttranslate.text(self.menu_system_voice.value)

        elif self.state == MenuState.SYS_VOICE_SPEED_FACTOR:
            self.menu_system_voice_factor = (self.menu_system_voice_factor - 1) % 10
            text = self.dgttranslate.text('B00_voice_speed', str(self.menu_system_voice_factor))

        elif self.state == MenuState.SYS_DISP:
            self.state = MenuState.SYS_VOICE
            self.menu_system = SystemLoop.prev(self.menu_system)
            text = self.dgttranslate.text(self.menu_system.value)

        elif self.state == MenuState.SYS_DISP_CNFRM:
            self.state = MenuState.SYS_DISP_PONDER
            self.menu_system_display = DisplayLoop.prev(self.menu_system_display)
            text = self.dgttranslate.text(self.menu_system_display.value)

        elif self.state == MenuState.SYS_DISP_CNFRM_YESNO:
            self.menu_system_display_confirm = not self.menu_system_display_confirm
            msg = 'off' if self.menu_system_display_confirm else 'on'
            text = self.dgttranslate.text('B00_confirm_' + msg)

        elif self.state == MenuState.SYS_DISP_PONDER:
            self.state = MenuState.SYS_DISP_CNFRM
            self.menu_system_display = DisplayLoop.prev(self.menu_system_display)
            text = self.dgttranslate.text(self.menu_system_display.value)

        elif self.state == MenuState.SYS_DISP_PONDER_INTERVAL:
            self.menu_system_display_ponderinterval -= 1
            if self.menu_system_display_ponderinterval < 1:
                self.menu_system_display_ponderinterval = 8
            text = self.dgttranslate.text('B00_ponder_interval', str(self.menu_system_display_ponderinterval))

        elif self.state == MenuState.SYS_BATTERY:
            self.state = MenuState.SYS_DISP
            self.menu_system = SystemLoop.prev(self.menu_system)
            text = self.dgttranslate.text(self.menu_system.value)

        else:  # Default
            pass
        self.current_text = text
        return text

    def main_right(self):
        """Change the menu state after RIGHT action."""
        text = self.dgttranslate.text('Y00_errormenu')
        if False:  # switch-case
            pass
        elif self.state == MenuState.TOP:
            pass

        elif self.state == MenuState.MODE:
            self.state = MenuState.POS
            self.menu_top = TopLoop.next(self.menu_top)
            text = self.dgttranslate.text(self.menu_top.value)

        elif self.state == MenuState.MODE_TYPE:
            self.menu_mode = ModeLoop.next(self.menu_mode)
            text = self.dgttranslate.text(self.menu_mode.value)

        elif self.state == MenuState.POS:
            self.state = MenuState.TIME
            self.menu_top = TopLoop.next(self.menu_top)
            text = self.dgttranslate.text(self.menu_top.value)

        elif self.state == MenuState.POS_COL:
            self.menu_position_whitetomove = not self.menu_position_whitetomove
            text = self.dgttranslate.text('B00_sidewhite' if self.menu_position_whitetomove else 'B00_sideblack')

        elif self.state == MenuState.POS_REV:
            self.menu_position_reverse = not self.menu_position_reverse
            text = self.dgttranslate.text('B00_bw' if self.menu_position_reverse else 'B00_wb')

        elif self.state == MenuState.POS_UCI:
            if self.engine_has_960:
                self.menu_position_uci960 = not self.menu_position_uci960
                text = self.dgttranslate.text('B00_960yes' if self.menu_position_uci960 else 'B00_960no')
            else:
                text = self.dgttranslate.text('Y00_error960')

        elif self.state == MenuState.POS_READ:
            pass

        elif self.state == MenuState.TIME:
            self.state = MenuState.BOOK
            self.menu_top = TopLoop.next(self.menu_top)
            text = self.dgttranslate.text(self.menu_top.value)

        elif self.state == MenuState.TIME_BLITZ:
            self.state = MenuState.TIME_FISCH
            self.menu_time_mode = TimeModeLoop.next(self.menu_time_mode)
            text = self.dgttranslate.text(self.menu_time_mode.value)

        elif self.state == MenuState.TIME_BLITZ_CTRL:
            self.menu_time_blitz = (self.menu_time_blitz + 1) % len(self.tc_blitz_map)
            text = self.dgttranslate.text('B00_tc_blitz', self.tc_blitz_list[self.menu_time_blitz])

        elif self.state == MenuState.TIME_FISCH:
            self.state = MenuState.TIME_FIXED
            self.menu_time_mode = TimeModeLoop.next(self.menu_time_mode)
            text = self.dgttranslate.text(self.menu_time_mode.value)

        elif self.state == MenuState.TIME_FISCH_CTRL:
            self.menu_time_fisch = (self.menu_time_fisch + 1) % len(self.tc_fisch_map)
            text = self.dgttranslate.text('B00_tc_fisch', self.tc_fisch_list[self.menu_time_fisch])

        elif self.state == MenuState.TIME_FIXED:
            self.state = MenuState.TIME_BLITZ
            self.menu_time_mode = TimeModeLoop.next(self.menu_time_mode)
            text = self.dgttranslate.text(self.menu_time_mode.value)

        elif self.state == MenuState.TIME_FIXED_CTRL:
            self.menu_time_fixed = (self.menu_time_fixed + 1) % len(self.tc_fixed_map)
            text = self.dgttranslate.text('B00_tc_fixed', self.tc_fixed_list[self.menu_time_fixed])

        elif self.state == MenuState.BOOK:
            self.state = MenuState.ENG
            self.menu_top = TopLoop.next(self.menu_top)
            text = self.dgttranslate.text(self.menu_top.value)

        elif self.state == MenuState.BOOK_NAME:
            self.menu_book = (self.menu_book + 1) % len(self.all_books)
            text = self.all_books[self.menu_book]['text']
            text.beep = self.dgttranslate.bl(BeepLevel.BUTTON)

        elif self.state == MenuState.ENG:
            self.state = MenuState.SYS
            self.menu_top = TopLoop.next(self.menu_top)
            text = self.dgttranslate.text(self.menu_top.value)

        elif self.state == MenuState.ENG_NAME:
            self.menu_engine_name = (self.menu_engine_name + 1) % len(self.installed_engines)
            text = self.installed_engines[self.menu_engine_name]['text']
            text.beep = self.dgttranslate.bl(BeepLevel.BUTTON)

        elif self.state == MenuState.ENG_NAME_LEVEL:
            level_dict = self.installed_engines[self.menu_engine_name]['level_dict']
            self.menu_engine_level = (self.menu_engine_level + 1) % len(level_dict)
            msg = sorted(level_dict)[self.menu_engine_level]
            text = self.dgttranslate.text('B00_level', msg)

        elif self.state == MenuState.SYS:
            self.state = MenuState.MODE
            self.menu_top = TopLoop.next(self.menu_top)
            text = self.dgttranslate.text(self.menu_top.value)

        elif self.state == MenuState.SYS_VERS:
            self.state = MenuState.SYS_IP
            self.menu_system = SystemLoop.next(self.menu_system)
            text = self.dgttranslate.text(self.menu_system.value)

        elif self.state == MenuState.SYS_IP:
            self.state = MenuState.SYS_SOUND
            self.menu_system = SystemLoop.next(self.menu_system)
            text = self.dgttranslate.text(self.menu_system.value)

        elif self.state == MenuState.SYS_SOUND:
            self.state = MenuState.SYS_LANG
            self.menu_system = SystemLoop.next(self.menu_system)
            text = self.dgttranslate.text(self.menu_system.value)

        elif self.state == MenuState.SYS_SOUND_TYPE:
            self.menu_system_sound_beep = BeepLoop.next(self.menu_system_sound_beep)
            text = self.dgttranslate.text(self.menu_system_sound_beep.value)

        elif self.state == MenuState.SYS_LANG:
            self.state = MenuState.SYS_LOG
            self.menu_system = SystemLoop.next(self.menu_system)
            text = self.dgttranslate.text(self.menu_system.value)

        elif self.state == MenuState.SYS_LANG_NAME:
            self.menu_system_language_name = LanguageLoop.next(self.menu_system_language_name)
            text = self.dgttranslate.text(self.menu_system_language_name.value)

        elif self.state == MenuState.SYS_LOG:
            self.state = MenuState.SYS_VOICE
            self.menu_system = SystemLoop.next(self.menu_system)
            text = self.dgttranslate.text(self.menu_system.value)

        elif self.state == MenuState.SYS_VOICE:
            self.state = MenuState.SYS_DISP
            self.menu_system = SystemLoop.next(self.menu_system)
            text = self.dgttranslate.text(self.menu_system.value)

        elif self.state == MenuState.SYS_VOICE_USER:
            self.state = MenuState.SYS_VOICE_SPEED
            self.menu_system_voice = VoiceLoop.next(self.menu_system_voice)
            text = self.dgttranslate.text(self.menu_system_voice.value)

        elif self.state == MenuState.SYS_VOICE_COMP:
            self.state = MenuState.SYS_VOICE_USER
            self.menu_system_voice = VoiceLoop.next(self.menu_system_voice)
            text = self.dgttranslate.text(self.menu_system_voice.value)

        elif self.state == MenuState.SYS_VOICE_TYPE_MUTE:
            self.menu_system_voice_mute = not self.menu_system_voice_mute
            msg = 'on' if self.menu_system_voice_mute else 'off'
            text = self.dgttranslate.text('B00_voice_' + msg)

        elif self.state == MenuState.SYS_VOICE_TYPE_MUTE_LANG:
            self.menu_system_voice_lang = (self.menu_system_voice_lang + 1) % len(self.voices_conf)
            vkey = self.voices_conf.keys()[self.menu_system_voice_lang]
            text = self.dgttranslate.text('B00_language_' + vkey + '_menu')  # voice using same as language

        elif self.state == MenuState.SYS_VOICE_TYPE_MUTE_LANG_SPEAK:
            vkey = self.voices_conf.keys()[self.menu_system_voice_lang]
            speakers = self.voices_conf[vkey]
            self.menu_system_voice_speak = (self.menu_system_voice_speak + 1) % len(speakers)
            speaker = speakers[list(speakers)[self.menu_system_voice_speak]]
            text = Dgt.DISPLAY_TEXT(l=speaker['large'], m=speaker['medium'], s=speaker['small'])
            text.beep = self.dgttranslate.bl(BeepLevel.BUTTON)
            text.wait = False
            text.maxtime = 0
            text.devs = {'ser', 'i2c', 'web'}

        elif self.state == MenuState.SYS_VOICE_SPEED:
            self.state = MenuState.SYS_VOICE_COMP
            self.menu_system_voice = VoiceLoop.next(self.menu_system_voice)
            text = self.dgttranslate.text(self.menu_system_voice.value)

        elif self.state == MenuState.SYS_VOICE_SPEED_FACTOR:
            self.menu_system_voice_factor = (self.menu_system_voice_factor + 1) % 10
            text = self.dgttranslate.text('B00_voice_speed', str(self.menu_system_voice_factor))

        elif self.state == MenuState.SYS_DISP:
            self.state = MenuState.SYS_BATTERY
            self.menu_system = SystemLoop.next(self.menu_system)
            text = self.dgttranslate.text(self.menu_system.value)

        elif self.state == MenuState.SYS_DISP_CNFRM:
            self.state = MenuState.SYS_DISP_PONDER
            self.menu_system_display = DisplayLoop.next(self.menu_system_display)
            text = self.dgttranslate.text(self.menu_system_display.value)

        elif self.state == MenuState.SYS_DISP_CNFRM_YESNO:
            self.menu_system_display_confirm = not self.menu_system_display_confirm
            msg = 'off' if self.menu_system_display_confirm else 'on'
            text = self.dgttranslate.text('B00_confirm_' + msg)

        elif self.state == MenuState.SYS_DISP_PONDER:
            self.state = MenuState.SYS_DISP_CNFRM
            self.menu_system_display = DisplayLoop.next(self.menu_system_display)
            text = self.dgttranslate.text(self.menu_system_display.value)

        elif self.state == MenuState.SYS_DISP_PONDER_INTERVAL:
            self.menu_system_display_ponderinterval += 1
            if self.menu_system_display_ponderinterval > 8:
                self.menu_system_display_ponderinterval = 1
            text = self.dgttranslate.text('B00_ponder_interval', str(self.menu_system_display_ponderinterval))

        elif self.state == MenuState.SYS_BATTERY:
            self.state = MenuState.SYS_VERS
            self.menu_system = SystemLoop.next(self.menu_system)
            text = self.dgttranslate.text(self.menu_system.value)

        else:  # Default
            pass
        self.current_text = text
        return text

    def main_middle(self, dev):
        """Change the menu state after MIDDLE action."""
        def _exit_position():
            self.state = MenuState.POS_READ
            return self.main_down()

        if self.inside_picochess_time(dev):
            text = self.updt_middle(dev)
        else:
            text = self.dgttranslate.text('B00_nofunction')
            if False:  # switch-case
                pass
            elif self.state == MenuState.POS:
                text = _exit_position()

            elif self.state == MenuState.POS_COL:
                text = _exit_position()

            elif self.state == MenuState.POS_REV:
                text = _exit_position()

            elif self.state == MenuState.POS_UCI:
                text = _exit_position()

            elif self.state == MenuState.POS_READ:
                text = _exit_position()

            else:  # Default
                pass
        self.current_text = text
        return text

    def updt_middle(self, dev):
        self.updt_devs.add(dev)
        text = self.dgttranslate.text('B00_updt_version', self.updt_tags[self.updt_version][1], devs=self.updt_devs)
        text.rd = ClockIcons.DOT
        logging.debug('enter update menu dev: %s', dev)
        self.updt_top = True
        return text

    def updt_right(self):
        self.updt_version = (self.updt_version + 1) % len(self.updt_tags)
        text = self.dgttranslate.text('B00_updt_version', self.updt_tags[self.updt_version][1], devs=self.updt_devs)
        text.rd = ClockIcons.DOT
        return text

    def updt_left(self):
        self.updt_version = (self.updt_version - 1) % len(self.updt_tags)
        text = self.dgttranslate.text('B00_updt_version', self.updt_tags[self.updt_version][1], devs=self.updt_devs)
        text.rd = ClockIcons.DOT
        return text

    def updt_down(self, dev):
        logging.debug('leave update menu dev: %s', dev)
        self.updt_top = False
        self.updt_devs.discard(dev)
        self.enter_top_menu()
        return self.updt_tags[self.updt_version][0]

    def updt_up(self, dev):
        logging.debug('leave update menu dev: %s', dev)
        self.updt_top = False
        self.updt_devs.discard(dev)
        text = self.enter_top_menu()
        return text

    def inside_main_menu(self):
        """Check if currently inside the menu."""
        return self.state != MenuState.TOP

    def get_current_text(self):
        """Return the current text."""
        return self.current_text
