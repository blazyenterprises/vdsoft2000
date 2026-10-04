"""Exercise packaged driver with real synthesis and a simulated NVDA host."""
import importlib.util
import sys
import types
import threading
import time
import unittest
from pathlib import Path

class Base:
    @staticmethod
    def VoiceSetting():return 'voice'
    @staticmethod
    def RateSetting():return 'rate'
    @staticmethod
    def RateBoostSetting():return 'rateBoost'
    @staticmethod
    def PitchSetting():return 'pitch'
    @staticmethod
    def VolumeSetting():return 'volume'
    @staticmethod
    def InflectionSetting():return 'inflection'
class Event:
    def __init__(self):self.items=[];self.signal=threading.Event()
    def notify(self,**kw):self.items.append(kw);self.signal.set()
class Player:
    instances=[]
    def __init__(self,**kw):self.kw=kw;self.audio=[];self.pauses=[];self.stops=0;Player.instances.append(self)
    def feed(self,data):self.audio.append(data)
    def idle(self):pass
    def stop(self):self.stops+=1
    def pause(self,value):self.pauses.append(value)
def cmd(name,attr):
    return type(name,(),{'__init__':lambda self,value:setattr(self,attr,value)})
commands=types.SimpleNamespace(**{name:cmd(name,attr) for name,attr in [('IndexCommand','index'),('CharacterModeCommand','state'),('BreakCommand','time'),('PitchCommand','newValue'),('RateCommand','newValue'),('VolumeCommand','newValue')]})
done=Event();index=Event();errors=[]
sys.modules['autoSettingsUtils']=types.ModuleType('autoSettingsUtils')
sys.modules['autoSettingsUtils.driverSetting']=types.SimpleNamespace(NumericDriverSetting=lambda key,*a,**kw:key)
sys.modules['config']=types.SimpleNamespace(conf={'audio':{'outputDevice':'chosen-device'}})
sys.modules['nvwave']=types.SimpleNamespace(WavePlayer=Player)
sys.modules['logHandler']=types.SimpleNamespace(log=types.SimpleNamespace(exception=lambda msg:errors.append((msg,sys.exception()))))
sys.modules['speech']=types.ModuleType('speech');sys.modules['speech.commands']=commands
sys.modules['synthDriverHandler']=types.SimpleNamespace(SynthDriver=Base,VoiceInfo=lambda *a:a,synthIndexReached=index,synthDoneSpeaking=done)
path=Path(__file__).parent/'addon/synthDrivers/vdsoft2000/__init__.py'
spec=importlib.util.spec_from_file_location('testvdsoft',path,submodule_search_locations=[str(path.parent)])
m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)

class TestAddon(unittest.TestCase):
    def setUp(self):
        errors.clear();done.items.clear();done.signal.clear();index.items.clear();Player.instances.clear()
        self.d=m.SynthDriver()
    def tearDown(self):
        self.d.terminate();self.assertFalse(self.d._worker.is_alive());self.assertFalse(errors,errors)
    def wait(self,count=1):
        end=time.monotonic()+5
        while len(done.items)<count and time.monotonic()<end:time.sleep(.01)
        self.assertEqual(len(done.items),count);self.assertFalse(errors,errors)
    def test_settings_and_real_audio(self):
        self.assertEqual(self.d._getAvailableVoices()['derik'][2],'en_US')
        self.assertEqual(set(self.d.supportedSettings),{'voice','rate','rateBoost','pitch','inflection','volume','roughness','breathiness','headSize','vocalTract','gender'})
        for setting in ('rate','pitch','inflection'):
            getattr(self.d,'_set_'+setting)(130);self.assertEqual(getattr(self.d,'_get_'+setting)(),100)
            getattr(self.d,'_set_'+setting)(50)
        self.d.speak(['Hello Brandon.',commands.IndexCommand(7),'Three.'])
        self.wait()
        self.assertEqual([x['index'] for x in index.items],[7])
        self.assertEqual(Player.instances[0].kw['outputDevice'],'chosen-device')
        self.assertGreater(sum(map(len,Player.instances[0].audio)),22050)
    def test_queue_commands(self):
        self.d.speak([commands.CharacterModeCommand(True),'abc3',commands.CharacterModeCommand(False),commands.BreakCommand(60),commands.PitchCommand(90),commands.RateCommand(90),'Hello.'])
        self.d.speak(['Second message.'])
        self.wait(2)

    def test_invisible_formatting(self):
        self.d.speak(['Hello.']);self.wait()
        plain=b''.join(Player.instances[-1].audio)
        self.d.speak(['\u2068Hello\u2069.\u200e\u200f\ufeff\u200b\ufe0f']);self.wait(2)
        self.assertEqual(b''.join(Player.instances[-1].audio),plain)
        self.d.speak([commands.CharacterModeCommand(True),'\u2068\u2069\u200d']);self.wait(3)
        self.assertFalse(Player.instances[-1].audio)
    def test_rate_scale(self):
        self.assertAlmostEqual(m.rate_scale(30),1)
        self.assertAlmostEqual(m.rate_scale(50),1.45)
        self.assertAlmostEqual(m.rate_scale(0),.4)
        self.assertAlmostEqual(m.rate_scale(100),2.5)
        self.assertTrue(all(m.rate_scale(n)<m.rate_scale(n+1) for n in range(100)))

    def test_volume(self):
        import array
        self.assertEqual(self.d._get_volume(),50)
        pcm=array.array('h',[1000,-1000,0]).tobytes()
        for identity in m.REFERENCE_LEVEL:
            self.assertEqual(m.volume_audio(pcm,identity,0),b'\0'*len(pcm))
            low=array.array('h',m.volume_audio(pcm,identity,25))
            normal=array.array('h',m.volume_audio(pcm,identity,50))
            self.assertAlmostEqual(normal[0]/low[0],2,delta=.002)
            loud=array.array('h',m.volume_audio(array.array('h',[30000,-30000]).tobytes(),identity,100))
            self.assertLess(max(map(abs,loud)),32767)
        self.d.speak([commands.VolumeCommand(0),'Hello.'])
        self.wait()
        self.assertFalse(any(b''.join(Player.instances[-1].audio)))

    def test_character_settings(self):
        for key in ('roughness','breathiness','headSize','vocalTract','gender'):
            self.assertEqual(getattr(self.d,'_get_'+key)(),0 if key=='roughness' else 50)
            getattr(self.d,'_set_'+key)(150)
            self.assertEqual(getattr(self.d,'_get_'+key)(),100)
        self.d.speak(['Many voices.']);self.wait()
        self.assertTrue(any(b''.join(Player.instances[-1].audio)))
    def test_rate_boost(self):
        self.assertFalse(self.d._get_rateBoost())
        self.d._set_rate(100)
        self.d.speak(['Hello Brandon.']);self.wait()
        normal=sum(map(len,Player.instances[-1].audio))
        self.d._set_rateBoost(True)
        self.d.speak(['Hello Brandon.']);self.wait(2)
        boosted=sum(map(len,Player.instances[-1].audio))
        self.assertGreater(boosted,0)
        self.assertAlmostEqual(boosted/normal,.5,delta=.01)
    def test_voice_selection_snapshot(self):
        voices=self.d._getAvailableVoices()
        self.assertEqual(list(voices),['derik','jeff','female1','female2','child','alien','robot','oldman','oldlady'])
        self.d.pause(True)
        for voice in voices:
            self.d._set_voice(voice)
            self.d.speak(['Hello.'])
        self.d.pause(False)
        self.wait(len(voices))
        audio=[b''.join(p.audio) for p in Player.instances]
        self.assertEqual(len(set(audio)),len(voices))
        self.assertTrue(all(audio))
        with self.assertRaises(LookupError):self.d._set_voice('missing')
    def test_cancel_while_rendering(self):
        entered=threading.Event();original=m.synthesize
        def blocked(*args,**kw):
            entered.set()
            end=time.monotonic()+3
            while not kw['cancelled']() and time.monotonic()<end:time.sleep(.005)
            return b''
        m.synthesize=blocked
        try:
            self.d.speak(['Long speech.',commands.IndexCommand(99)])
            self.assertTrue(entered.wait(3));self.d.cancel()
            m.synthesize=original
            self.d.speak(['New speech.']);self.wait()
            self.assertEqual(index.items,[])
            self.assertFalse(Player.instances[0].audio)
        finally:m.synthesize=original
    def test_pause_and_resume(self):
        self.d.pause(True);self.d.speak(['Hello.'])
        time.sleep(.2)
        self.assertFalse(done.items)
        self.d.pause(False);self.wait()

if __name__=='__main__':unittest.main()
