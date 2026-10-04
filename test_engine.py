import array
import json
import math
from pathlib import Path
import unittest
from dataclasses import replace
from english import English, number, LETTERS
from engine import ALL_PHONES, Voice, base, synthesize, save, SR, pitch_plan, VOICES, configured_voice

class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.en=English()
    def test_inventory(self):
        missing={base(p) for phones in self.en.lexicon.values() for p in phones}-ALL_PHONES
        self.assertEqual(missing,set())
    def test_numbers(self):
        self.assertEqual(number('2000'),'two thousand')
        self.assertEqual(number('-3.05'),'minus three point zero five')
        self.assertEqual(number('007'),'zero zero seven')
        for n in range(1000):
            phones,unknown=self.en.convert(str(n))
            self.assertTrue(phones);self.assertFalse(unknown)
    def test_unknown_and_language(self):
        self.assertEqual(self.en.convert('zzzzq')[1],['zzzzq'])
        with self.assertRaises(ValueError):self.en.convert('\u062b\u0644\u0627\u062b\u0629')

    def test_unknown_pronunciation(self):
        self.assertEqual(self.en.pronounce('useable'),self.en.pronounce('usable'))
        self.assertEqual(self.en.pronounce('wize'),['W','AY1','Z'])
        self.assertEqual(self.en.pronounce('shplooft'),['SH','P','L','UW1','F','T'])
        for word in ('useable','wize','shplooft','blorfts','alexalupios','snazzifying'):
            phones=self.en.pronounce(word)
            spelling=[p for c in word for p in LETTERS[ord(c)-97].split()]
            self.assertNotEqual(phones,spelling)
            self.assertTrue(all(base(p) in ALL_PHONES for p in phones))
            self.assertTrue(synthesize(phones))
        self.assertEqual(self.en.pronounce('hello'),self.en.lexicon['hello'])
    def test_render(self):
        phones,unknown=self.en.convert('Three clear voices. Hello Brandon!')
        self.assertFalse(unknown)
        pcm=synthesize(phones)
        a=array.array('h',pcm)
        self.assertGreater(len(a),SR)
        self.assertGreater(math.sqrt(sum(x*x for x in a)/len(a)),300)
        self.assertLess(max(map(abs,a)),32767)
        self.assertEqual(pcm,synthesize(phones))
        self.assertLess(len(synthesize(phones,rate=1.5)),len(pcm))
        self.assertNotEqual(pcm,synthesize(phones,Voice(pitch=145)))
    def test_all_phones(self):
        for p in sorted(ALL_PHONES):
            a=array.array('h',synthesize([p]))
            self.assertGreater(max(map(abs,a)),10,p)
    def test_empty_and_validation(self):
        self.assertEqual(synthesize([]),b'')
        with self.assertRaises(ValueError):synthesize(['INVALID'])
        with self.assertRaises(ValueError):synthesize(['AA'],rate=0)

    def test_inflection(self):
        statement=['HH','EH1','L','OW0','.']
        question=statement[:-1]+['?']
        falling=pitch_plan(statement); rising=pitch_plan(question)
        self.assertGreater(rising[-2][-1],falling[-2][-1]+6)
        self.assertLess(falling[-2][-1],falling[0][0])
        for i in range(3):self.assertAlmostEqual(falling[i][-1],falling[i+1][0])
        flat=synthesize(statement,Voice(expression=0))
        self.assertEqual(flat,synthesize(question,Voice(expression=0)))
        self.assertNotEqual(flat,synthesize(statement))
        self.assertEqual(len(flat),len(synthesize(statement)))
        with self.assertRaises(ValueError):synthesize(statement,Voice(expression=3))

    def test_exclamation(self):
        plain,_=self.en.convert('Hello Brandon.')
        emphatic,_=self.en.convert('Hello Brandon!')
        self.assertEqual(emphatic[-1],'!')
        a=pitch_plan(plain);b=pitch_plan(emphatic)
        self.assertGreater(max(x for phone in b for x in phone),max(x for phone in a for x in phone)+1)
        self.assertNotEqual(synthesize(plain),synthesize(emphatic))
        self.assertEqual(synthesize(plain,Voice(expression=0)),synthesize(emphatic,Voice(expression=0)))

    def test_voice_presets(self):
        self.assertEqual(configured_voice('derik'),Voice())
        for identity in VOICES:
            for pitch in (0,50,100):
                for inflection in (0,100):
                    pcm=synthesize(['S','IY1','.'],configured_voice(identity,pitch,inflection))
                    a=array.array('h',pcm)
                    self.assertGreater(max(map(abs,a)),100)
                    self.assertLess(max(map(abs,a)),32767)

    def test_character_controls(self):
        phones=['M','AE1','N','S']
        for identity in VOICES:
            baseline=synthesize(phones,configured_voice(identity))
            for setting in ('roughness','breathiness','headSize','vocalTract','gender'):
                changed=synthesize(phones,configured_voice(identity,**{setting:100}))
                self.assertNotEqual(changed,baseline,(identity,setting))
            for extreme in (0,100):
                v=configured_voice(identity,roughness=extreme,breathiness=extreme,headSize=extreme,vocalTract=extreme,gender=extreme)
                pcm=synthesize(phones,v,rate=5)
                self.assertTrue(pcm)
                self.assertLess(max(map(abs,array.array('h',pcm))),32767)

    def test_consonant_identity_and_stop_closure(self):
        # Distinct consonants even when pitch and vocal-tract size are identical.
        outputs=[synthesize(['S','T','IY1'],replace(v,pitch=112,tract_scale=1.0)) for v in VOICES.values()]
        self.assertEqual(len(set(outputs)),len(VOICES))
        for v in VOICES.values():
            t=array.array('h',synthesize(['T'],v))
            d=array.array('h',synthesize(['D'],v))
            closure=max(1,int(len(t)*.30))
            self.assertEqual(max(map(abs,t[:closure])),0)
            self.assertGreater(max(map(abs,d[:closure])),10)
            self.assertNotEqual(t,d)

    def test_streaming(self):
        phones,_=self.en.convert('Many men know my name. '*8)
        chunks=[]
        self.assertEqual(synthesize(phones,on_audio=chunks.append),b'')
        self.assertGreater(len(chunks),20)
        self.assertEqual(b''.join(chunks),synthesize(phones))
        self.assertLess(len(chunks[0]),SR)
        stopped=[]
        synthesize(phones,on_audio=stopped.append,cancelled=lambda:bool(stopped))
        self.assertEqual(len(stopped),1)

    def test_nasals(self):
        m=synthesize(['M']);n=synthesize(['N'])
        self.assertNotEqual(m,n)
        for pcm in (m,n):
            a=array.array('h',pcm)
            self.assertGreater(max(map(abs,a)),100)

    def test_output_headroom(self):
        import engine
        values=[-.8,-.4,0,.4,.8]
        result=array.array('h',engine.encode(values))
        self.assertLess(abs(result[4]-2*result[3]),2)
        phones,_=self.en.convert('Many men know my name. The quick brown fox jumps over the lazy dog.')
        for voice in VOICES.values():
            a=array.array('h',synthesize(phones,voice))
            self.assertLess(max(map(abs,a)),int(.94*32767))

    def test_voice_names(self):
        self.assertEqual(self.en.pronounce('Roxanne'),['R','AA0','K','S','AE1','N'])
        self.assertEqual(self.en.pronounce('Josie'),['JH','OW1','Z','IY0'])
        for identity in ('female1','female2'):
            j=array.array('h',synthesize(['JH'],VOICES[identity]))
            zh=array.array('h',synthesize(['ZH'],VOICES[identity]))
            self.assertLess(sum(x*x for x in j[:400]),sum(x*x for x in zh[:400]))

if __name__=='__main__':unittest.main()
