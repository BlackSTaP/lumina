"""Emergency directives, persistence, and independent schedule updates."""
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, Mock
from zoneinfo import ZoneInfo

import scraper
from scraper import parse_emergency, merge_emergency

INTRO = """‼️УВАГА!
По Запорізькій області запроваджено графіки аварійних відключень (ГАВ) та спеціальні графіки аварійних відключень (СГАВ). У зв'язку із цим за частиною адрес можливі вимкнення електропостачання поза доведеним ГПВ.
Причина запровадження додаткових обмежень - пошкодження електрообладнання внаслідок атак окупаційних військ рф на енергетичну інфраструктуру."""
CANCEL = "За вказівкою НЕК «Укренерго» спеціальні графіки аварійних відключень (СГАВ) та графіки аварійних відключень (ГАВ) по Запорізькій області скасовані у повному обсязі. Продовжують діяти графіки погодинних відключень (ГПВ)."

class EmergencyTests(unittest.TestCase):
    t = datetime(2026,11,17,12,tzinfo=ZoneInfo('Europe/Kyiv'))

    def parse(self,text,offset=0):
        return parse_emergency(text,self.t+timedelta(minutes=offset),'https://t.me/zoe_alarm/123',123)

    def test_exact_user_messages(self):
        for text,active in [(INTRO,True),(CANCEL,False)]:
            event=self.parse(text)
            self.assertEqual(set(event),{'gav','sgav'})
            self.assertTrue(all(x['active']==active for x in event.values()))

    def test_variations(self):
        for text in ['Введено ГАВ та СГАВ!', 'Застосовуються графіки аварійних вимкнень.',
                     'У Запоріжжі діють екстрені відключення електроенергії.',
                     'ГАВ введені.', 'Введены аварийные отключения.', 'Графіки аварійних відключень\nзапроваджені.']:
            with self.subTest(text=text):
                self.assertTrue(merge_emergency(None,[self.parse(text)])['active'])
        for text in ['ГАВ та СГАВ більше не застосовуються.', 'Скасовано аварійні відключення.',
                     'ГАВ і СГАВ відмінено.', 'ГАВ отменены.']:
            with self.subTest(text=text):
                self.assertTrue(self.parse(text))
                self.assertFalse(any(x['active'] for x in self.parse(text).values()))

    def test_no_false_switches(self):
        for text in ['ГПВ на сьогодні: Черга 1.1: 09:00-13:00', 'Можливе запровадження ГАВ.',
                     'Якщо введено ГАВ, графіки не діють.', 'ГАВ не скасовані.',
                     'ГАВ не запроваджено.', 'ГПВ не діють через ГАВ.', 'До введення ГАВ діють ГПВ.', 'Завтра будуть введені ГАВ.',
                     'Що таке графіки аварійних відключень?', 'ГАВ частково скасовані.',
                     'Скасовано ГАВ для частини споживачів.']:
            with self.subTest(text=text): self.assertEqual(self.parse(text),{})

    def test_partial_and_mixed_cancellation(self):
        state=merge_emergency(None,[self.parse(INTRO)])
        state=merge_emergency(state,[self.parse('СГАВ скасовані. ГАВ продовжують діяти.',1)])
        self.assertTrue(state['active'])
        self.assertFalse(state['regimes']['sgav']['active'])
        self.assertTrue(state['regimes']['gav']['active'])
        state=merge_emergency(state,[self.parse('ГАВ скасовані.',2)])
        self.assertFalse(state['active'])

    def test_chronology_restart_and_edited_post(self):
        state=merge_emergency(None,[self.parse(CANCEL,5),self.parse(INTRO)])
        self.assertFalse(state['active'])
        self.assertEqual(merge_emergency(state,[]),state)
        self.assertFalse(merge_emergency(state,[self.parse(INTRO)])['active'])
        self.assertTrue(merge_emergency(state,[self.parse(INTRO,5)])['active'])

    def test_channel_reads_status_posts_without_schedule(self):
        from html import escape
        def wrap(text, post, minute):
            return '<div class="tgme_widget_message_wrap"><div class="tgme_widget_message" data-post="zoe_alarm/'+str(post)+'"><a class="tgme_widget_message_date"><time datetime="2026-11-17T12:'+minute+':00+02:00"></time></a><div class="tgme_widget_message_text">'+escape(text).replace('\n','<br>')+'</div></div></div>'
        response=Mock(text=wrap(INTRO,100,'00')+wrap(CANCEL,101,'05')+wrap('Черга 1.1: 09:00-13:00',102,'10'))
        session=Mock()
        session.get.return_value=response
        with patch.object(scraper,'MAX_PAGES',1),patch.object(scraper.time,'sleep'):
            schedules,events=scraper.scan_channel(session,self.t.date())
        self.assertEqual(len(schedules),1)
        self.assertEqual(len(events),2)
        state=merge_emergency(None,events)
        self.assertFalse(state['active'])
        self.assertEqual(state['source_url'],'https://t.me/zoe_alarm/101')

    def test_status_only_update_preserves_schedules(self):
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory)/'schedule.json'
            original=[{'date':'17.11.2026','published_at':self.t.isoformat(),'queues':{'1.1':'09:00 - 13:00'}}]
            out.write_text(json.dumps(original))
            with patch.object(scraper,'OUTPUT',out), patch.object(scraper,'scan_channel',return_value=({},[self.parse(INTRO)])):
                self.assertEqual(scraper.main(),0)
            saved=json.loads(out.read_text())
            self.assertEqual(saved[0]['queues'],original[0]['queues'])
            self.assertTrue(saved[0]['emergency']['active'])
            with patch.object(scraper,'OUTPUT',out), patch.object(scraper,'scan_channel',return_value=({},[self.parse(CANCEL,5)])):
                scraper.main()
            self.assertFalse(json.loads(out.read_text())[0]['emergency']['active'])
            before=out.read_text()
            with patch.object(scraper,'OUTPUT',out), patch.object(scraper,'scan_channel',return_value=({},[])):
                scraper.main()
            self.assertEqual(out.read_text(),before)

    def test_future_directive_not_applied_early(self):
        for text in ['З 14:00 введено ГАВ.', 'ГАВ скасовані з 14:00.']:
            with self.subTest(text=text):
                self.assertEqual(parse_emergency(text,self.t,now=self.t),{})
                self.assertTrue(parse_emergency(text,self.t,now=self.t+timedelta(hours=2)))

    def test_ubuntu_import_and_empty_result(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('lumina_scraper', Path(scraper.__file__))
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertFalse(module.ChannelScan({},[]))
        self.assertTrue(module.ChannelScan({},[self.parse(INTRO)]))

    def test_no_schedule_yet(self):
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory)/'schedule.json'
            with patch.object(scraper,'OUTPUT',out), patch.object(scraper,'scan_channel',return_value=({},[self.parse(INTRO)])):
                scraper.main()
            saved=json.loads(out.read_text())
            self.assertEqual(saved[0]['queues'],{})
            self.assertTrue(saved[0]['emergency']['active'])

if __name__=='__main__': unittest.main()
