/* Kapas site script.
   The advisor part (photo check, chat, reliability panel) keeps the same safe rendering as the earlier page:
   text that comes from the server is only ever put in with textContent, never innerHTML.
   innerHTML below is used only for fixed drawings and icons written in this file. */
(function(){
'use strict';

const API = location.protocol === 'file:' ? 'http://127.0.0.1:8080' : '';
const $ = id => document.getElementById(id);
const K = window.KAPAS || {GROUPS:[], DISEASES:[], STAGES:[], ZONES:{}, HISTORY:[], art:() => '', PHOTO:{}};
const NAMES = {en:'English', hi:'हिन्दी', mr:'मराठी', gu:'ગુજરાતી', te:'తెలుగు', kn:'ಕನ್ನಡ', ta:'தமிழ்', bn:'বাংলা', pa:'ਪੰਜਾਬੀ', ml:'മലയാളം'};
const LS = {get(k){try{return localStorage.getItem(k)}catch(e){return null}}, set(k,v){try{localStorage.setItem(k,v)}catch(e){}}};
const reduced = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
const sideBySide = () => matchMedia('(min-width: 961px)').matches;

/* ---------- Words for the advisor (English and Hindi) ---------- */
const I18N = {
en:{
  h1:'Check a cotton leaf',
  lede:'Add a clear photo of one leaf. Kapas suggests what it may be, then answers your questions only from the guides loaded on this computer.',
  frameEmpty:'Drop a leaf photo here', frameSub:'or use the buttons below', photoAlt:'Selected leaf photo',
  camera:'Take a photo', file:'Choose from files', check:'Check this leaf', checking:'Checking the leaf…',
  tip:'One leaf, flat on a plain light background, in daylight, no flash. Fill the frame and keep it sharp.',
  speakLabel:'Read answers aloud', speakOff:'Spoken answers are available in English and Hindi only.',
  stReady:'Photo check ready', stNoModel:'Photo check not set up', stDocs:'Guides loaded', stNoDocs:'No guides loaded', stDown:'Server not reachable',
  howTitle:'How it works',
  how1t:'Add a photo', how1d:'One leaf, in daylight.',
  how2t:'Read the result', how2d:'Kapas shows its closest guesses and says plainly when it is not sure.',
  how3t:'Ask follow-ups', how3d:'Answers come only from the loaded guides, with the source named.',
  vMatch:'Possible match', vHealthy:'Looks healthy', vUnsure:'Not sure',
  unsureTitle:'Not sure about this leaf', healthyTitle:'No disease spotted',
  gaugeLabel:'model score', gaugeMin:'{min}% needed',
  gaugeNote:'The model needs at least {min}% to call a match. The score shows how strongly it leans, not the chance that it is right.',
  guesses:'Closest guesses', testScore:'Test score for this disease',
  testScoreNote:'Measured on photos the model had not seen. 1.00 would be perfect.',
  whyNot:'Why Kapas is not sure',
  rLow:'The top guess scored {p}%. It needs at least {min}% to count as a match.',
  rClass:'In testing, the model was not reliable on “{d}”, its top guess.',
  rNone:'The model has no test record for “{d}”.',
  guides:'What the guides say', nextTitle:'What to do next',
  noPassage:'No matching passage in the loaded guides', sources:'Sources',
  english:'Show English version', transFail:'Translation did not work, so this answer is in English.',
  adviceLang:'This advice is in {a}. Check the leaf again to get it in {b}.',
  ask:'Ask a follow-up', askPh:'Type your question', send:'Ask', thinking:'Looking through the guides',
  chatTitle:'Ask the guide', chatLead:'Ask about cotton pests and diseases. Answers come only from the loaded guide, with the source named.',
  micStart:'Ask by voice', micStop:'Stop recording', micWorking:'Listening to your question',
  errMic:'The microphone could not be used. Allow microphone access in your browser, or type your question.',
  learn:'Read about {d} below',
  s1:'What are the signs of {d}?', s2:'How does {d} spread?', s3:'How can I manage {d}?', s4:'Which spray is recommended for {d}?',
  g1:'Which diseases are common in cotton?', g2:'How do I check my field for pests?', g3:'What does a healthy cotton leaf look like?', g4:'When should I call an agriculture officer?',
  webLabel:'From the internet, not your loaded guides', webSrc:'Web pages used',
  webCheck:'Web pages can be wrong or out of date. Check with your KVK before spraying anything.',
  webNone:'I also searched the internet but found nothing reliable.', webOffline:'I could not reach the internet to look further.',
  webError:'The internet search did not work this time.', usedDx:'Answered with your leaf result in mind: {d}', understood:'Understood as: {q}',
  webOn:'Internet lookup on', webOff:'Internet lookup off',
  reliTitle:'What Kapas can and cannot recognise',
  reliLead:'Test score for each disease (1.00 is perfect). The gold mark is the minimum, {f1}, a disease needs before it can be shown as a match. Diseases not listed here are not recognised at all.',
  reliBelow:'Never shown as a match',
  reliAcc:'Overall test accuracy {a}%, average score across diseases {m}. The test set is small, so treat these as rough.',
  disclaimer:'Kapas is a research prototype from a university project. It suggests; it does not diagnose. Before spraying anything, check with your Krishi Vigyan Kendra (KVK) or agriculture officer.',
  errNet:'Could not reach the server. Check that the app is running, then try again.',
  errBig:'That photo is too large. Try a smaller one.',
  errImg:'That file could not be read as a photo. Try a JPG or PNG.',
  errServer:'Something went wrong on the server. Try again in a moment.',
  errNoModel:'The photo check is not set up yet. Train the model first.',
  errSession:'This chat has expired. Check the leaf again to start a new one.',
  errTrans:'Your question could not be translated. Try English, or try again.',
  srResult:'Result: {t}. Model score {p}%.'
},
hi:{
  h1:'कपास की पत्ती जाँचें',
  lede:'एक पत्ती की साफ़ फ़ोटो जोड़ें। कपास बताएगा कि यह क्या हो सकता है, और आपके सवालों के जवाब सिर्फ़ इस कंप्यूटर पर लोड किए गए दस्तावेज़ों से देगा।',
  frameEmpty:'यहाँ पत्ती की फ़ोटो छोड़ें', frameSub:'या नीचे के बटन इस्तेमाल करें', photoAlt:'चुनी गई पत्ती की फ़ोटो',
  camera:'फ़ोटो खींचें', file:'फ़ाइल से चुनें', check:'इस पत्ती को जाँचें', checking:'पत्ती की जाँच हो रही है…',
  tip:'एक पत्ती, सादी हल्की पृष्ठभूमि पर रखी हुई, दिन की रोशनी में, बिना फ़्लैश। पत्ती को पूरे फ़्रेम में रखें और फ़ोटो साफ़ लें।',
  speakLabel:'जवाब बोलकर सुनाएँ', speakOff:'बोलकर जवाब सिर्फ़ अंग्रेज़ी और हिन्दी में मिलता है।',
  stReady:'फ़ोटो जाँच तैयार', stNoModel:'फ़ोटो जाँच अभी तैयार नहीं', stDocs:'दस्तावेज़ लोड हैं', stNoDocs:'कोई दस्तावेज़ लोड नहीं', stDown:'सर्वर से संपर्क नहीं हो पा रहा',
  howTitle:'कैसे काम करता है',
  how1t:'फ़ोटो जोड़ें', how1d:'एक पत्ती, दिन की रोशनी में।',
  how2t:'नतीजा देखें', how2d:'कपास अपने सबसे नज़दीकी अनुमान दिखाता है और पक्का न होने पर साफ़ कहता है।',
  how3t:'आगे पूछें', how3d:'जवाब सिर्फ़ लोड किए गए दस्तावेज़ों से आते हैं, स्रोत के नाम के साथ।',
  vMatch:'संभावित रोग', vHealthy:'पत्ती स्वस्थ दिखती है', vUnsure:'पक्का नहीं',
  unsureTitle:'इस पत्ती के बारे में पक्का नहीं', healthyTitle:'कोई रोग नहीं दिखा',
  gaugeLabel:'मॉडल स्कोर', gaugeMin:'{min}% ज़रूरी',
  gaugeNote:'अनुमान मानने के लिए मॉडल को कम से कम {min}% चाहिए। स्कोर बताता है कि मॉडल कितना झुका है, सही होने की संभावना नहीं।',
  guesses:'सबसे नज़दीकी अनुमान', testScore:'इस रोग के लिए जाँच-स्कोर',
  testScoreNote:'उन फ़ोटो पर मापा गया जो मॉडल ने पहले नहीं देखीं। 1.00 सबसे अच्छा होगा।',
  whyNot:'कपास को पक्का क्यों नहीं है',
  rLow:'सबसे ऊपर वाले अनुमान का स्कोर {p}% रहा। अनुमान मानने के लिए कम से कम {min}% चाहिए।',
  rClass:'जाँच में मॉडल अपने सबसे ऊपर वाले अनुमान “{d}” पर भरोसेमंद नहीं निकला।',
  rNone:'“{d}” के लिए मॉडल का कोई जाँच-रिकॉर्ड नहीं है।',
  guides:'दस्तावेज़ों में क्या लिखा है', nextTitle:'आगे क्या करें',
  noPassage:'लोड किए गए दस्तावेज़ों में कोई मेल खाता अंश नहीं मिला', sources:'स्रोत',
  english:'अंग्रेज़ी में देखें', transFail:'अनुवाद नहीं हो सका, इसलिए यह जवाब अंग्रेज़ी में है।',
  adviceLang:'यह सलाह {a} में है। {b} में पाने के लिए पत्ती फिर से जाँचें।',
  ask:'आगे का सवाल पूछें', askPh:'अपना सवाल लिखें', send:'पूछें', thinking:'दस्तावेज़ देखे जा रहे हैं',
  chatTitle:'गाइड से पूछें', chatLead:'कपास के कीटों और रोगों के बारे में पूछें। जवाब सिर्फ़ लोड किए गए दस्तावेज़ों से, स्रोत के नाम के साथ आते हैं।',
  micStart:'बोलकर पूछें', micStop:'रिकॉर्डिंग रोकें', micWorking:'आपका सवाल सुना जा रहा है',
  errMic:'माइक्रोफ़ोन इस्तेमाल नहीं हो सका। ब्राउज़र में माइक्रोफ़ोन की अनुमति दें, या सवाल लिखें।',
  learn:'{d} के बारे में नीचे पढ़ें',
  s1:'{d} के लक्षण क्या हैं?', s2:'{d} कैसे फैलता है?', s3:'{d} को कैसे संभालें?', s4:'{d} के लिए कौन सा छिड़काव सुझाया गया है?',
  g1:'कपास में कौन से रोग आम हैं?', g2:'मैं अपने खेत में कीट कैसे जाँचूँ?', g3:'कपास की स्वस्थ पत्ती कैसी दिखती है?', g4:'कृषि अधिकारी को कब बुलाना चाहिए?',
  webLabel:'इंटरनेट से, आपके लोड किए दस्तावेज़ों से नहीं', webSrc:'इस्तेमाल किए गए वेब पेज',
  webCheck:'वेब पेज ग़लत या पुराने हो सकते हैं। कुछ भी छिड़कने से पहले अपने KVK से पूछ लें।',
  webNone:'मैंने इंटरनेट पर भी खोजा, पर कोई भरोसेमंद जवाब नहीं मिला।', webOffline:'आगे खोजने के लिए इंटरनेट से संपर्क नहीं हो सका।',
  webError:'इस बार इंटरनेट खोज काम नहीं कर सकी।', usedDx:'आपकी पत्ती के नतीजे को ध्यान में रखकर जवाब: {d}', understood:'समझा गया सवाल: {q}',
  webOn:'इंटरनेट खोज चालू', webOff:'इंटरनेट खोज बंद',
  reliTitle:'कपास क्या पहचान सकता है और क्या नहीं',
  reliLead:'हर रोग का जाँच-स्कोर (1.00 सबसे अच्छा)। सुनहरा निशान न्यूनतम स्कोर {f1} है, जो किसी रोग को अनुमान की तरह दिखाने के लिए चाहिए। जो रोग यहाँ नहीं हैं, वे बिल्कुल नहीं पहचाने जाते।',
  reliBelow:'अनुमान की तरह कभी नहीं दिखता',
  reliAcc:'कुल जाँच-सटीकता {a}%, रोगों में औसत स्कोर {m}। जाँच-सेट छोटा है, इसलिए इन्हें मोटा अंदाज़ा समझें।',
  disclaimer:'कपास एक विश्वविद्यालय परियोजना का शोध प्रोटोटाइप है। यह सुझाव देता है, पक्का निदान नहीं करता। कोई भी दवा छिड़कने से पहले अपने कृषि विज्ञान केंद्र (KVK) या कृषि अधिकारी से पूछ लें।',
  errNet:'सर्वर से संपर्क नहीं हो सका। देखें कि ऐप चल रहा है, फिर दोबारा कोशिश करें।',
  errBig:'यह फ़ोटो बहुत बड़ी है। छोटी फ़ोटो चुनें।',
  errImg:'यह फ़ाइल फ़ोटो की तरह पढ़ी नहीं जा सकी। JPG या PNG चुनें।',
  errServer:'सर्वर पर कुछ गड़बड़ हुई। थोड़ी देर बाद फिर कोशिश करें।',
  errNoModel:'फ़ोटो जाँच अभी तैयार नहीं है। पहले मॉडल ट्रेन करें।',
  errSession:'यह बातचीत ख़त्म हो चुकी है। नई शुरुआत के लिए पत्ती फिर से जाँचें।',
  errTrans:'आपके सवाल का अनुवाद नहीं हो सका। अंग्रेज़ी में लिखें या फिर कोशिश करें।',
  srResult:'नतीजा: {t}। मॉडल स्कोर {p}%।'
}};

const S = {lang:'en', langs:['en','hi'], cfg:null, down:false, file:null, url:null, session:null, last:null, busy:false, chatBusy:false, asked:false};
const ui = () => I18N[S.lang] ? S.lang : 'en';
function t(k, v){
  let s = (I18N[ui()][k] !== undefined ? I18N[ui()][k] : I18N.en[k]);
  if(s === undefined) return k;
  if(v) for(const x in v) s = s.split('{' + x + '}').join(v[x]);
  return s;
}
const canSpeak = () => ((S.cfg && S.cfg.voice_languages) || ['en','hi']).indexOf(S.lang) >= 0;

function h(tag, props){
  const e = document.createElement(tag);
  if(props) for(const k in props){
    const v = props[k];
    if(v == null || v === false) continue;
    if(k === 'class') e.className = v;
    else if(k === 'text') e.textContent = v;
    else e.setAttribute(k, v === true ? '' : v);
  }
  for(let i = 2; i < arguments.length; i++){
    [].concat(arguments[i]).forEach(c => { if(c == null || c === false) return; e.append(c.nodeType ? c : document.createTextNode(String(c))); });
  }
  return e;
}

/* =====================================================================
   ADVISOR
   ===================================================================== */
function applyStatic(){
  $('advisor').lang = ui();
  document.querySelectorAll('#advisor [data-t]').forEach(n => n.textContent = t(n.dataset.t));
  document.querySelectorAll('#advisor [data-t-ph]').forEach(n => n.setAttribute('placeholder', t(n.dataset.tPh)));
  document.querySelectorAll('#advisor [data-t-aria]').forEach(n => n.setAttribute('aria-label', t(n.dataset.tAria)));
  document.querySelectorAll('#advisor [data-t-alt]').forEach(n => n.setAttribute('alt', t(n.dataset.tAlt)));
  $('go').textContent = S.busy ? t('checking') : t('check');
  setMicLabel();
}

function buildLang(){
  const box = $('langBox'); box.replaceChildren();
  if(S.langs.length <= 3){
    const seg = h('div', {class:'seg', role:'group', 'aria-label':'Language'});
    S.langs.forEach(c => seg.append(h('button', {type:'button', 'data-l':c, 'aria-pressed':String(c === S.lang), lang:c, text:NAMES[c] || c})));
    seg.addEventListener('click', e => { const b = e.target.closest('button[data-l]'); if(b) setLang(b.dataset.l); });
    box.append(seg);
  } else {
    const sel = h('select', {class:'sel', 'aria-label':'Language'});
    S.langs.forEach(c => sel.append(h('option', {value:c, text:NAMES[c] || c, selected:c === S.lang})));
    sel.addEventListener('change', () => setLang(sel.value));
    box.append(sel);
  }
}
function setLang(c){
  S.lang = c; LS.set('kapas.lang', c);
  buildLang(); applyStatic(); renderChips(); renderSpeak(); renderSugg(); renderReli();
  if(S.last) renderResult(false);
}

/* Theme */
function effDark(){
  const th = document.documentElement.dataset.theme;
  return th ? th === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches;
}
function syncTheme(){ $('themeBtn').setAttribute('aria-pressed', String(effDark())); }
$('themeBtn').addEventListener('click', () => {
  const next = effDark() ? 'light' : 'dark';
  document.documentElement.dataset.theme = next; LS.set('kapas.theme', next); syncTheme();
});

/* Status chips, speak switch */
function renderChips(){
  const ul = $('chips'); ul.replaceChildren();
  const add = (cls, k) => ul.append(h('li', {class:'chip ' + cls, text:t(k)}));
  if(S.down){ add('bad', 'stDown'); return; }
  const c = S.cfg; if(!c) return;
  add(c.classifier_loaded ? '' : 'warn', c.classifier_loaded ? 'stReady' : 'stNoModel');
  add(c.documents_loaded ? '' : 'warn', c.documents_loaded ? 'stDocs' : 'stNoDocs');
  if(typeof c.web_lookup === 'boolean') add(c.web_lookup ? '' : 'warn', c.web_lookup ? 'webOn' : 'webOff');
}
function renderSpeak(){
  const ok = canSpeak(), inp = $('speak');
  inp.disabled = !ok; if(!ok) inp.checked = false;
  $('speakRow').classList.toggle('off', !ok);
  $('speakTxt').textContent = ok ? t('speakLabel') : t('speakOff');
}
function refreshGo(){
  const blocked = S.cfg && !S.cfg.classifier_loaded;
  $('go').disabled = !S.file || S.busy || !!blocked;
  if(blocked && S.file) showErr(t('errNoModel'));
}
function showErr(m){ $('err').textContent = m || ''; }
function showChatErr(m){ $('chatErr').textContent = m || ''; }

/* Photo handling */
const frame = $('frame');
function setFile(f){
  if(!f) return;
  if(f.type && f.type.indexOf('image/') !== 0){ showErr(t('errImg')); return; }
  if(S.url) URL.revokeObjectURL(S.url);
  S.file = f; S.url = URL.createObjectURL(f);
  $('preview').src = S.url; frame.classList.add('has');
  S.last = null; S.session = null; S.asked = false;
  $('result').classList.add('hidden'); $('howMini').classList.remove('hidden');
  $('log').replaceChildren(); showErr(''); showChatErr(''); renderSugg(); refreshGo();
}
$('camBtn').addEventListener('click', () => $('inCam').click());
$('fileBtn').addEventListener('click', () => $('inFile').click());
['inCam','inFile'].forEach(id => $(id).addEventListener('change', e => { setFile(e.target.files[0]); e.target.value = ''; }));
['dragenter','dragover'].forEach(n => frame.addEventListener(n, e => { e.preventDefault(); frame.classList.add('drag'); }));
['dragleave','drop'].forEach(n => frame.addEventListener(n, e => { e.preventDefault(); frame.classList.remove('drag'); }));
frame.addEventListener('drop', e => { const f = e.dataTransfer && e.dataTransfer.files[0]; if(f) setFile(f); });

// Phone photos can be 5 to 12 MB; the server rejects files over 10 MB. Shrink big ones first.
async function prepare(file){
  try{
    const bmp = await createImageBitmap(file);
    const big = Math.max(bmp.width, bmp.height);
    if(big <= 1600 && file.size <= 4 * 1024 * 1024){ bmp.close && bmp.close(); return {blob:file, name:file.name || 'leaf.jpg'}; }
    const k = Math.min(1, 1600 / big);
    const c = document.createElement('canvas'); c.width = Math.round(bmp.width * k); c.height = Math.round(bmp.height * k);
    c.getContext('2d').drawImage(bmp, 0, 0, c.width, c.height); bmp.close && bmp.close();
    const b = await new Promise(r => c.toBlob(r, 'image/jpeg', 0.9));
    return b ? {blob:b, name:'leaf.jpg'} : {blob:file, name:file.name || 'leaf.jpg'};
  }catch(e){ return {blob:file, name:file.name || 'leaf.jpg'}; }
}

function errText(status, d){
  if(status === 0) return t('errNet');
  if(status === 413) return t('errBig');
  if(status === 503) return t('errNoModel');
  if(status === 404) return t('errSession');
  if(status === 502) return t('errTrans');
  if(status >= 500) return t('errServer');
  return (d && d.error) || t('errImg');
}

/* Diagnose */
function setBusy(b){
  S.busy = b;
  frame.classList.toggle('scanning', b); $('cap').classList.toggle('hidden', !b);
  frame.setAttribute('aria-busy', String(b));
  $('go').textContent = b ? t('checking') : t('check'); refreshGo();
}
async function check(){
  if(!S.file || S.busy) return;
  setBusy(true); showErr('');
  try{
    const p = await prepare(S.file);
    const fd = new FormData();
    fd.append('image', p.blob, p.name);
    fd.append('language', S.lang);
    fd.append('speak', ($('speak').checked && canSpeak()) ? '1' : '0');
    const r = await fetch(API + '/api/diagnose', {method:'POST', body:fd});
    let d = null; try{ d = await r.json(); }catch(e){}
    if(!r.ok || !d || !d.success){ showErr(errText(r.status, d)); return; }
    S.down = false; S.session = d.session_id; S.last = {d, lang:S.lang}; S.asked = false;
    $('log').replaceChildren();
    renderResult(true); renderSugg(); renderChips();
    if(!sideBySide()) $('result').scrollIntoView({behavior:reduced() ? 'auto' : 'smooth', block:'start'});
  }catch(e){ S.down = true; renderChips(); showErr(t('errNet')); }
  finally{ setBusy(false); }
}
$('go').addEventListener('click', check);

/* Safe rendering of advice text (no innerHTML for server text) */
const INL = /(\*\*[^*\n]+\*\*|[(\[]\s*(?:Sources?|स्रोत)\s*\d+(?:\s*[,&]\s*\d+)*\s*[)\]]|\[\s*\d+(?:\s*,\s*\d+)*\s*\])/i;
function inline(text, parent){
  text.split(INL).forEach(part => {
    if(!part) return;
    if(part.length > 4 && part.slice(0,2) === '**' && part.slice(-2) === '**') parent.append(h('strong', {text:part.slice(2,-2)}));
    else if(/^[(\[]/.test(part) && /(Source|स्रोत|^\[\s*\d)/i.test(part)) parent.append(h('span', {class:'ref', text:part.replace(/^[(\[]\s*|\s*[)\]]$/g, '')}));
    else parent.append(document.createTextNode(part));
  });
}
function fmtAdvice(text){
  const root = h('div', {class:'advice'});
  let list = null;
  String(text || '').replace(/\r/g, '').split('\n').forEach(raw => {
    const line = raw.trim();
    if(!line){ list = null; return; }
    const m = line.match(/^(?:[-*•–]|\d+[.)])\s+(.*)$/);
    if(m){
      if(!list){ list = h(/^\d/.test(line) ? 'ol' : 'ul', {class:'adv-list'}); root.append(list); }
      const li = h('li'); inline(m[1], li); list.append(li); return;
    }
    list = null;
    const hm = line.match(/^#{1,4}\s+(.*)$/);
    const p = h('p', hm ? {class:'adv-h'} : null); inline(hm ? hm[1] : line, p); root.append(p);
  });
  return root;
}
const pretty = n => String(n).replace(/\.(txt|pdf|md)$/i, '').replace(/[_-](txt|pdf)$/i, '').replace(/_+/g, ' ').trim();

const GLOBE = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9.5"/><path d="M2.5 12h19M12 2.5c2.6 2.7 3.9 5.9 3.9 9.5s-1.3 6.8-3.9 9.5c-2.6-2.7-3.9-5.9-3.9-9.5S9.4 5.2 12 2.5z"/></svg>';
const safeUrl = u => /^https?:\/\//i.test(u || '');

// Goes ABOVE the answer: says where it came from, and what it was understood as.
function answerHead(d, typed){
  const out = [];
  if(d.source_kind === 'web'){
    const l = h('div', {class:'weblabel'}); l.innerHTML = GLOBE; l.append(document.createTextNode(t('webLabel'))); out.push(l);
  }
  if(typed !== undefined){
    if(d.used_diagnosis && d.disease_context) out.push(h('p', {class:'ctx', text:t('usedDx', {d:d.disease_context})}));
    if(d.question_english && d.question_english.trim().toLowerCase() !== typed.trim().toLowerCase()) out.push(h('p', {class:'ctx', text:t('understood', {q:d.question_english})}));
  }
  return out;
}

// Everything that goes under an answer: refusal chip, sources, warnings, audio, English copy.
function answerExtras(d, english, showNoPassage){
  const out = [];
  if(showNoPassage && d.grounded === false && d.source_kind !== 'web') out.push(h('div', {class:'ungrounded', text:t('noPassage')}));
  if(d.source_kind === 'web' && d.web_sources && d.web_sources.length){
    out.push(h('h4', {class:'srcs-h', text:t('webSrc')}));
    out.push(h('ol', {class:'websrc'}, d.web_sources.filter(x => safeUrl(x.url)).map(x => {
      let host = ''; try{ host = new URL(x.url).hostname.replace(/^www\./, ''); }catch(e){}
      return h('li', null, h('a', {href:x.url, target:'_blank', rel:'noopener noreferrer', title:x.url, text:x.title || host}), h('small', {text:host}));
    })));
    out.push(h('div', {class:'note', text:t('webCheck')}));
  }
  if(d.source_kind !== 'web' && d.web_status && ['off_topic', 'ok', 'need_more', 'no_dose'].indexOf(d.web_status) < 0){
    const k = d.web_status === 'offline' ? 'webOffline' : (d.web_status === 'error' ? 'webError' : 'webNone');
    out.push(h('p', {class:'ctx', style:'margin-top:12px', text:t(k)}));
  }
  if(d.source_kind !== 'web' && d.source_documents && d.source_documents.length){
    out.push(h('h4', {class:'srcs-h', text:t('sources')}));
    out.push(h('ul', {class:'srcs'}, d.source_documents.map(n => h('li', {title:n, text:pretty(n)}))));
  }
  if(d.translation_failed) out.push(h('div', {class:'note', text:t('transFail')}));
  if(d.audio_url){
    const src = d.audio_url.charAt(0) === '/' ? API + d.audio_url : d.audio_url;
    out.push(h('audio', {controls:true, preload:'none', src}));
  }
  if(english && d.answer_language && d.answer_language !== 'en'){
    out.push(h('details', {class:'en'}, h('summary', {text:t('english')}), h('div', {text:english})));
  }
  return out;
}

/* Gauge */
function gaugeSvg(p, min){
  const R = 80, cx = 100, cy = 100, th = Math.PI * (1 - min);
  const pt = r => [(cx + r * Math.cos(th)).toFixed(1), (cy - r * Math.sin(th)).toFixed(1)];
  const a = pt(R - 14), b = pt(R + 14), lab = pt(R + 28);
  const arc = 'M20 100A80 80 0 0 1 180 100';
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '-14 -2 228 130'); svg.setAttribute('class', 'gauge'); svg.setAttribute('aria-hidden', 'true');
  // numbers only; no server text is placed in this markup
  svg.innerHTML =
    '<path class="g-track" d="' + arc + '" pathLength="100"/>' +
    '<path class="g-val" d="' + arc + '" pathLength="100" data-to="' + (100 - Math.round(p * 100)) + '"/>' +
    '<line class="g-tick" x1="' + a[0] + '" y1="' + a[1] + '" x2="' + b[0] + '" y2="' + b[1] + '"/>' +
    '<text class="g-min" x="' + lab[0] + '" y="' + (Number(lab[1]) + 3) + '"></text>' +
    '<text class="g-num" x="100" y="94">' + Math.round(p * 100) + '%</text>' +
    '<text class="g-lbl" x="100" y="118"></text>';
  svg.querySelector('.g-min').textContent = t('gaugeMin', {min:Math.round(min * 100)});
  svg.querySelector('.g-lbl').textContent = t('gaugeLabel');
  return svg;
}
const ICON = {
  ok:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9.5"/><path d="M7.5 12.5l3 3 6-6.5"/></svg>',
  unsure:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9.5"/><path d="M9.5 9.5a2.7 2.7 0 0 1 5.2.9c0 1.8-2.7 2.3-2.7 4"/><path d="M12 17.6v.1"/></svg>'
};

/* Result */
function renderResult(animate){
  const L = S.last, box = $('result');
  if(!L){ box.classList.add('hidden'); $('howMini').classList.remove('hidden'); return; }
  const d = L.d, dg = d.diagnosis, cfg = S.cfg || {};
  const min = typeof cfg.min_probability === 'number' ? cfg.min_probability : 0.7;
  const confident = dg.status === 'confident';
  const healthy = confident && /^healthy/i.test(dg.disease || '');
  const kind = !confident ? 'unsure' : (healthy ? 'healthy' : 'match');
  const top = (dg.top3 && dg.top3[0]) ? dg.top3[0].disease : (dg.disease || '');
  const title = kind === 'unsure' ? t('unsureTitle') : (kind === 'healthy' ? t('healthyTitle') : dg.disease);

  box.className = 'panel ' + (kind === 'unsure' ? 'unsure' : 'ok') + (animate ? ' enter' : '');
  box.replaceChildren();
  $('howMini').classList.add('hidden');

  const pill = h('span', {class:'verdict'}); pill.innerHTML = kind === 'unsure' ? ICON.unsure : ICON.ok;
  pill.append(document.createTextNode(t(kind === 'unsure' ? 'vUnsure' : (kind === 'healthy' ? 'vHealthy' : 'vMatch'))));
  const g = gaugeSvg(dg.probability, min);
  box.append(
    pill,
    h('div', {class:'res-head'}, h('h2', {class:'res-title', id:'resTitle', text:title}), g),
    h('p', {class:'fine', text:t('gaugeNote', {min:Math.round(min * 100)})})
  );
  const val = g.querySelector('.g-val');
  if(animate && !reduced()){ requestAnimationFrame(() => requestAnimationFrame(() => { val.style.strokeDashoffset = val.dataset.to; })); }
  else { val.style.transition = 'none'; val.style.strokeDashoffset = val.dataset.to; }

  const see = h('div', {class:'blk'}, h('h3', {text:t('guesses')}));
  const rows = h('ul', {class:'rows'});
  (dg.top3 || []).forEach((x, i) => {
    const pc = Math.round(x.probability * 100);
    const bar = h('div', {class:'bar', role:'img', 'aria-label':x.disease + ' ' + pc + '%'}, h('i'));
    bar.firstChild.style.setProperty('--w', pc + '%');
    rows.append(h('li', {class:'row' + (i === 0 ? ' lead' : '')}, h('span', {class:'nm', text:x.disease}), h('span', {class:'pc', text:pc + '%'}), bar));
  });
  see.append(rows);
  if(kind === 'match' && cfg.per_class_f1 && typeof cfg.per_class_f1[dg.disease] === 'number'){
    const f1 = cfg.per_class_f1[dg.disease];
    const bar = h('div', {class:'bar', role:'img', 'aria-label':t('testScore') + ' ' + f1.toFixed(2)}, h('i'));
    bar.firstChild.style.setProperty('--w', Math.round(f1 * 100) + '%');
    see.append(h('div', {style:'margin-top:24px'},
      h('ul', {class:'rows', style:'margin-top:0'}, h('li', {class:'row lead'}, h('span', {class:'nm', text:t('testScore')}), h('span', {class:'pc', text:f1.toFixed(2) + ' / 1.00'}), bar)),
      h('p', {class:'fine', style:'margin-top:8px', text:t('testScoreNote')})));
  }
  if(kind === 'unsure' && dg.reasons && dg.reasons.length){
    see.append(h('div', {style:'margin-top:22px'}, h('h3', {text:t('whyNot')}),
      h('ul', {class:'reasons'}, dg.reasons.map(r => {
        const k = /below/i.test(r) ? 'rLow' : (/unreliable/i.test(r) ? 'rClass' : 'rNone');
        return h('li', {text:t(k, {p:Math.round(dg.probability * 100), min:Math.round(min * 100), d:top})});
      }))));
  }
  if(dg.note) see.append(h('p', {class:'fine', text:dg.note}));
  box.append(see);

  const adv = h('div', {class:'blk'}, h('h3', {text:t(kind === 'match' ? (d.source_kind === 'web' ? 'webLabel' : 'guides') : 'nextTitle')}), fmtAdvice(d.advice));
  answerExtras(d, d.advice_english, kind === 'match').forEach(n => adv.append(n));
  if(L.lang !== S.lang) adv.append(h('div', {class:'note', text:t('adviceLang', {a:NAMES[L.lang] || L.lang, b:NAMES[S.lang] || S.lang})}));
  box.append(adv);

  // Link to the matching disease entry further down this page
  const did = kind === 'match' ? K.PHOTO[dg.disease] : null;
  if(did && document.getElementById('d-' + did)){
    const a = h('a', {class:'btn soft learn', href:'#d-' + did, text:t('learn', {d:dg.disease})});
    box.append(a);
  }
  $('sr').textContent = t('srResult', {t:title, p:Math.round(dg.probability * 100)});
}

/* Chat */
function renderSugg(){
  const box = $('sugg'); box.replaceChildren();
  if(S.asked) return;
  const dg = S.last && S.last.d.diagnosis;
  const dis = dg && dg.status === 'confident' && !/^healthy/i.test(dg.disease || '') ? dg.disease : null;
  (dis ? ['s1','s2','s3','s4'] : ['g1','g2','g3','g4']).forEach(k => box.append(h('button', {type:'button', text:t(k, {d:dis})})));
}
$('sugg').addEventListener('click', e => { const b = e.target.closest('button'); if(b) ask(b.textContent); });
$('composer').addEventListener('submit', e => { e.preventDefault(); const v = $('q').value; $('q').value = ''; ask(v); });

function scrollTo(el){ el.scrollIntoView({block:'nearest', behavior:reduced() ? 'auto' : 'smooth'}); }
function thinking(){
  const wait = h('div', {class:'bub a', role:'status', 'aria-label':t('thinking')}, h('span', {class:'dots'}, h('i'), h('i'), h('i')));
  $('log').append(wait); scrollTo(wait);
  return wait;
}
function setChatBusy(b){ S.chatBusy = b; $('send').disabled = b; $('mic').disabled = b && !Mic.on; }

async function ask(q){
  q = (q || '').trim();
  if(!q || S.chatBusy) return;
  setChatBusy(true); S.asked = true; renderSugg(); showChatErr('');
  $('log').append(h('div', {class:'bub q', text:q}));
  const wait = thinking();
  try{
    const body = {question:q, language:S.lang, speak:!!($('speak').checked && canSpeak())};
    if(S.session) body.session_id = S.session;
    const r = await fetch(API + '/api/chat', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
    let d = null; try{ d = await r.json(); }catch(e){}
    wait.replaceChildren(); wait.removeAttribute('role'); wait.removeAttribute('aria-label');
    if(!r.ok || !d || !d.success){
      if(r.status === 404) S.session = null;
      wait.className = 'bub a err'; wait.textContent = errText(r.status, d);
    } else {
      answerHead(d, q).forEach(n => wait.append(n));
      wait.append(fmtAdvice(d.response));
      answerExtras(d, d.response_english, true).forEach(n => wait.append(n));
    }
  }catch(e){
    wait.replaceChildren(); wait.className = 'bub a err'; wait.textContent = t('errNet');
  }finally{
    setChatBusy(false); scrollTo(wait);
  }
}

/* Voice question (browser records, /api/voice-query transcribes and answers) */
const Mic = {rec:null, chunks:[], stream:null, timer:null, on:false};
function setMicLabel(){
  const m = $('mic'); if(!m) return;
  const k = Mic.on ? 'micStop' : 'micStart';
  m.setAttribute('aria-label', t(k)); m.title = t(k);
}
function setMic(on){ Mic.on = on; $('mic').classList.toggle('rec', on); $('mic').setAttribute('aria-pressed', String(on)); setMicLabel(); }
async function micToggle(){
  if(Mic.on){ try{ Mic.rec.stop(); }catch(e){} return; }
  if(S.chatBusy) return;
  showChatErr('');
  if(!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia || !window.MediaRecorder){ showChatErr(t('errMic')); return; }
  try{ Mic.stream = await navigator.mediaDevices.getUserMedia({audio:true}); }
  catch(e){ showChatErr(t('errMic')); return; }
  const type = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg'].find(m => MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(m)) || '';
  Mic.rec = type ? new MediaRecorder(Mic.stream, {mimeType:type}) : new MediaRecorder(Mic.stream);
  Mic.chunks = [];
  Mic.rec.ondataavailable = e => { if(e.data && e.data.size) Mic.chunks.push(e.data); };
  Mic.rec.onstop = () => {
    clearTimeout(Mic.timer);
    Mic.stream.getTracks().forEach(tr => tr.stop());
    setMic(false);
    const blob = new Blob(Mic.chunks, {type:Mic.rec.mimeType || 'audio/webm'});
    if(blob.size > 1200) sendVoice(blob);
  };
  Mic.rec.start(); setMic(true);
  Mic.timer = setTimeout(() => { if(Mic.on) try{ Mic.rec.stop(); }catch(e){} }, 30000);
}
async function sendVoice(blob){
  if(S.chatBusy) return;
  setChatBusy(true); S.asked = true; renderSugg();
  const wait = thinking(); wait.setAttribute('aria-label', t('micWorking'));
  try{
    const ext = /mp4/.test(blob.type) ? 'm4a' : (/ogg/.test(blob.type) ? 'ogg' : 'webm');
    const fd = new FormData(); fd.append('audio', blob, 'voice.' + ext);
    const r = await fetch(API + '/api/voice-query', {method:'POST', body:fd});
    let d = null; try{ d = await r.json(); }catch(e){}
    wait.replaceChildren(); wait.removeAttribute('role'); wait.removeAttribute('aria-label');
    if(!r.ok || !d || !d.success){
      wait.className = 'bub a err'; wait.textContent = (d && d.error) || errText(r.status, d);
    } else {
      if(d.question) $('log').insertBefore(h('div', {class:'bub q', text:d.question}), wait);
      if(d.language && d.language !== 'en' && d.question_english) wait.append(h('p', {class:'ctx', text:t('understood', {q:d.question_english})}));
      wait.append(fmtAdvice(d.response));
      answerExtras(d, d.response_english, true).forEach(n => wait.append(n));
      const au = wait.querySelector('audio'); if(au){ try{ const p = au.play(); if(p && p.catch) p.catch(() => {}); }catch(e){} }
    }
  }catch(e){
    wait.replaceChildren(); wait.className = 'bub a err'; wait.textContent = t('errNet');
  }finally{
    setChatBusy(false); scrollTo(wait);
  }
}
$('mic').addEventListener('click', micToggle);

/* Reliability */
function renderReli(){
  const c = S.cfg, box = $('reli');
  if(!c || !c.per_class_f1){ box.classList.add('hidden'); return; }
  box.classList.remove('hidden');
  const min = typeof c.min_class_f1 === 'number' ? c.min_class_f1 : 0.3;
  const body = $('reliBody'); body.replaceChildren();
  body.append(h('p', {class:'fine', style:'margin-top:0', text:t('reliLead', {f1:min.toFixed(2)})}));
  const rows = h('ul', {class:'rows'});
  Object.entries(c.per_class_f1).sort((a, b) => b[1] - a[1]).forEach(([name, f1]) => {
    const low = f1 < min;
    const bar = h('div', {class:'bar', role:'img', 'aria-label':name + ' ' + f1.toFixed(2)}, h('i'));
    bar.firstChild.style.setProperty('--w', Math.max(2, Math.round(f1 * 100)) + '%'); bar.style.setProperty('--min', (min * 100) + '%');
    rows.append(h('li', {class:'row' + (low ? ' low' : '')}, h('span', {class:'nm', text:name}), h('span', {class:'pc', text:f1.toFixed(2)}), bar, low ? h('span', {class:'tag', text:t('reliBelow')}) : null));
  });
  body.append(rows);
  if(typeof c.test_accuracy === 'number' && typeof c.test_macro_f1 === 'number')
    body.append(h('p', {class:'fine', text:t('reliAcc', {a:Math.round(c.test_accuracy * 100), m:c.test_macro_f1.toFixed(2)})}));
}

/* =====================================================================
   SITE: header, reveal, season chart, history, diseases
   ===================================================================== */
const header = $('top');
const NAV = ['advisor', 'how', 'cotton', 'season', 'history', 'diseases'];
let menuOpen = false;
function setMenu(on){
  menuOpen = on; header.dataset.menu = String(on);
  $('menuBtn').setAttribute('aria-expanded', String(on));
  onScroll();
}
$('menuBtn').addEventListener('click', () => setMenu(!menuOpen));
document.addEventListener('keydown', e => { if(e.key === 'Escape' && menuOpen){ setMenu(false); $('menuBtn').focus(); } });
$('nav').addEventListener('click', e => { if(e.target.closest('a')) setMenu(false); });
matchMedia('(min-width: 901px)').addEventListener('change', e => { if(e.matches && menuOpen) setMenu(false); });

let ticking = false;
function onScroll(){
  if(ticking) return; ticking = true;
  requestAnimationFrame(() => {
    ticking = false;
    const y = window.scrollY, max = document.documentElement.scrollHeight - innerHeight;
    header.dataset.s = String(y > 40 || menuOpen);
    $('progress').style.setProperty('--p', max > 0 ? Math.min(1, y / max).toFixed(4) : 0);
    // which section are we in
    let cur = null;
    NAV.forEach(id => { const el = $(id); if(el && el.getBoundingClientRect().top <= innerHeight * 0.38) cur = id; });
    document.querySelectorAll('#nav a').forEach(a => a.setAttribute('aria-current', String(a.getAttribute('href') === '#' + cur)));
    updateTimeline();
  });
}
addEventListener('scroll', onScroll, {passive:true});
addEventListener('resize', () => { onScroll(); placeInd(); }, {passive:true});

/* Hero: the cotton plant. It grows and opens on load, sways in a light breeze,
   flutters when the pointer brushes it, and its bolls and flower can be touched. */
(function(){
  const art = $('heroArt'), hero = $('hero');
  const svg = art && art.querySelector('svg.plant');
  if(!svg) return;
  const NS = 'http://www.w3.org/2000/svg';
  const calm = reduced();
  const fine = matchMedia('(hover: hover) and (pointer: fine)').matches;
  const hint = $('plantHint'), hintTxt = $('plantHintTxt');
  if(hintTxt) hintTxt.textContent = fine ? 'Touch the cotton' : 'Tap the cotton';
  let touched = false;
  function used(){ if(touched) return; touched = true; if(hint) hint.classList.add('gone'); }
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

  /* ----- bolls: --o is how open a boll is (0 shut, 1 fully open); CSS does the drawing ----- */
  const backOut = t => { const c = 1.35, u = t - 1; return 1 + (c + 1) * u * u * u + c * u * u; };
  const bolls = Array.prototype.map.call(svg.querySelectorAll('.boll'), el => ({
    el, o:0, base:parseFloat(el.dataset.open) || 0, raf:0, timer:0,
    cx:+el.dataset.cx, cy:+el.dataset.cy, s:+el.dataset.s,
    lint:el.querySelector('.lint'), hit:el.querySelector('.hit')
  }));
  function setO(b, v){ b.o = v; b.el.style.setProperty('--o', v.toFixed(3)); }
  function tween(b, to, ms, delay, easing){
    cancelAnimationFrame(b.raf); clearTimeout(b.timer);
    if(calm){ setO(b, to); return; }
    const from = b.o, ease = easing || backOut;
    b.timer = setTimeout(() => {
      const t0 = performance.now();
      (function step(now){
        const k = clamp((now - t0) / ms, 0, 1);
        setO(b, from + (to - from) * ease(k));
        if(k < 1) b.raf = requestAnimationFrame(step); else setO(b, to);
      })(t0);
    }, (delay || 0) * 1000);
  }
  bolls.forEach(b => {
    const pop = b.el.closest('.pop');
    const d = pop ? (parseFloat(pop.style.getPropertyValue('--d')) || 0) : 0;
    if(b.base > 0) tween(b, b.base, 1700, d + .45);
  });

  /* ----- seeds of cotton that drift away ----- */
  const tufts = svg.querySelector('#tufts');
  let live = 0, gust = 0;
  function tuft(x, y, power){
    if(calm || !tufts || live > 26) return;
    const g = document.createElementNS(NS, 'g'), tf = document.createElementNS(NS, 'g');
    g.setAttribute('class', 'tuft'); g.setAttribute('transform', 'translate(' + x.toFixed(1) + ' ' + y.toFixed(1) + ')');
    tf.setAttribute('class', 'tf');
    const dur = 3.6 + Math.random() * 2.6;
    tf.style.setProperty('--dx', (((Math.random() * 1.3 - .25) * 150 + gust * 90) * power).toFixed(0) + 'px');
    tf.style.setProperty('--dy', (-(70 + Math.random() * 160) * power).toFixed(0) + 'px');
    tf.style.setProperty('--rt', ((Math.random() - .5) * 170).toFixed(0) + 'deg');
    tf.style.setProperty('--t', dur.toFixed(2) + 's');
    tf.innerHTML = '<circle r="5.2"/><circle cx="4.6" cy="-2.6" r="3.8"/><circle cx="-4.2" cy="-3" r="3.4"/><path d="M0 -5Q4 -14 10 -17M-3 -4Q-9 -11 -12 -12"/>';
    g.appendChild(tf); tufts.appendChild(g); live++;
    let gone = false;
    const rm = () => { if(gone) return; gone = true; g.remove(); live--; };
    tf.addEventListener('animationend', rm); setTimeout(rm, dur * 1000 + 800);
  }
  function burst(b, n, power){
    for(let i = 0; i < n; i++) setTimeout(() => tuft(b.cx + (Math.random() - .5) * 70 * b.s, b.cy + (Math.random() - .3) * 44 * b.s, power), i * 70);
  }
  function pulse(b){
    if(calm || !b.lint || !b.lint.animate) return;
    b.lint.animate([{transform:'scale(1)'}, {transform:'scale(1.09)', offset:.3}, {transform:'scale(.985)', offset:.65}, {transform:'scale(1)'}], {duration:900, easing:'ease-out'});
  }

  /* ----- touching ----- */
  const sway = [];
  bolls.forEach(b => {
    if(!b.hit) return;
    b.hit.addEventListener('pointerenter', e => {
      if(e.pointerType !== 'mouse') return;
      used();
      if(b.base < .99) tween(b, Math.min(1, b.base + .24), 520, 0, t => 1 - Math.pow(1 - t, 3));
      else { pulse(b); burst(b, 1, .6); }
    });
    b.hit.addEventListener('pointerleave', e => {
      if(e.pointerType !== 'mouse') return;
      if(b.base < .99) tween(b, b.base, 700, 0, t => 1 - Math.pow(1 - t, 3));
    });
    b.hit.addEventListener('click', () => {
      used();
      if(b.base < .99){ b.base = 1; tween(b, 1, 1500); setTimeout(() => { pulse(b); burst(b, 7, 1); }, calm ? 0 : 450); }
      else { pulse(b); burst(b, 6, 1); gust += .5; }
    });
  });
  const flower = svg.querySelector('.flower'), fhit = svg.querySelector('.fhit');
  if(flower && fhit) fhit.addEventListener('click', () => {
    used(); flower.classList.toggle('pink');
    const el = fhit.closest('.sw'); sway.forEach(e => { if(e.el === el) e.v += 4.5; });
  });

  /* ----- breeze: every swaying part follows a slow wave, plus gusts and brushes ----- */
  Array.prototype.forEach.call(svg.querySelectorAll('.sw'), el => sway.push({
    el, k:+el.dataset.k || 0, f:+el.dataset.f || 1, ph:+el.dataset.ph || 0, px:+el.dataset.px || 0, py:+el.dataset.py || 0,
    w:+el.dataset.w || 1, cx:+el.dataset.cx || 0, cy:+el.dataset.cy || 0, r:+el.dataset.r || 0, a:0, v:0, last:999
  }));
  let raf = 0, inView = true;
  const t0 = performance.now();
  function frame(now){
    raf = requestAnimationFrame(frame);
    const t = (now - t0) / 1000;
    gust *= .965;
    for(let i = 0; i < sway.length; i++){
      const e = sway[i];
      const target = e.k * (.8 * Math.sin(t * e.f + e.ph) + .2 * Math.sin(t * e.f * 2.3 + e.ph * 1.7)) + gust * e.k * e.w * 1.5;
      e.v = e.v * .88 + (target - e.a) * .07;
      e.a += e.v;
      if(Math.abs(e.a - e.last) > .004){
        e.el.setAttribute('transform', 'rotate(' + e.a.toFixed(3) + ' ' + e.px + ' ' + e.py + ')');
        e.last = e.a;
      }
    }
  }
  function start(){ if(!raf && !calm && inView && !document.hidden) raf = requestAnimationFrame(frame); }
  function stop(){ cancelAnimationFrame(raf); raf = 0; }
  if('IntersectionObserver' in window) new IntersectionObserver(es => { inView = es[0].isIntersecting; inView ? start() : stop(); }).observe(hero);
  document.addEventListener('visibilitychange', () => document.hidden ? stop() : start());
  start();

  /* a soft gust now and then, and a seed or two coming off the big boll */
  (function breeze(){
    setTimeout(() => {
      if(inView && !document.hidden){
        gust += (Math.random() < .5 ? -1 : 1) * (.7 + Math.random() * .5);
        const big = bolls.filter(b => b.o > .8);
        if(big.length) burst(big[Math.floor(Math.random() * big.length)], 2, .7);
      }
      breeze();
    }, 6500 + Math.random() * 5000);
  })();

  /* pointer: the plant leans a little, brushing leaves makes them flutter, a quick sweep makes a gust */
  let lx = 0, ly = 0, lt = 0;
  hero.addEventListener('pointermove', e => {
    if(e.pointerType !== 'mouse' && e.pointerType !== 'pen') return;
    const hr = hero.getBoundingClientRect();
    art.style.setProperty('--px', (((e.clientX - hr.left) / hr.width - .5) * 2).toFixed(3));
    art.style.setProperty('--py', (((e.clientY - hr.top) / hr.height - .5) * 2).toFixed(3));
    if(calm) return;
    const now = performance.now(), dt = Math.max(8, now - lt);
    const vx = (e.clientX - lx) / dt; lx = e.clientX; ly = e.clientY; lt = now;
    const r = svg.getBoundingClientRect();
    if(e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) return;
    const x = (e.clientX - r.left) / r.width * 520, y = (e.clientY - r.top) / r.height * 690;
    gust = clamp(gust + vx * .45, -1.6, 1.6);
    const push = clamp(vx * 1.4, -1.6, 1.6);
    for(let i = 0; i < sway.length; i++){
      const s = sway[i];
      if(s.r && Math.abs(x - s.cx) < s.r && Math.abs(y - s.cy) < s.r && Math.hypot(x - s.cx, y - s.cy) < s.r) s.v += push * s.k * .2;
    }
  });
  hero.addEventListener('pointerleave', () => { art.style.setProperty('--px', 0); art.style.setProperty('--py', 0); });
})();

/* Reveal on scroll */
const io = ('IntersectionObserver' in window) ? new IntersectionObserver(es => es.forEach(en => {
  if(en.isIntersecting){ en.target.classList.add('in'); io.unobserve(en.target); }
}), {threshold:0.18, rootMargin:'0px 0px -6% 0px'}) : null;
function reveal(el){ if(io) io.observe(el); else el.classList.add('in'); }
['flow', 'cotBars'].forEach(id => { const el = $(id); if(el) reveal(el); });
document.querySelectorAll('.outcome, .stat, .cot-cols > div, .species div').forEach((el, i) => { el.classList.add('rv'); el.style.setProperty('--d', i % 4); reveal(el); });
/* The cotton meters live inside .stat figures; reveal them with the figure */
document.querySelectorAll('.stat').forEach(el => reveal(el));

/* ---------- Season chart ---------- */
const LV = {L:['lv-L', 'Low'], N:['lv-L', 'Minor'], M:['lv-M', 'Moderate'], H:['lv-H', 'High'], J:['lv-H', 'Major']};
let zoneKey = 'north';
function buildZones(){
  const tabs = $('zoneTabs'); tabs.replaceChildren();
  tabs.append(h('span', {class:'zt-ind', id:'ztInd', 'aria-hidden':'true'}));
  Object.keys(K.ZONES).forEach(k => {
    tabs.append(h('button', {type:'button', role:'tab', id:'zt-' + k, 'data-z':k, 'aria-selected':String(k === zoneKey), 'aria-controls':'heat', tabindex:k === zoneKey ? '0' : '-1', text:K.ZONES[k].name}));
  });
  tabs.addEventListener('click', e => { const b = e.target.closest('button[data-z]'); if(b) setZone(b.dataset.z, true); });
  tabs.addEventListener('keydown', e => {
    const keys = Object.keys(K.ZONES), i = keys.indexOf(zoneKey);
    let n = null;
    if(e.key === 'ArrowRight') n = keys[(i + 1) % keys.length];
    if(e.key === 'ArrowLeft') n = keys[(i - 1 + keys.length) % keys.length];
    if(n){ e.preventDefault(); setZone(n, true); $('zt-' + n).focus(); }
  });
  renderZone();
  if(document.fonts && document.fonts.ready) document.fonts.ready.then(placeInd);
  requestAnimationFrame(placeInd);
}
function setZone(k, user){
  zoneKey = k;
  document.querySelectorAll('#zoneTabs button').forEach(b => { const on = b.dataset.z === k; b.setAttribute('aria-selected', String(on)); b.tabIndex = on ? 0 : -1; });
  placeInd(); renderZone();
}
function placeInd(){
  const ind = $('ztInd'), b = document.querySelector('#zoneTabs button[aria-selected="true"]');
  if(!ind || !b) return;
  ind.style.width = b.offsetWidth + 'px'; ind.style.transform = 'translateX(' + b.offsetLeft + 'px)';
}
function renderZone(){
  const z = K.ZONES[zoneKey];
  const info = $('zoneInfo'); info.replaceChildren();
  info.append(h('b', {text:z.name + ' zone: '}), document.createTextNode(z.states + '. Sown ' + z.sowing + ', ' + z.water + '.'));
  const tbl = $('heat'); tbl.replaceChildren();
  const hr = h('tr', null, h('th', {scope:'col', class:'sr-only', text:'Disease'}));
  K.STAGES.forEach(s => hr.append(h('th', {scope:'col'}, h('span', {class:'st-n', text:s.n}), h('span', {class:'st-d', text:s.d}))));
  tbl.append(h('thead', null, hr));
  const tb = h('tbody');
  z.rows.forEach((r, i) => {
    const has = r[1] && document.getElementById('d-' + r[1]);
    const th = h('th', {scope:'row'}, has ? h('a', {href:'#d-' + r[1], text:r[0]}) : h('span', {text:r[0]}));
    const tr = h('tr', {style:'--r:' + i}, th);
    r[2].forEach(v => {
      if(!v){ tr.append(h('td', {'aria-label':'Not listed'})); return; }
      tr.append(h('td', {class:LV[v][0]}, LV[v][1]));
    });
    tb.append(tr);
  });
  tbl.append(tb);
}

/* ---------- History ---------- */
function buildHistory(){
  const ol = $('tl'); ol.replaceChildren();
  K.HISTORY.forEach((e, i) => {
    const li = h('li', {class:'rv', style:'--d:0'}, h('div', {class:'tl-when', text:e.when}), h('div', {class:'tl-title', text:e.title}), h('p', {class:'tl-text', text:e.text}));
    ol.append(li); reveal(li);
  });
}
function updateTimeline(){
  const ol = $('tl'); if(!ol) return;
  const r = ol.getBoundingClientRect(), mid = innerHeight * 0.62;
  const p = Math.max(0, Math.min(1, (mid - r.top) / r.height));
  ol.style.setProperty('--p', p.toFixed(4));
  ol.querySelectorAll('li').forEach(li => { li.classList.toggle('on', li.getBoundingClientRect().top < mid); });
}

/* ---------- Diseases ---------- */
const gcol = id => { const g = K.GROUPS.find(x => x.id === id); return g ? g.color : '#2E7D55'; };
function photoState(d){
  if(!d.photo) return null;
  const c = S.cfg, f1 = c && c.per_class_f1 && c.per_class_f1[d.photo];
  const min = c && typeof c.min_class_f1 === 'number' ? c.min_class_f1 : 0.3;
  if(typeof f1 === 'number') return f1 >= min ? 'yes' : 'no';
  return d.id === 'anthracnose' ? 'no' : 'yes';
}
const CAMI = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linejoin="round" aria-hidden="true"><path d="M4 8.5h3l1.6-2.5h6.8L17 8.5h3v10.5H4z"/><circle cx="12" cy="13.5" r="3.4"/></svg>';
function badge(d, long){
  const st = photoState(d); if(!st) return null;
  const b = h('span', {class:'badge' + (st === 'no' ? ' no' : '')});
  if(st === 'yes') b.innerHTML = CAMI;
  b.append(document.createTextNode(st === 'yes' ? (long ? 'Photo check can suggest this' : 'Photo check') : (long ? 'Photo check cannot recognise this reliably' : 'Not in photo check')));
  return b;
}
function renderBadges(){
  K.DISEASES.forEach(d => {
    const slotT = document.querySelector('[data-bt="' + d.id + '"]'), slotA = document.querySelector('[data-ba="' + d.id + '"]');
    if(slotT){ slotT.replaceChildren(); const b = badge(d, false); if(b) slotT.append(b); }
    if(slotA){
      slotA.replaceChildren(); const b = badge(d, true);
      if(b){
        slotA.append(b);
        const f1 = S.cfg && S.cfg.per_class_f1 && S.cfg.per_class_f1[d.photo];
        if(typeof f1 === 'number') slotA.append(h('span', {class:'fine', text:'Test score ' + f1.toFixed(2) + ' out of 1.00'}));
      }
    }
  });
}

let filter = 'all';
function buildDiseases(){
  const fbox = $('filters'), tiles = $('tiles'), list = $('disList'), spy = $('spy');
  const opts = [{id:'all', name:'All', n:K.DISEASES.length}].concat(K.GROUPS.map(g => ({id:g.id, name:g.name, n:K.DISEASES.filter(d => d.group === g.id).length})));
  opts.push({id:'photo', name:'Photo check', n:K.DISEASES.filter(d => photoState(d) === 'yes').length});
  opts.forEach(o => fbox.append(h('button', {type:'button', 'data-f':o.id, 'aria-pressed':String(o.id === filter), text:o.name + ' ' + o.n})));
  fbox.addEventListener('click', e => {
    const b = e.target.closest('button[data-f]'); if(!b) return;
    filter = b.dataset.f;
    fbox.querySelectorAll('button').forEach(x => x.setAttribute('aria-pressed', String(x === b)));
    let n = 0;
    tiles.querySelectorAll('li').forEach(li => {
      const d = K.DISEASES.find(x => x.id === li.dataset.id);
      const show = filter === 'all' || (filter === 'photo' ? photoState(d) === 'yes' : d.group === filter);
      li.classList.toggle('off', !show); if(show) li.style.setProperty('--i', n++);
    });
  });

  K.DISEASES.forEach((d, i) => {
    const col = gcol(d.group), gname = (K.GROUPS.find(g => g.id === d.group) || {}).name || '';
    /* tile */
    const box = h('div', {class:'art-box'}); box.innerHTML = K.art(d.id, d.id + '-t');
    const tile = h('a', {class:'tile', href:'#d-' + d.id, style:'--grp:' + col}, box,
      h('span', {class:'tile-name', text:d.name}),
      h('span', {class:'tile-kind'}, h('i'), d.kind),
      h('span', {'data-bt':d.id}));
    tiles.append(h('li', {'data-id':d.id, style:'--i:' + i}, tile));

    /* spy link */
    spy.append(h('a', {href:'#d-' + d.id, 'data-id':d.id, style:'--grp:' + col, text:d.name}));

    /* article */
    const abox = h('div', {class:'art-box'}); abox.innerHTML = K.art(d.id, d.id + '-a');
    const dl = h('dl', null,
      h('div', null, h('dt', {text:'What to look for'}), h('dd', null, h('ul', null, d.signs.map(s => h('li', {text:s}))))),
      h('div', null, h('dt', {text:'How it spreads'}), h('dd', {text:d.spread})),
      h('div', null, h('dt', {text:'Where and when'}), h('dd', {text:d.where})),
      h('div', null, h('dt', {text:'What the guide suggests'}), h('dd', null, h('ul', null, d.manage.map(s => h('li', {text:s})))))
    );
    const art = h('article', {class:'dis', id:'d-' + d.id, 'data-id':d.id, style:'--grp:' + col, tabindex:'-1', 'aria-labelledby':'h-' + d.id},
      h('div', {class:'dis-art'}, abox),
      h('div', {class:'dis-main'},
        h('h3', {id:'h-' + d.id, text:d.name}),
        h('div', {class:'dis-kind'}, h('span', {text:gname.toLowerCase().indexOf(d.kind.toLowerCase()) >= 0 ? d.kind : gname + ', ' + d.kind.toLowerCase()}), h('span', {class:'cause', text:d.cause.join('; ')}), h('span', {'data-ba':d.id, class:'ba'})),
        h('p', {class:'dis-sum', text:d.blurb}),
        dl,
        h('div', {class:'dis-act'},
          h('button', {class:'btn primary', type:'button', 'data-q':d.q.signs, text:'Ask Kapas how to spot it'}),
          h('button', {class:'btn soft', type:'button', 'data-q':d.q.manage, text:'Ask Kapas how to manage it'}),
          h('a', {class:'dis-back', href:'#diseases', text:'Back to the list'}))
      ));
    list.append(art);
  });

  list.addEventListener('click', e => { const b = e.target.closest('button[data-q]'); if(b) askKapas(b.dataset.q); });
  renderBadges();
  initSpy(); initArtPlay();
}

function flash(el){
  if(!el) return;
  el.classList.remove('flash'); void el.offsetWidth; el.classList.add('flash');
  try{ el.focus({preventScroll:true}); }catch(e){}
  setTimeout(() => el.classList.remove('flash'), 4200);
}
function targetOf(hash){ return hash && hash.length > 1 ? document.getElementById(decodeURIComponent(hash.slice(1))) : null; }
document.addEventListener('click', e => {
  const a = e.target.closest('a[href^="#"]'); if(!a) return;
  const el = targetOf(a.getAttribute('href')); if(!el) return;
  if(el.classList.contains('dis')) flash(el);
});
addEventListener('hashchange', () => { const el = targetOf(location.hash); if(el && el.classList.contains('dis')) flash(el); });

function askKapas(q){
  const chat = $('chat');
  chat.scrollIntoView({behavior:reduced() ? 'auto' : 'smooth', block:'center'});
  setTimeout(() => ask(q), reduced() ? 0 : 650);
}

function initSpy(){
  const links = {}; document.querySelectorAll('#spy a').forEach(a => links[a.dataset.id] = a);
  document.querySelectorAll('.dis').forEach(a => {
    if(io) io.observe(a); else a.classList.add('in');
  });
  if(!('IntersectionObserver' in window)) return;
  const spy = new IntersectionObserver(es => es.forEach(en => {
    if(en.isIntersecting){
      Object.keys(links).forEach(k => links[k].setAttribute('aria-current', String(k === en.target.dataset.id)));
      const svg = en.target.querySelector('.art'); if(svg) svg.classList.add('play');
    }
  }), {rootMargin:'-30% 0px -60% 0px'});
  document.querySelectorAll('.dis').forEach(a => spy.observe(a));
}
function initArtPlay(){
  const arts = document.querySelectorAll('.tile .art');
  if(!('IntersectionObserver' in window)){ document.querySelectorAll('.art').forEach(a => a.classList.add('play')); return; }
  const o = new IntersectionObserver(es => es.forEach(en => {
    if(en.isIntersecting){ en.target.classList.add('play'); o.unobserve(en.target); }
  }), {threshold:0.4});
  arts.forEach(a => o.observe(a));
}

/* =====================================================================
   START
   ===================================================================== */
(function init(){
  syncTheme();
  const saved = LS.get('kapas.lang'); S.lang = (saved && I18N[saved]) ? saved : 'en';
  buildLang(); applyStatic(); renderSpeak(); renderSugg();
  buildDiseases(); buildZones(); buildHistory();
  if(location.protocol === 'file:'){ const l = $('legacyLink'); if(l) l.setAttribute('href', 'legacy-vbgramg.html'); }
  onScroll();
  if(location.hash){ const el = targetOf(location.hash); if(el){ setTimeout(() => { el.scrollIntoView(); if(el.classList.contains('dis')) flash(el); }, 150); } }
  fetch(API + '/api/cotton-status').then(r => { if(!r.ok) throw new Error('status ' + r.status); return r.json(); }).then(d => {
    S.cfg = d; S.down = false;
    if(Array.isArray(d.text_languages) && d.text_languages.length){
      S.langs = d.text_languages;
      if(S.langs.indexOf(S.lang) < 0) S.lang = 'en';
    }
    buildLang(); applyStatic(); renderChips(); renderSpeak(); renderReli(); refreshGo(); renderBadges();
    if(typeof d.min_probability === 'number') document.querySelectorAll('[data-live="minp"]').forEach(n => n.textContent = Math.round(d.min_probability * 100) + '%');
  }).catch(() => { S.down = true; renderChips(); });
})();
})();
