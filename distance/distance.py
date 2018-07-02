# -*- coding: utf-8 -*-

"""Main module."""

import logging
import asyncio

log = logging.getLogger(__name__)


class Distance():
    def __init__(self, loop, db, little_end):
        self.loop = loop or asyncio.get_event_loop()
        self.db = db
        if little_end not in ('A', 'B', 'a', 'b'):
            little_end = 'A'
            log.warning('Little_end is not A or B. By default A!')
        self.default_little_end = little_end.upper()

        self.ref_info = {}

    def set_publish(self, publish):
        if callable(publish):
            self.publish = publish
        else:
            self.publish = None

    def start(self):
        self._auto_loop()

    def _auto_loop(self):
        self.preset()
        self.loop.call_later(60, self._auto_loop)

    async def got_command(self, mesg):
        try:
            log.info('Distance received: {}'.format(mesg))
            return await self._do_action(mesg)
        except Exception as e:
            log.error('Distance do_action() exception: {}'.format(e))

    def get_info(self):
        return {"references": self.ref_info}

    async def _do_action(self, mesg):
        _type = mesg.get('type', '').upper()
        if not _type:
            return
        _name = mesg.get('name', '')
        _remark = mesg.get('remark', '')
        _offset = mesg.get('offset', 0)

        alarm_names = _name.split("_")
        sys_id = alarm_names[1]
        pm_id = alarm_names[2]

        description = ''

        if _type == 'COMM FAIL':
            _key = sys_id + '_' + pm_id
            (_pm_position, _little_end) = self.ref_info.get(_key, ('', ''))
            if not _pm_position:
                description = '{}设备通讯失败'.format(_name)
            else:
                description = '围界标定{}米{}设备通讯失败'.format(_pm_position, _name)
        elif _type == 'ENCLOSURE TAMPER':
            _key = sys_id + '_' + pm_id
            (_pm_position, _little_end) = self.ref_info.get(_key, ('', ''))
            if not _pm_position:
                description = '{}防拆开关打开'.format(_name)
            else:
                description = '围界标定{}米{}防拆开关打开'.format(_pm_position, _name)
        elif _type == 'CABLE FAULT':
            _key = sys_id + '_' + pm_id
            (_pm_position, _little_end) = self.ref_info.get(_key, ('', ''))
            if not _pm_position:
                description = '{}电缆故障'.format(_name)
            else:
                description = '围界标定{}米PM{}端电缆故障'.format(_pm_position, _name[3:])
        elif _type == 'CABLE ALARM':
            pm_id = _remark[2]
            _key = sys_id + '_' + pm_id
            (_pm_position, _little_end) = self.ref_info.get(_key, ('', ''))
            if not _pm_position:
                description = '{}电缆报警'.format(_name)
            else:
                _cable = _remark[3].upper()
                _position = self.do_computation(_pm_position, _little_end,
                                                _cable, _offset)
                description ='围界标定{}米报警'.format(_position)
        else:
            pass
        if description:
            mesg['description'] = description
        self.send(mesg)

    async def find(self, collection, conditions=None):
        result = []
        try:
            result = await self.db.do_find(collection, conditions)
        except Exception as e:
            log.error('Connect to database has Error: {}'.format(e))
        return result

    async def get_reference(self):
        ref_list = await self.find('references')
        for _ref in ref_list:
            _ref_name = _ref.get('name', '')
            _params = _ref_name.split('_')
            if _params[0] !=  'REF':
                continue
            if len(_params) < 4:
                continue
            sys_id = _params[1]
            pm_id = _params[2]
            pm_position = _params[3]
            if not sys_id.isdigit() or not pm_id.isdigit() or not pm_position.isdigit():
                log.warning('Check the reference naming format: {}'.format(_ref_name))
                continue
            little_end = self.default_little_end
            if len(_params) > 4 and _params[4].upper() in ('A', 'B'):
                little_end = _params[4].upper()
            sys_pm = sys_id + '_' + pm_id
            self.ref_info[sys_pm] = (pm_position, little_end)

    def preset(self):
        asyncio.ensure_future(self.get_reference())

    def do_computation(self, pm_position, little_end, cable, subcell):
        position = int(pm_position)
        if little_end == 'A':                            # little_end表示某PM距离起点最近的一端电缆
            if cable == 'A':
                position -= int(subcell) * 1.1
            else:
                position += int(subcell) * 1.1
        else:
            if cable == 'A':
                position += int(subcell) * 1.1
            else:
                position -= int(subcell) * 1.1
        return round(position)

    def send(self, rep_msg):
        if callable(self.publish):
            self.publish(rep_msg)
