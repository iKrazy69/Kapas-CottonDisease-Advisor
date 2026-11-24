import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'backend'))
from answer_cleanup import collapse_repeats

fails = []
def check(name, cond, extra=''):
    print(('PASS ' if cond else 'FAIL ') + name)
    if not cond:
        fails.append(name)
        if extra != '': print('   ', extra)

runaway = open(os.path.join(HERE, 'fixtures', 'q22_runaway_answer.txt'), encoding='utf-8').read()
fixed = collapse_repeats(runaway)
sents = [s.strip() for s in fixed.replace('\n', ' ').split('. ') if s.strip()]
check('the 676-word looping answer shrinks to a short one', len(fixed.split()) < 150, len(fixed.split()))
check('its first sentence and its dose are kept', fixed.startswith('To drench the roots with Carbendazim') and '10 g/10 L' in fixed)
check('no sentence is left twice', len(sents) == len(set(sents)), sents)
check('it ends on a full sentence, not mid-word', fixed.rstrip().endswith(('.', ')')), fixed[-60:])
check('running it again changes nothing', collapse_repeats(fixed) == fixed)

normal = ('Spray Imidacloprid 17.8 SL @ 0.5 ml per litre of water (Source 1).\n\n'
          'Repeat after 15 days if the pest count stays above the threshold (Source 2).\n\n'
          'Do not spray during flowering when bees are active (Source 1).')
check('a normal answer comes back unchanged', collapse_repeats(normal) == normal)
bullets = 'Bacterial leaf blight spreads through:\n\n* Rain splash\n* Irrigation water\n* Farm operations\n* Windy rain\n* Overhead splash irrigation\n* Field labourers brushing against wet plants\n* Through natural openings like stomata or hydathodes' * 1
check('a bullet list without full stops is left alone', collapse_repeats(bullets) == bullets)
hindi = 'कार्बेन्डाज़िम 50% WP को 10 ग्राम प्रति 10 लीटर पानी में मिलाकर जड़ों के पास डालें (स्रोत 1)। ' * 1 + 'सफेद मक्खी के लिए पीले चिपचिपे जाल प्रति एकड़ 8 से 10 लगाएँ और हर सप्ताह जाँचें (स्रोत 2)। ' + 'रोग फैलने पर पौधों के आसपास की मिट्टी को भी उपचारित करें (स्रोत 3)।'
check('a Hindi answer with different sentences is left alone', collapse_repeats(hindi) == hindi)
looped_hi = hindi + ' ' + hindi
out_hi = collapse_repeats(looped_hi)
check('a Hindi answer repeated twice is cut back to one copy', out_hi.count('कार्बेन्डाज़िम') == 1 and 'सफेद मक्खी' in out_hi, out_hi)
check('short and empty text pass through', collapse_repeats('') == '' and collapse_repeats(None) is None and collapse_repeats('Yes.') == 'Yes.')
short_rep = 'Spray now. Spray now.'
check('very short text is not touched', collapse_repeats(short_rep) == short_rep)

print('\nFAILED:', fails if fails else 'none')
sys.exit(1 if fails else 0)
