"""VDSoft2000 experimental source/filter synthesizer. No recorded speech."""
from dataclasses import dataclass, replace
import array
import math
import random
import re
import sys
import wave

SR = 22050
# Starting acoustic targets, tuned as a US male prototype, not DECtalk data.
VOWELS = {
 'IY':(280,2250,3000), 'IH':(390,1950,2650), 'EH':(530,1800,2500),
 'AE':(680,1700,2450), 'AA':(730,1100,2450), 'AO':(570,850,2400),
 'UH':(430,1100,2350), 'UW':(300,800,2200), 'AH':(600,1200,2500),
 'AX':(450,1450,2500), 'ER':(470,1300,1680),
 'EY':(480,1950,2600), 'AY':(740,1250,2500), 'OW':(500,950,2450),
 'AW':(730,1200,2450), 'OY':(570,850,2450),
}
END = {'EY':'IY','AY':'IH','OW':'UW','AW':'UH','OY':'IH'}
SONORANTS = {'R':(350,1300,1650),'L':(380,1100,2650),'W':(260,650,2200),
 'Y':(250,2350,3000),'M':(250,1000,2100),'N':(280,1500,2400),'NG':(300,1800,2600)}
FRICATIVES = {'F':(1400,4200),'V':(1400,4200),'TH':(1700,4500),'DH':(1700,4500),
 'S':(4500,6800),'Z':(4500,6800),'SH':(2300,3800),'ZH':(2300,3800),'HH':(1000,2400)}
STOPS = {'P':(800,2500),'B':(800,2500),'T':(3500,5500),'D':(3500,5500),
 'K':(1700,3500),'G':(1700,3500),'CH':(2300,3800),'JH':(2300,3800)}
ALL_PHONES = set(VOWELS)|set(SONORANTS)|set(FRICATIVES)|set(STOPS)

@dataclass(frozen=True)
class Voice:
    name: str = 'Derik'
    style: str = 'human'
    pitch: float = 112.0
    tract_scale: float = 1.0
    breath: float = .015
    expression: float = 1.0
    closure: float = .85
    roughness: float = 0.0
    tremor: float = 0.0
    consonant_scale: float = 1.0
    consonant_gain: float = 1.0
    consonant_length: float = 1.0
    transition: float = .22
    aspiration: float = 1.0
    formant_offsets: tuple = (0.,0.,0.)
    formant_gains: tuple = (1.,.85,.55,.20)

VOICES = {
    'derik': Voice(),
    'jeff': Voice(name='Jeff',pitch=98,tract_scale=.92,breath=.012,expression=.85,
                  closure=.74,consonant_scale=.88,consonant_gain=.80,consonant_length=1.12,
                  transition=.30,aspiration=.65,formant_offsets=(35,-80,120),formant_gains=(1.,.95,.65,.22)),
    'female1': Voice(name='Roxanne',pitch=195,tract_scale=1.18,breath=.018,
                     expression=1.05,closure=.87,consonant_scale=1.12,consonant_gain=1.12,
                     consonant_length=.88,transition=.15,aspiration=1.15,formant_offsets=(-20,100,50),formant_gains=(.85,1.,.65,.25)),
    'female2': Voice(name='Josie',pitch=165,tract_scale=1.10,breath=.035,
                     expression=.90,closure=.78,consonant_scale=.95,consonant_gain=.78,
                     consonant_length=1.08,transition=.29,aspiration=.80,formant_offsets=(30,-90,-80),formant_gains=(1.,.80,.48,.16)),
    'child': Voice(name='Child',pitch=255,tract_scale=1.32,breath=.022,
                   expression=1.15,closure=.82,consonant_scale=1.20,
                   consonant_length=.86,transition=.17,formant_gains=(.85,1.,.70,.24)),
    'alien': Voice(name='Alien',style='alien',pitch=138,tract_scale=.88,breath=.02,
                   expression=1.25,closure=.88,consonant_scale=1.12,
                   transition=.32,formant_offsets=(100,-240,310),formant_gains=(.8,1.,.85,.30)),
    'robot': Voice(name='Robot',style='robot',pitch=100,tract_scale=1.02,breath=.005,
                   expression=.15,closure=.90,consonant_scale=1.05,
                   transition=.08,formant_gains=(.9,1.,.70,.28)),
    'oldman': Voice(name='Old Man',pitch=105,tract_scale=.95,breath=.075,
                    expression=.82,closure=.76,tremor=.025,consonant_scale=.90,
                    consonant_gain=.82,consonant_length=1.18,transition=.30,
                    aspiration=.85,formant_offsets=(20,-90,80),formant_gains=(1.,.78,.46,.15)),
    'oldlady': Voice(name='Old Lady',pitch=178,tract_scale=1.12,breath=.09,
                     expression=1.08,closure=.80,tremor=.035,consonant_scale=1.02,
                     consonant_gain=.90,consonant_length=1.12,transition=.27,
                     aspiration=.95,formant_offsets=(45,100,-60),formant_gains=(.90,.95,.55,.20)),
}

def configured_voice(identity, pitch=50, inflection=50, roughness=0, breathiness=50, headSize=50, vocalTract=50, gender=50):
    preset=VOICES[identity]
    shape=(vocalTract-50)/50
    gender_shift=(gender-50)/50
    size=2**(-(headSize-50)/180)
    return replace(preset,
        pitch=max(60,min(300,preset.pitch*2**((pitch-50)/50+gender_shift*.30))),
        expression=min(2,preset.expression*inflection/50),
        roughness=max(0,min(100,roughness))/100,
        breath=preset.breath*(breathiness/50) if breathiness<=50 else preset.breath+.65*((breathiness-50)/50)**1.3,
        tract_scale=max(.7,min(1.4,preset.tract_scale*size)),
        consonant_scale=max(.7,min(1.3,preset.consonant_scale*size**.4)),
        formant_offsets=tuple(a+b*shape+c*gender_shift for a,b,c in zip(preset.formant_offsets,(100,-180,140),(0,80,120))),
        closure=max(.65,min(.91,preset.closure+.035*gender_shift)))

def base(p): return re.sub('[012]$','',p)
def target(p):
    return VOWELS.get(base(p), SONORANTS.get(base(p),(450,1450,2500)))
def mix(a,b,t): return tuple(x+(y-x)*t for x,y in zip(a,b))

def pitch_plan(phones):
    """Nine semitone targets per phone, with accents continuous across phones."""
    plan=[(0.,)*9 for _ in phones]
    phrase=[]
    def finish(ending):
        if not phrase:return
        length=len(phrase)
        accents=[j+.55 for j,idx in enumerate(phrase) if phones[idx].endswith('1')]
        for j,idx in enumerate(phrase):
            values=[]
            for step in range(9):
                pos=j+step/8
                progress=pos/length
                # Phrase declination and stressed syllable peaks; broader than
                # one vowel, so pitch does not restart on each consonant.
                tone=(2.4-2.0*progress) if ending=='!' else (1.1-2.0*progress)
                for k,center in enumerate(accents):
                    height=3.1 if k==len(accents)-1 else 2.3
                    if ending=='!':height*=1.65
                    tone+=height*math.exp(-.5*((pos-center)/.8)**2)
                final=max(0.,min(1.,(progress-.72)/.28))
                final=final*final*(3-2*final)
                tone+=({'?':4.5, ',':1.8, '!':-3.8}.get(ending,-2.6))*final
                values.append(tone)
            plan[idx]=tuple(values)
        phrase.clear()
    for idx,p in enumerate(phones):
        if p in ('.','?','!',','):finish(p)
        elif p!='|':phrase.append(idx)
    finish('.')
    return plan

class Resonator:
    def __init__(self): self.y1=self.y2=0.0
    def tune(self,f,bw):
        r=math.exp(-math.pi*bw/SR)
        self.a=2*r*math.cos(2*math.pi*f/SR); self.b=-r*r
        # Normalize at the requested resonance. The old (1-r) gain strongly
        # favored low formants, burying the vowel's higher resonances.
        omega=2*math.pi*f/SR
        self.g=(1-r)*math.sqrt(1+r*r-2*r*math.cos(2*omega))
    def tick(self,x):
        y=self.g*x+self.a*self.y1+self.b*self.y2
        self.y2,self.y1=self.y1,y
        return y

class NasalNotch:
    def __init__(self, frequency):
        self.c=2*math.cos(2*math.pi*frequency/SR)
        self.r=math.exp(-math.pi*350/SR)
        self.x1=self.x2=self.y1=self.y2=0.
    def tick(self,x):
        y=x-self.c*self.x1+self.x2+self.r*self.c*self.y1-self.r*self.r*self.y2
        self.x2,self.x1=self.x1,x
        self.y2,self.y1=self.y1,y
        return y

def encode(samples):
    # Conservative linear gain preserves consonant and vowel waveforms.
    # The final clamp is only an overflow guard, not a sound-shaping limiter.
    pcm=array.array('h',(int(max(-.95,min(.95,x*.20))*32767) for x in samples))
    if sys.byteorder!='little':pcm.byteswap()
    return pcm.tobytes()

def synthesize(phones, voice=Voice(), rate=1.0, cancelled=None, on_audio=None):
    if not .4<=rate<=5: raise ValueError('Rate must be between 0.4 and 5.')
    if not 60<=voice.pitch<=300: raise ValueError('Pitch must be between 60 and 300 Hz.')
    if not .7<=voice.tract_scale<=1.4: raise ValueError('Tract scale must be between 0.7 and 1.4.')
    if not 0<=voice.expression<=2: raise ValueError('Inflection must be between 0 and 2.')
    contours=pitch_plan(phones)
    rng=random.Random(2000)
    filters=[Resonator() for _ in range(4)]; noise_filters=[Resonator(),Resonator()]
    phase=0.; samples=[]; elapsed=0.; dc_x=dc_y=0.
    for idx, raw in enumerate(phones):
        if cancelled and cancelled(): return b''
        if on_audio and samples:
            on_audio(encode(samples));samples.clear()
            if cancelled and cancelled():return b''
        p=base(raw)
        if p in ('|',',','.','?','!'):
            duration={'|':.012,',':.16,'.':.30,'?':.30,'!':.30}[p]/rate
            samples.extend([0.]*int(duration*SR))
            for f in filters+noise_filters:f.y1=f.y2=0.
            if p in ('.','?','!'): elapsed=0.
            continue
        if p not in ALL_PHONES: raise ValueError('Unsupported phoneme: '+raw)
        vowel=p in VOWELS; stop=p in STOPS; fric=p in FRICATIVES
        stressed=raw.endswith('1')
        duration=(.145 if vowel else .105 if fric else .095 if stop else .085)
        if not vowel: duration*=voice.consonant_length
        if vowel: duration*=1.18 if stressed else .78 if raw.endswith('0') else 1.
        if voice.style=='robot':duration=.12 if vowel else .09
        if idx+1==len(phones) or phones[idx+1] in ('.','?','!',','):duration*=1.25
        n=max(1,int(duration/rate*SR))
        here=VOWELS['AX'] if raw=='AH0' else target(raw)
        before=target(phones[idx-1]) if idx and phones[idx-1] not in ('|','.',',','?','!') else here
        after=target(phones[idx+1]) if idx+1<len(phones) and phones[idx+1] not in ('|','.',',','?','!') else here
        if p=='HH':here=after
        if p in ('K','G'):
            # Velar closure/release: bring F2/F3 together, then release into vowel.
            locus=max(1500,min(2500,after[1]*.75+650))
            here=(280,locus,locus+350)
        noise_target=FRICATIVES.get(p,STOPS.get(p,(1500,4000)))
        if p in ('K','G'):noise_target=(locus,locus+650)
        for f,hz in zip(noise_filters,noise_target):f.tune(hz*voice.consonant_scale,450 if p in ('K','G') else 800)
        breath_filter=Resonator();breath_filter.tune(1700*voice.tract_scale,1800)
        nasal=p in ('M','N','NG')
        notch=NasalNotch({'M':900,'N':1500,'NG':2100}.get(p,900)*voice.tract_scale) if nasal else None
        contour=contours[idx]
        for i in range(n):
            if i%256==0 and cancelled and cancelled(): return b''
            t=i/max(1,n-1)
            if i%64==0:
                formants=here
                if p in END:formants=mix(here,VOWELS[END[p]],min(1,max(0,(t-.25)/.7)))
                if t<voice.transition:formants=mix(mix(before,here,.55),formants,t/voice.transition)
                elif t>1-voice.transition:formants=mix(formants,mix(here,after,.35),(t-1+voice.transition)/voice.transition)
                formants=tuple(f+offset for f,offset in zip(formants,voice.formant_offsets))
                bands=(90,110,150,220) if not nasal else (55,220,280,350)
                for f,hz,bw in zip(filters,(*formants,3500),bands):f.tune(hz*voice.tract_scale,bw)
            segment=min(7,int(t*8)); fraction=t*8-segment
            semitones=contour[segment]+fraction*(contour[segment+1]-contour[segment])
            if voice.style=='robot':semitones=round(semitones)
            f0=voice.pitch*2**(voice.expression*semitones/12)
            if voice.tremor:f0*=1+voice.tremor*(math.sin(elapsed*2*math.pi*5.2)+.35*math.sin(elapsed*2*math.pi*7.1))
            if voice.style=='alien':f0*=1+.045*math.sin(elapsed*2*math.pi*6)
            if voice.roughness:
                f0*=1+voice.roughness*(.035*math.sin(elapsed*2*math.pi*37)+.018*math.sin(elapsed*2*math.pi*61))
            phase=(phase+f0/SR)%1
            # Faster glottal closure supplies harmonics to the upper formants.
            # Equal positive/negative areas retain a zero-mean source.
            opening=voice.closure
            source=math.sin(math.pi*phase/opening) if phase<opening else -(opening/(1-opening))*math.sin(math.pi*(phase-opening)/(1-opening))
            if voice.style=='alien':source*=.65+.35*math.cos(elapsed*2*math.pi*67)
            elif voice.style=='robot':source=.65*source+.35*(2*phase-1)
            if voice.roughness:source*=1-.25*voice.roughness*(1+math.sin(elapsed*math.pi*voice.pitch))
            noise=rng.uniform(-1,1)
            voiced=vowel or p in SONORANTS or p in ('B','D','G','V','DH','Z','ZH','JH')
            amplitude=1. if vowel else .65 if p in SONORANTS else .22
            burst=1.; aspiration=0.
            if stop:
                if p in ('CH','JH'):
                    release=.35
                    since=(t-release)*duration/rate
                    burst=0. if since<0 else .65+1.4*math.exp(-since/.007)
                    amplitude=.035 if t<release else .30
                else:
                    # Voiceless stops: closure, strong transient, aspirated release.
                    # Voiced stops: closure voicing, softer transient, early voicing.
                    release=.48 if voiced else .42
                    since=(t-release)*duration/rate
                    burst=0. if since<0 else math.exp(-since/.009)*( .48 if voiced else 1.5)
                    if p in ('K','G') and since>=0:
                        burst=math.exp(-since/.016)*(1.1 if voiced else 2.5)
                    amplitude=(.16 if t<release else .38) if voiced else 0.
                    if not voiced and since>=0:
                        aspiration=.48*voice.aspiration*(1-math.exp(-since/.004))*math.exp(-since/.05)
            excitation=(source*amplitude*(1-min(.25,voice.breath*.3)) if voiced else 0)+noise*(voice.breath if not stop else 0.)
            if aspiration:excitation+=noise*aspiration
            if p=='HH':excitation=noise*.45*voice.aspiration
            # Nasal murmur dominates, while oral resonances are attenuated.
            gains=(1.35,.18,.10,.035) if nasal else voice.formant_gains
            resonated=sum(f.tick(excitation)*gain for f,gain in zip(filters,gains))
            if nasal:resonated=notch.tick(resonated)
            hiss=sum(f.tick(noise) for f in noise_filters)*(.42 if p in ('S','Z','SH','ZH','CH','JH') else .18)*voice.consonant_gain
            signal=resonated+(hiss*burst if fric and p!='HH' or stop else 0.)
            # Audible aspiration around the voiced source, rather than only low resonances.
            if vowel or p in SONORANTS:signal+=breath_filter.tick(noise)*max(0,voice.breath-.04)*1.8
            # Short ramps suppress waveform discontinuities, not inter-phone padding.
            edge=min(1.,i/(SR*.003),(n-1-i)/(SR*.003))
            signal*=max(0,edge)
            y=signal-dc_x+.995*dc_y; dc_x,dc_y=signal,y
            samples.append(y); elapsed+=1/SR
    pcm=encode(samples)
    if on_audio:
        if pcm and not (cancelled and cancelled()):on_audio(pcm)
        return b''
    return pcm


def save(path, pcm):
    with wave.open(str(path),'wb') as w:
        w.setparams((1,2,SR,0,'NONE',''));w.writeframes(pcm)
