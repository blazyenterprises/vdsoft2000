VDSoft2000 0.6.0 - Derik public testing build

Install the .nvda-addon package, restart NVDA, and select VDSoft2000 in
NVDA Settings > Speech > Change. Choose Derik, Jeff, Roxanne, or Josie. All are U.S. English.

Rate, pitch and inflection are available in Speech settings and NVDA's
synth settings ring. All default to 50. Rate 50 is now 1.45 times the original sample speed;
rate 30 matches the old rate 50. Pitch and inflection retain their defaults.
Inflection 0 gives flat pitch; 100 doubles the default pitch movement.
Rate ranges from 0.4 to 2.5 times normal. Pitch changes the source pitch,
not vocal-tract size. NVDA manages saving these standard settings.

Audio uses nvwave and the output device selected in NVDA's Audio settings.
Supports cancellation, pause/resume, queued speech, index notifications,
character spelling, breaks, and embedded pitch/rate commands.
No external engine, Python installation, downloads, or accounts required.

This is experimental English-only software for testing. Arabic is not implemented. Unknown English words are pronounced using spelling rules. Guesses for
names and invented words may need tuning; explicit character reading still spells.
Non-ASCII characters are described by Unicode names, not pronounced in
their language. Pronunciation and symbol handling are still limited.
Long text is synthesized in bounded chunks, with possible prosody resets.

Validation: real engine and driver tests in a simulated NVDA host, including
queueing, controls, device selection, cancellation and pause/resume.
Live NVDA integration still requires tester verification. The manifest
declares compatibility through NVDA 2026.1; this is not a claim that every
NVDA release was tested. Keep another synthesizer available while testing.

CMUdict and its license are included under synthDrivers/vdsoft2000/data.
This package contains original VDSoft2000 synthesis code and dictionary
data; it contains no DECtalk, MBROLA, Flite or recorded voice engine.
No automatic updater is included.

0.6.0: Voice-specific consonant spectra, strength, timing, vowel transitions
and resonance offsets. Reworked stop closure, release and aspiration to
distinguish unvoiced P/T/K from voiced B/D/G. Listening evaluation needed.

0.6.0: Audio is delivered progressively during synthesis instead of waiting
for a complete text chunk. Fixed gain and soft limiting replace whole-chunk
peak normalization. M and N now have stronger nasal murmur and different
resonance notches. Long-input prosody still uses bounded text chunks.

0.6.0: Explicit Roxanne and Josie pronunciations; strengthened affricate
release for English J and CH to distinguish them from continuous fricatives.

0.6.0: Recalibrated rate scale: old rate 50 is now 30; new rate 50 is
45 percent faster. The 0 and 100 endpoints remain 0.4 and 2.5 times normal.

0.6.0: Rate Boost doubles the selected speech rate for all voices, up to
5 times original speed. Off by default. Pitch is unchanged. NVDA saves
the checkbox with the other synthesizer settings.

0.6.0: Removed excessive streaming gain and continuous soft saturation.
Conservative linear output restores waveform dynamics. Streaming and
the nasal articulation changes remain enabled.

0.6.0: Volume control, default 50, calibrated per voice against average
0.3.0 speech level. Zero mutes; higher values increase gain subject to peak
headroom. Whole audio blocks are reduced linearly when needed to prevent
clipping. Matching is approximate because 0.3.0 normalized each utterance.

0.6.0: Five additional sliders, available in Speech settings and the synth
settings ring, saved by NVDA. Values are 0-100 and apply to all voices:
- Roughness: 0 (default) smooth; higher adds pitch/voicing irregularity.
- Breathiness: 0 removes added breath noise; 50 preserves the preset;
  higher adds airflow noise.
- Head size: lower = smaller/brighter resonances; higher = larger/deeper.
  This does not directly change pitch.
- Vocal tract: changes relative vowel resonances rather than overall size;
  50 preserves the preset. This is a timbre-shaping control, not anatomy.
- Gender: lower shifts toward a masculine voice character, higher toward
  feminine, by adjusting source pitch, closure and upper resonances.
  50 preserves each voice's identity. It is not a language setting.
Head size, vocal tract and gender default to 50. Setting every new slider
to its default restores the prior voice settings. Existing rate, boost,
pitch, inflection and volume controls remain available. Extreme combinations
are experimental and can reduce intelligibility; output peak protection stays on.

0.6.0: Stronger K/G releases with vowel-dependent velar resonances.
Breathiness above 50 adds substantially stronger filtered airflow noise;
50 retains subtle preset breath, and 0 removes it. Test 80-100 to hear it.

0.6.0: Exclamation marks retain their own phrase ending, with raised pitch,
stronger stress accents and an emphatic falling finish. Inflection controls
the effect; zero keeps pitch flat. Volume is not increased.

0.6.0: Added Child (higher pitch and smaller resonances), Alien (unusual
resonances and modulated voicing), and Robot (rigid timing, stepped subtle
intonation and buzzy source). All speak US English and support all controls.
Child remains descriptively labeled until named. Existing voice IDs retained.

0.6.0: Ignore invisible Unicode format controls (including directional
isolates, direction marks, zero-width joiners and byte-order marks) and
variation selectors before speaking or spelling. Visible text is retained.

0.6.0: Added Old Man and Old Lady, with individual resonance, breath,
articulation and subtle vocal tremor. These are stylized voice characters.
Both support the existing controls and remain descriptively named.
