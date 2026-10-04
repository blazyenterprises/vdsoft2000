"""Derik: single synthesis worker, cancellable DSP and NVDA audio playback."""
from collections import OrderedDict
import array
import sys
import queue
import threading
import re
import unicodedata
from autoSettingsUtils.driverSetting import NumericDriverSetting
import config
import nvwave
from logHandler import log
from speech.commands import IndexCommand, CharacterModeCommand, BreakCommand, PitchCommand, RateCommand, VolumeCommand
from synthDriverHandler import SynthDriver as Base, VoiceInfo, synthIndexReached, synthDoneSpeaking
from .english import English, LETTERS
from .engine import VOICES, configured_voice, SR, synthesize

def clamp(value): return max(0,min(100,int(value)))

def rate_scale(value):
    value=clamp(value)
    # Preserve the slow end; old midpoint is now 30, with a faster new midpoint.
    anchors=((0,.4),(30,1.),(50,1.45),(100,2.5))
    for (lo,a),(hi,b) in zip(anchors,anchors[1:]):
        if value<=hi:return a*(b/a)**((value-lo)/(hi-lo))
    return 2.5

# RMS calibration against 0.3.0 across four speech passages per voice.
REFERENCE_LEVEL={'derik':1.8231,'jeff':3.0328,'female1':2.0312,'female2':2.7417,'child':2.,'alien':2.,'robot':1.8,'oldman':2.6,'oldlady':2.2}

def volume_audio(pcm,identity,volume):
    samples=array.array('h',pcm)
    if sys.byteorder!='little':samples.byteswap()
    peak=max(map(abs,samples),default=0)
    gain=REFERENCE_LEVEL[identity]*clamp(volume)/50
    # Scale whole block linearly if it exceeds headroom; never flatten peaks.
    if peak:gain=min(gain,.94*32767/peak)
    result=array.array('h',(int(x*gain) for x in samples))
    if sys.byteorder!='little':result.byteswap()
    return result.tobytes()

class SynthDriver(Base):
    name='vdsoft2000'
    description='VDSoft2000'
    supportedSettings=(Base.VoiceSetting(),Base.RateSetting(),Base.RateBoostSetting(),Base.PitchSetting(),Base.InflectionSetting(),Base.VolumeSetting(),
        NumericDriverSetting('roughness','Roughness',availableInSettingsRing=True,defaultVal=0),
        NumericDriverSetting('breathiness','Breathiness',availableInSettingsRing=True,defaultVal=50),
        NumericDriverSetting('headSize','Head size',availableInSettingsRing=True,defaultVal=50),
        NumericDriverSetting('vocalTract','Vocal tract',availableInSettingsRing=True,defaultVal=50),
        NumericDriverSetting('gender','Gender',availableInSettingsRing=True,defaultVal=50))
    supportedCommands={IndexCommand,CharacterModeCommand,BreakCommand,PitchCommand,RateCommand,VolumeCommand}
    supportedNotifications={synthIndexReached,synthDoneSpeaking}

    @classmethod
    def check(cls): return True

    def __init__(self):
        super().__init__()
        self._rate=self._pitch=self._inflection=self._volume=50
        self._roughness=0
        self._breathiness=self._headSize=self._vocalTract=self._gender=50
        self._voice='derik'
        self._rateBoost=False
        self._queue=queue.Queue()
        self._lock=threading.RLock()
        self._generation=0
        self._closed=False
        self._ready=threading.Event();self._ready.set()
        self._player=None
        self._worker=threading.Thread(target=self._run,name='VDSoft2000',daemon=True)
        self._worker.start()

    def _getAvailableVoices(self):
        return OrderedDict((key,VoiceInfo(key,preset.name+' (U.S. English)','en_US')) for key,preset in VOICES.items())
    def _get_voice(self): return self._voice
    def _set_voice(self,value):
        if value not in VOICES:raise LookupError(value)
        self._voice=value
    def _get_roughness(self):return self._roughness
    def _set_roughness(self,value):self._roughness=clamp(value)
    def _get_breathiness(self):return self._breathiness
    def _set_breathiness(self,value):self._breathiness=clamp(value)
    def _get_headSize(self):return self._headSize
    def _set_headSize(self,value):self._headSize=clamp(value)
    def _get_vocalTract(self):return self._vocalTract
    def _set_vocalTract(self,value):self._vocalTract=clamp(value)
    def _get_gender(self):return self._gender
    def _set_gender(self,value):self._gender=clamp(value)
    def _get_volume(self):return self._volume
    def _set_volume(self,value):self._volume=clamp(value)
    def _get_rate(self):return self._rate
    def _set_rate(self,value):self._rate=clamp(value)
    def _get_rateBoost(self):return self._rateBoost
    def _set_rateBoost(self,value):self._rateBoost=bool(value)
    def _get_pitch(self):return self._pitch
    def _set_pitch(self,value):self._pitch=clamp(value)
    def _get_inflection(self):return self._inflection
    def _set_inflection(self,value):self._inflection=clamp(value)

    def speak(self,speechSequence):
        # Snapshot NVDA's prosody commands on its thread (newValue reads config).
        parts=[]
        for item in speechSequence:
            if isinstance(item,str):parts.append(('text',item))
            elif isinstance(item,IndexCommand):parts.append(('index',item.index))
            elif isinstance(item,CharacterModeCommand):parts.append(('spell',item.state))
            elif isinstance(item,BreakCommand):parts.append(('break',max(0,item.time)))
            elif isinstance(item,PitchCommand):parts.append(('pitch',clamp(item.newValue)))
            elif isinstance(item,RateCommand):parts.append(('rate',clamp(item.newValue)))
            elif isinstance(item,VolumeCommand):parts.append(('volume',clamp(item.newValue)))
        with self._lock:
            if not self._closed:
                self._queue.put((self._generation,parts,self._rate,self._pitch,self._inflection,self._voice,self._rateBoost,self._volume,dict(roughness=self._roughness,breathiness=self._breathiness,headSize=self._headSize,vocalTract=self._vocalTract,gender=self._gender)))

    def cancel(self):
        with self._lock:
            self._generation+=1
            self._ready.set()
            while True:
                try:self._queue.get_nowait()
                except queue.Empty:break
            if self._player:self._player.stop()

    def pause(self,switch):
        with self._lock:
            if switch:self._ready.clear()
            else:self._ready.set()
            if self._player:self._player.pause(switch)

    def terminate(self):
        self.cancel()
        with self._lock:
            self._closed=True
            self._queue.put(None)
        self._worker.join(timeout=3)

    def _valid(self,g):return not self._closed and g==self._generation

    def _feed(self,pcm,g):
        # Feed short blocks so pause/cancel never waits for a whole paragraph.
        for offset in range(0,len(pcm),2204):
            self._ready.wait()
            if not self._valid(g):return
            self._player.feed(pcm[offset:offset+2204])
            if not self._valid(g):
                self._player.stop()
                return

    def _run(self):
        try:english=English()
        except Exception:
            log.exception('VDSoft2000 dictionary failed to load')
            return
        while True:
            job=self._queue.get()
            if job is None:return
            g,parts,rate,pitch,inflection,identity,rateBoost,volume,character=job
            if not self._valid(g):continue
            try:
                with self._lock:
                    if not self._valid(g):continue
                    self._player=nvwave.WavePlayer(channels=1,samplesPerSec=SR,bitsPerSample=16,
                        outputDevice=config.conf['audio']['outputDevice'],wantDucking=True)
                    self._player.pause(not self._ready.is_set())
                spell=False
                for kind,value in parts:
                    if not self._valid(g):break
                    self._ready.wait()
                    if not self._valid(g):break
                    if kind=='spell':spell=value
                    elif kind=='pitch':pitch=value
                    elif kind=='rate':rate=value
                    elif kind=='volume':volume=value
                    elif kind=='index':
                        self._player.idle()
                        with self._lock:
                            if self._valid(g):synthIndexReached.notify(synth=self,index=value)
                    elif kind=='break':
                        for start in range(0,value,50):
                            if not self._valid(g):break
                            self._feed(b'\0\0'*int(SR*min(50,value-start)/1000),g)
                    elif kind=='text':
                        # Bound latency and memory for long documents at phrase/word boundaries.
                        chunks=re.findall(r'.{1,180}(?:\s+|$)|\S{1,180}',value,re.S)
                        for chunk in chunks:
                            if not self._valid(g):break
                            # English-only: name unsupported characters rather than killing speech.
                            chunk=''.join(c if c.isascii() else ' '+unicodedata.name(c,'unknown character').lower()+' ' for c in chunk if unicodedata.category(c)!='Cf' and not (0xFE00<=ord(c)<=0xFE0F or 0xE0100<=ord(c)<=0xE01EF))
                            if spell:
                                phones=[]
                                for c in chunk:
                                    if c.isalpha():phones.extend(LETTERS[ord(c.lower())-97].split())
                                    else:phones.extend(english.convert('space' if c.isspace() else c)[0])
                                    phones.append('|')
                            else:phones,_=english.convert(chunk)
                            voice=configured_voice(identity,pitch,inflection,**character)
                            synthesize(phones,voice,rate_scale(rate)*(2 if rateBoost else 1),cancelled=lambda:not self._valid(g),
                                       on_audio=lambda pcm:self._feed(volume_audio(pcm,identity,volume),g))
                if self._valid(g):
                    self._player.idle()
                    with self._lock:
                        if self._valid(g):synthDoneSpeaking.notify(synth=self)
            except Exception:
                log.exception('VDSoft2000 synthesis failed')
                with self._lock:
                    if self._valid(g):synthDoneSpeaking.notify(synth=self)
            finally:
                with self._lock:
                    if self._player:
                        self._player.stop()
                        self._player=None
