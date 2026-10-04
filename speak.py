"""Run: python speak.py "Hello Brandon" -o hello.wav"""
import argparse
import json
from pathlib import Path
from english import English
from engine import Voice, synthesize, save

def main():
    p=argparse.ArgumentParser(description='VDSoft2000 US male formant prototype')
    p.add_argument('text');p.add_argument('-o','--output',type=Path,default=Path('speech.wav'))
    p.add_argument('--pitch',type=float,default=112);p.add_argument('--rate',type=float,default=1)
    p.add_argument('--inflection',type=float,default=1,help='0 = flat, 1 = Derik default, 2 = exaggerated')
    args=p.parse_args()
    phones,unknown=English().convert(args.text)
    save(args.output,synthesize(phones,Voice(pitch=args.pitch,expression=args.inflection),args.rate))
    args.output.with_suffix('.json').write_text(json.dumps({'text':args.text,'phones':phones,'guessed_words':unknown},indent=2),encoding='utf-8')
    print(args.output.resolve())
    if unknown:print('Guessed pronunciations:',', '.join(unknown))

if __name__=='__main__': main()
