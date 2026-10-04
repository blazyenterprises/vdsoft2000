"""US English dictionary frontend with a rule-based unknown-word fallback."""
from pathlib import Path
import re

UNITS = 'zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split()
TENS = 'zero ten twenty thirty forty fifty sixty seventy eighty ninety'.split()
LETTERS = ['EY1','B IY1','S IY1','D IY1','IY1','EH1 F','JH IY1','EY1 CH','AY1','JH EY1','K EY1','EH1 L','EH1 M','EH1 N','OW1','P IY1','K Y UW1','AA1 R','EH1 S','T IY1','Y UW1','V IY1','D AH1 B AH0 L Y UW0','EH1 K S','W AY1','Z IY1']

def guess_pronunciation(word):
    """Conservative spelling rules, not a claim of correct pronunciation for names."""
    word=word.lower().replace("'",'')
    groups={'tion':'SH AH0 N','sion':'ZH AH0 N','tch':'CH','dge':'JH',
        'sh':'SH','ch':'CH','th':'TH','ph':'F','ng':'NG','ck':'K','qu':'K W',
        'ee':'IY','ea':'IY','oo':'UW','ai':'EY','ay':'EY','oi':'OY','oy':'OY',
        'ou':'AW','ow':'AW','au':'AO','aw':'AO','oa':'OW','ie':'IY',
        'ar':'AA R','or':'AO R','er':'ER','ir':'ER','ur':'ER'}
    consonants=dict(zip('bdfhjklmnpqrtvwxz',
        ['B','D','F','HH','JH','K','L','M','N','P','K','R','T','V','W','K S','Z']))
    short={'a':'AE','e':'EH','i':'IH','o':'AA','u':'AH'}
    long={'a':'EY','e':'IY','i':'AY','o':'OW','u':'Y UW'}
    phones=[];i=0
    while i<len(word):
        c=word[i];tail=word[i:];nxt=word[i+1:i+2]
        if i==0 and word[:2] in ('kn','gn','wr'):i+=1;continue
        if tail=='e' and i>1 and any(p in short.values() or p in ('EY','IY','AY','OW','UW','ER') for p in phones):break
        # Consonant + le ending: table-like syllable, rather than silent e.
        if tail=='le' and i and word[i-1] not in 'aeiou':phones.extend(['AH0','L']);break
        match=next((g for g in sorted(groups,key=len,reverse=True) if tail.startswith(g)),None)
        if match:phones.extend(groups[match].split());i+=len(match);continue
        if c in short:
            silent_e=(i+2==len(word)-1 and word[-1]=='e' and nxt not in 'aeiouwxy')
            phones.extend((long[c] if silent_e else short[c]).split())
        elif c=='c':phones.append('S' if nxt and nxt in 'eiy' else 'K')
        elif c=='g':phones.append('JH' if nxt and nxt in 'eiy' else 'G')
        elif c=='s':phones.append('Z' if i and nxt and word[i-1] in 'aeiou' and nxt in 'aeiou' else 'S')
        elif c=='y':phones.append('Y' if i==0 else 'IY' if i==len(word)-1 and len(word)>3 else 'IH')
        elif c in consonants:phones.extend(consonants[c].split())
        i+=1
        if c not in 'aeiou' and i<len(word) and word[i]==c:i+=1
    vowels={'AA','AE','AH','AO','AW','AY','EH','ER','EY','IH','IY','OW','OY','UH','UW'}
    stressed=False
    for i,p in enumerate(phones):
        if p in vowels:
            phones[i]=p+('0' if stressed else '1');stressed=True
    return phones

def cardinal(n):
    if n < 20: return UNITS[n]
    if n < 100: return TENS[n//10] + (' '+UNITS[n%10] if n%10 else '')
    for value, name in [(10**9,'billion'),(10**6,'million'),(1000,'thousand'),(100,'hundred')]:
        if n >= value: return cardinal(n//value)+' '+name+(' '+cardinal(n%value) if n%value else '')

def number(token):
    sign = 'minus ' if token.startswith('-') else 'plus ' if token.startswith('+') else ''
    parts = token.lstrip('+-').split('.')
    digits = parts[0]
    words = ' '.join(UNITS[int(c)] for c in digits) if len(digits)>9 or (len(digits)>1 and digits[0]=='0') else cardinal(int(digits))
    return sign+words+(' point '+' '.join(UNITS[int(c)] for c in parts[1]) if len(parts)>1 else '')

class English:
    def __init__(self):
        self.lexicon = {}
        for line in (Path(__file__).parent/'data/cmudict.txt').read_text(encoding='utf-8').splitlines():
            if not line or line.startswith(';;;'): continue
            word, *phones = line.split()
            self.lexicon.setdefault(re.sub(r'\(\d+\)$','',word.lower()), phones)
        self.lexicon.update({
            'vdsoft':'V IY1 D IY1 S AO1 F T'.split(),
            'roxanne':'R AA0 K S AE1 N'.split(),
            'josie':'JH OW1 Z IY0'.split(),
        })
        # Established alternate spelling: preserve the dictionary's usable pronunciation.
        self.lexicon['useable']=self.lexicon.get('usable','Y UW1 Z AH0 B AH0 L'.split())

    def pronounce(self,word):
        word=word.lower()
        if word in self.lexicon:return self.lexicon[word]
        # Regular suffixes retain known stems, including consonant voicing.
        for suffix in ("'s",'s','ed','ing'):
            if not word.endswith(suffix):continue
            stem=word[:-len(suffix)]
            candidates=[stem]
            if suffix in ('ed','ing'):
                candidates.append(stem+'e')
                if len(stem)>2 and stem[-1]==stem[-2]:candidates.append(stem[:-1])
            root=next((self.lexicon[x] for x in candidates if x in self.lexicon),None)
            if root:
                last=re.sub('[012]','',root[-1])
                if suffix in ('s',"'s"):
                    extra=['IH0','Z'] if last in ('S','Z','SH','ZH','CH','JH') else ['S'] if last in ('P','T','K','F','TH') else ['Z']
                elif suffix=='ed':extra=['IH0','D'] if last in ('T','D') else ['T'] if last in ('P','K','F','TH','S','SH','CH') else ['D']
                else:extra=['IH0','NG']
                return root+extra
        return guess_pronunciation(word)

    def convert(self, text):
        if any(c.isalpha() and not c.isascii() for c in text):
            raise ValueError('This first prototype supports English only; Arabic is not implemented yet.')
        text = text.replace('\u2019', "'")
        text = re.sub(r'[+-]?\d+(?:\.\d+)?',lambda m:number(m[0]),text)
        result, unknown = [], []
        for token in re.findall(r"[a-zA-Z]+(?:'[a-zA-Z]+)*|[.,;:!?\n]",text):
            if token[0].isalpha():
                phones = self.lexicon.get(token.lower())
                if phones is None:
                    unknown.append(token)
                    phones = self.pronounce(token)
                result.extend(phones)
                result.append('|')
            else: result.append(token if token in '?!' else '.' if token in '.\n' else ',')
        return result, unknown
