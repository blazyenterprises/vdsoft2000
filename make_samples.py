import array
import json
import math
import time
from pathlib import Path
from english import English
from engine import synthesize,save,SR

r=Path(__file__).parent
en=English()
examples={
 '01-us-male-introduction':'Hello Brandon. This is V D soft 2000. I am the first American male voice. Welcome to the new speech system.',
 '02-numbers':'Zero, one, two, three, four, five, six, seven, eight, nine, ten. Twenty three. One hundred and five. Two thousand.',
 '03-articulation':'Please check the sound. The red car is parked outside. She sells sea shells. Think about three things. Can you hear me clearly?',
}
report=[]
for name,text in examples.items():
    phones,unknown=en.convert(text)
    assert not unknown,unknown
    start=time.perf_counter();pcm=synthesize(phones);t=time.perf_counter()-start
    save(r/'samples'/f'{name}.wav',pcm)
    a=array.array('h',pcm)
    report.append(dict(file=name+'.wav',text=text,phones=phones,seconds=len(a)/SR,render_seconds=t,
                       peak=max(map(abs,a)),rms=math.sqrt(sum(x*x for x in a)/len(a))))
(r/'samples/report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps([{k:v for k,v in x.items() if k!='phones'} for x in report],indent=2))
