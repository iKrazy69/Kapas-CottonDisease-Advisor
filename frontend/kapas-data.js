/* Kapas site content.
   Every disease fact below is taken from the ICAR-CICR guide
   "Integrated Management of Cotton Pests, Diseases and Nematodes" (Nagrare V.S. et al., 2026).
   Risk tables are the guide's Tables 7 to 9. History facts are listed with their sources in the page footer.
   No spray names or doses are kept on the site on purpose: Kapas reads those from the guide and shows the source. */
(function(){
'use strict';

/* ---------- Groups (dye colours: leaf, catechu, turmeric, madder) ---------- */
const GROUPS = [
  {id:'leaf',   name:'Leaf diseases',        color:'#2E7D55'},
  {id:'roots',  name:'Roots and wilts',      color:'#8A5A34'},
  {id:'boll',   name:'Boll rots',            color:'#C98A0B'},
  {id:'bv',     name:'Bacterial and viral',  color:'#B8433A'}
];

/* ---------- Diseases ---------- */
const DISEASES = [
{
  id:'root-rot', name:'Root rot', group:'roots', kind:'Fungal, soil-borne',
  cause:['Rhizoctonia solani','Macrophomina phaseolina','Sclerotium rolfsii'],
  blurb:'A soil-borne rot that destroys the roots, cuts off water, and can kill a plant within days.',
  signs:[
    'Plants wilt and droop, and come out of the ground easily.',
    'Few or no side roots. Rhizoctonia leaves roots brown and wet. Macrophomina leaves them black and dry, with bark that shreds.',
    'In peak heat a plant can wilt for good within 24 to 48 hours, its dead leaves still clinging on.'
  ],
  spread:'It lives in the soil and likes warm, moist conditions. Desi cotton is far more susceptible than other types.',
  where:'Worst in the North zone (Haryana, Punjab, Rajasthan), where severe outbreaks can take up to half the plants, or whole pockets of a field. The guide rates it High in the North, Moderate in the Central zone and Low in the South, where it mainly affects Tamil Nadu.',
  manage:[
    'Plough deep in summer and rotate crops.',
    'Use farmyard manure enriched with Trichoderma.',
    'Sow healthy, treated seed.',
    'Avoid excess nitrogen and keep irrigation steady.',
    'Remove infected plants, and shred residues after harvest.'
  ],
  q:{signs:'What are the signs of root rot in cotton?', manage:'How can I manage root rot in cotton?'}
},
{
  id:'fusarium-wilt', name:'Fusarium wilt', group:'roots', kind:'Fungal, soil-borne', photo:'Fusarium wilt',
  cause:['Fusarium oxysporum f. sp. vasinfectum'],
  blurb:'A wilt fungus that blocks the plant’s water vessels. Cut the stem and look for a dark ring.',
  signs:[
    'Leaves turn yellow, then wilt and droop.',
    'Cut a root or stem and the inner tissue is dark brown. This is the most telling sign.',
    'Plants die in patches that follow the rows.'
  ],
  spread:'Seed, contaminated machinery and crop residue carry it, and its resting spores survive in soil for years. Root-knot nematodes make the wilt worse.',
  where:'Once a problem of Asiatic (desi) cotton, it is now reported in upland cotton too, including in North India and in light-soil pockets of Gujarat and Maharashtra where nematodes are also present. Moderate risk in the North and Central zones.',
  manage:[
    'Treat seed before sowing.',
    'Check fields for root-knot nematodes.',
    'Drain waterlogged ground.',
    'Feed the crop in balance, with enough potassium.',
    'Keep tools clean and remove crop residues.',
    'Rotate with maize, sorghum or paddy for two to three seasons.'
  ],
  q:{signs:'What are the signs of Fusarium wilt in cotton?', manage:'How can I manage Fusarium wilt in cotton?'}
},
{
  id:'internal-boll-rot', name:'Internal boll rot', group:'boll', kind:'Bacterial',
  cause:['Pantoea dispersa and other Pantoea species'],
  blurb:'The boll looks normal outside, but the lint inside turns yellow-brown and slimy.',
  signs:[
    'The outside of the boll looks normal.',
    'Inside, the lint turns yellow, brown or brick-coloured and slimy, and the seeds rot.',
    'Bolls can lock hard and open only partly. This is called hardlock.'
  ],
  spread:'Sap-sucking insects carry the bacteria in when they puncture young green bolls, around two to three weeks old.',
  where:'Now emerging in all three zones. The guide rates it High in the Central zone during flowering and boll development, Moderate in the South and Low in the North. Yield losses of up to 25% have been reported, and seed germination suffers.',
  manage:[
    'Give plants room and keep air moving through the canopy.',
    'Avoid excess nitrogen and phosphorus.',
    'Drain fields well.',
    'Keep sap-sucking insects down, since they carry the bacteria.',
    'Add foliar nutrition as advised.'
  ],
  q:{signs:'What are the signs of internal boll rot in cotton?', manage:'How can I manage internal boll rot in cotton?'}
},
{
  id:'fungal-boll-rot', name:'Boll rot (outside)', group:'boll', kind:'Fungal',
  cause:['A group of fungi, among them Lasiodiplodia theobromae, Colletotrichum, Alternaria and Fusarium'],
  blurb:'Several fungi rot bolls from the outside in, especially in cloudy, humid weather.',
  signs:[
    'Dead patches, and yellow or brown staining on the boll.',
    'Fungal growth on the boll surface.',
    'The fibre inside is discoloured and of poor quality.'
  ],
  spread:'The fungi enter through natural openings or through wounds made by insects. Cloudy, humid weather and rain splash at flowering and boll stage favour them.',
  where:'The guide rates it Moderate in the North (late stages) and Central zones, and Low in the South. The main damage is to lint quality.',
  manage:[
    'Choose early or mid-duration varieties and sow on time.',
    'Space plants well, drain fields and feed in balance.',
    'Open up the canopy.',
    'Control sap-sucking pests that make wounds.',
    'Make sure sprays reach the middle and lower canopy.',
    'Pick promptly and keep picked cotton clean.'
  ],
  q:{signs:'What are the signs of fungal boll rot in cotton?', manage:'How can I manage fungal boll rot in cotton?'}
},
{
  id:'target-spot', name:'Target spot', group:'leaf', kind:'Fungal', photo:'Target spot',
  cause:['Corynespora cassiicola'],
  blurb:'Round brown spots with rings that merge, and make leaves drop early.',
  signs:[
    'Small, round brown spots with rings inside them, like a target.',
    'Spots merge into large blighted patches.',
    'Leaves drop early. Spots can also reach leaf stalks, stems and bolls.'
  ],
  spread:'Wind and rain splash carry it. Warm, wet weather, a dense canopy and excess nitrogen favour it, and it repeats through the season.',
  where:'Now a major leaf spot in the Central zone. The guide rates it Moderate in the North and Central zones and Low in the South.',
  manage:[
    'Destroy crop residues and plough deep in summer.',
    'Space plants well, and use resistant varieties where available.',
    'Rotate crops.',
    'Avoid excess nitrogen and over-irrigation.',
    'Scout the lower canopy every week.'
  ],
  q:{signs:'What are the signs of target spot in cotton?', manage:'How can I manage target spot in cotton?'}
},
{
  id:'alternaria', name:'Alternaria leaf spot', group:'leaf', kind:'Fungal', photo:'Alternaria leaf spot',
  cause:['Alternaria macrospora','Alternaria alternata','Alternaria gossypina'],
  blurb:'Brown spots with purple edges and cracked centres, mostly on older, lower leaves.',
  signs:[
    'Small brown spots with purple margins.',
    'Rings inside the spots, and centres that crack as they dry.',
    'Older, lower leaves are hit first, and badly hit leaves drop.',
    'It can stain the lint.'
  ],
  spread:'Infected crop debris and seed carry it. Wet, humid, warm weather favours it.',
  where:'A major leaf disease in South India, common in humid Karnataka and Tamil Nadu. The guide rates it Moderate in the Central and South zones.',
  manage:[
    'Clear residues from the field and plough deep.',
    'Use early or resistant varieties and sow on time.',
    'Control weeds.',
    'Feed in balance, including potash.',
    'Scout every week and pick on time.'
  ],
  q:{signs:'What are the signs of Alternaria leaf spot in cotton?', manage:'How can I manage Alternaria leaf spot in cotton?'}
},
{
  id:'myrothecium', name:'Myrothecium leaf spot', group:'leaf', kind:'Fungal', photo:'Myrothecium leaf spot',
  cause:['Paramyrothecium roridum'],
  blurb:'Round spots with grey centres that later fall out, leaving shot holes.',
  signs:[
    'Round or irregular spots with light-brown or grey centres and purple edges.',
    'Water-soaked at first. The centres drop out later and leave shot holes.',
    'In humid weather, black spore masses with white tufts form on the spots.'
  ],
  spread:'Rain splash, irrigation water and wind spread it. It is carried on crop debris and seed, and plants with a heavy boll load are more susceptible.',
  where:'The guide lists it as Low risk in its North and Central tables, mainly at flowering and boll stages.',
  manage:[
    'Treat seed.',
    'Remove crop debris.',
    'Space plants well.',
    'Feed in balance.',
    'Start scouting about 30 days after sowing.'
  ],
  q:{signs:'What are the signs of Myrothecium leaf spot in cotton?', manage:'How can I manage Myrothecium leaf spot in cotton?'}
},
{
  id:'cotton-rust', name:'Cotton rust', group:'leaf', kind:'Fungal',
  cause:['Phakopsora gossypii'],
  blurb:'Small pinkish-brown pustules on older leaves, mostly in the dry season.',
  signs:[
    'Small pinkish-brown pustules on the leaf.',
    'They start on older, lower leaves.'
  ],
  spread:'It survives on wild grasses and volunteer cotton at field borders. It is a dry-season disease, December to March.',
  where:'Now a major disease in the South, especially in Andhra Pradesh, where it arrives mid-season instead of late. Minor in the North and Central zones.',
  manage:[
    'Clear field borders of wild grasses and volunteer plants.',
    'Avoid excess nitrogen and keep potassium adequate.',
    'Space plants well.',
    'Destroy crop residues.'
  ],
  q:{signs:'What are the signs of cotton rust?', manage:'How can I manage cotton rust?'}
},
{
  id:'grey-mildew', name:'Grey mildew', group:'leaf', kind:'Fungal',
  cause:['Ramularia areola (Mycosphaerella areola)'],
  blurb:'Pale, angular patches with a frosty white growth underneath.',
  signs:[
    'Pale, angular, see-through spots on older leaves, bounded by the veins.',
    'A frosty white growth on the underside of the leaf.',
    'Severe cases strip the plant of its leaves.'
  ],
  spread:'Heavy rain from June to September and humid weather favour it. It used to be a late-season disease of desi cotton, and now shows up mid and late season in upland and desi cotton alike.',
  where:'The Central and South zones. The guide rates it Low to Moderate.',
  manage:[
    'Plough deep in summer.',
    'Control weeds and volunteer cotton.',
    'Avoid excess nitrogen.',
    'Destroy residues after picking.'
  ],
  q:{signs:'What are the signs of grey mildew in cotton?', manage:'How can I manage grey mildew in cotton?'}
},
{
  id:'bacterial-leaf-blight', name:'Bacterial leaf blight', group:'bv', kind:'Bacterial', photo:'Bacterial leaf blight',
  cause:['Xanthomonas citri pv. malvacearum (also called blackarm)'],
  blurb:'Angular, water-soaked leaf spots that turn black and follow the veins.',
  signs:[
    'Water-soaked spots on the seed-leaves of seedlings.',
    'Angular leaf spots held in by the veins, turning brown to black.',
    'Amber ooze that dries to a whitish crust.',
    'Black streaks on stems (blackarm), and rotting bolls.'
  ],
  spread:'It is seed-borne. Rain splash, irrigation water and farm work spread it, and it survives in crop residue. Warm, humid weather favours it.',
  where:'Moderate in the Central zone, and in the South a Major disease from squaring onwards. Low in the North. Heavy losses are possible on susceptible varieties in humid conditions.',
  manage:[
    'Use acid-delinted, treated seed.',
    'Choose resistant hybrids.',
    'Scout every week, walking an X or Z across the field.',
    'Remove diseased seedlings.',
    'Avoid excess nitrogen and control weeds.',
    'Prefer furrow to overhead irrigation.',
    'Pick clean, destroy residues and plough deep.'
  ],
  q:{signs:'What are the signs of bacterial leaf blight in cotton?', manage:'How can I manage bacterial leaf blight in cotton?'}
},
{
  id:'leaf-curl', name:'Cotton leaf curl disease', group:'bv', kind:'Viral', photo:'Cotton leaf curl virus disease',
  cause:['Begomoviruses, carried only by the whitefly Bemisia tabaci'],
  blurb:'A whitefly-borne virus that curls leaves, thickens veins and stunts the plant.',
  signs:[
    'Leaf veins thicken, and leaves curl up or down.',
    'Small leaf-like outgrowths (enations) form under the leaf.',
    'Plants stay stunted, with few squares and flowers.'
  ],
  spread:'Only whiteflies carry it, from plant to plant. Weeds and other host crops nearby keep the virus going.',
  where:'Mainly the North zone (Punjab, Haryana, Rajasthan), where the guide rates it High from the vegetative stage onwards.',
  manage:[
    'Choose resistant varieties and sow on time.',
    'Grow border rows of desi cotton.',
    'Keep okra, cucurbits and tomato away from cotton fields.',
    'Pull out and bury infected plants, and remove weeds.',
    'Use yellow sticky traps, and neem early in the season.',
    'Avoid synthetic pyrethroids.',
    'Destroy ratoon crops.'
  ],
  q:{signs:'What are the signs of cotton leaf curl disease?', manage:'How can I manage cotton leaf curl disease?'}
},
{
  id:'tsv', name:'Tobacco streak virus', group:'bv', kind:'Viral',
  cause:['Tobacco streak virus, an RNA virus carried by thrips'],
  blurb:'A virus that thrips carry on pollen from weeds, mainly Parthenium.',
  signs:[
    'Yellow-green spots and rings that turn purple-brown and die.',
    'Squares and bracts dry up.',
    'Plants stay stunted, and those infected early may die.'
  ],
  spread:'Thrips move virus-carrying pollen, mostly from the weed Parthenium hysterophorus, onto cotton.',
  where:'Central and South India, including Marathwada and Vidarbha. In the South it is now a major constraint in popular Bt hybrids, and it causes what the guide calls Cotton Necrosis Disease.',
  manage:[
    'Choose resistant varieties and rotate crops.',
    'Control Parthenium and other weeds.',
    'Plant barrier or intercrop rows of pearl millet, maize, sorghum, pulses or soybean.',
    'Remove infected plants.',
    'Use blue sticky traps.'
  ],
  q:{signs:'What are the signs of tobacco streak virus in cotton?', manage:'How can I manage tobacco streak virus in cotton?'}
},
{
  id:'sooty-mould', name:'Sooty mould', group:'leaf', kind:'Fungal', photo:'Sooty mould disease',
  cause:['Sooty mould fungi growing on insect honeydew'],
  blurb:'A black film that grows on the sticky honeydew left by whiteflies, aphids and mealybugs.',
  signs:[
    'A black, sooty coating on the leaves.',
    'Leaves feel sticky from honeydew.'
  ],
  spread:'It grows on honeydew that sap-sucking insects drop on the leaves. The problem starts with those insects.',
  where:'The guide mentions it as a result of whitefly, aphid and mealybug infestations. It has no chapter of its own on sooty mould.',
  manage:[
    'The guide has no section on sooty mould itself. Ask Kapas about whitefly, aphid or mealybug management, or check with your KVK.'
  ],
  q:{signs:'What does sooty mould on cotton look like?', manage:'How can I manage whitefly, aphids and mealybugs on cotton?'}
},
{
  id:'anthracnose', name:'Anthracnose', group:'leaf', kind:'Fungal', photo:'Anthracnose',
  cause:['Colletotrichum gossypii','Colletotrichum siamense'],
  blurb:'Listed in the guide as a minor disease of the South zone, with not much impact.',
  signs:[
    'The guide gives no detailed description. It rates anthracnose Low risk with not much impact, in the South zone during flowering and boll stages.'
  ],
  spread:'The guide does not describe how it spreads.',
  where:'The South zone only.',
  manage:[
    'No management section in the guide. Ask Kapas, or check with your KVK.'
  ],
  q:{signs:'What is anthracnose in cotton?', manage:'How can I manage anthracnose in cotton?'}
}
];

/* ---------- Season: zones, stages and risk (guide Tables 7 to 9) ---------- */
const STAGES = [
  {n:'Seedling',      d:'1 to 20 days'},
  {n:'Vegetative',    d:'20 to 45 days'},
  {n:'Squaring',      d:'45 to 70 days'},
  {n:'Flowering and boll setting', d:'70 to 120 days'},
  {n:'Boll development', d:'120 to 150 days'},
  {n:'Harvest',       d:'150 to 180 days'}
];
/* L low, N minor, M moderate, H high, J major; null = not listed for that stage */
const ZONES = {
  north:{
    name:'North', states:'Punjab, Haryana, Rajasthan', sowing:'April to May', water:'mostly irrigated',
    rows:[
      ['Root rot','root-rot',            ['H','H','H','H','H',null]],
      ['Cotton leaf curl disease','leaf-curl', [null,'H','H','H','H',null]],
      ['Fusarium wilt','fusarium-wilt',  [null,'M','M','M','M',null]],
      ['Target spot','target-spot',      [null,'M','M','M','M',null]],
      ['Boll rot (outside)','fungal-boll-rot', [null,null,null,null,'M','M']],
      ['Bacterial leaf blight','bacterial-leaf-blight', ['L','L','L','L','L',null]],
      ['Tobacco streak virus','tsv',     [null,'L','L','L','L',null]],
      ['Internal boll rot','internal-boll-rot', [null,null,null,'L','L',null]],
      ['Myrothecium leaf spot','myrothecium', [null,null,null,'L','L',null]]
    ]
  },
  central:{
    name:'Central', states:'Maharashtra, Gujarat, Madhya Pradesh', sowing:'June to July', water:'mostly rainfed',
    rows:[
      ['Internal boll rot','internal-boll-rot', [null,null,null,'H','H',null]],
      ['Bacterial leaf blight','bacterial-leaf-blight', [null,'M','M','M','M',null]],
      ['Alternaria leaf spot','alternaria', [null,'M','M','M','M',null]],
      ['Root rot','root-rot',            ['M','M','M','M',null,null]],
      ['Fusarium wilt','fusarium-wilt',  [null,'M','M','M','M',null]],
      ['Target spot','target-spot',      [null,'M','M','M','M',null]],
      ['Grey mildew','grey-mildew',      [null,null,'L','M','M','M']],
      ['Boll rot (outside)','fungal-boll-rot', [null,null,null,'M','M','M']],
      ['Tobacco streak virus','tsv',     [null,'L','M','M',null,null]],
      ['Phomopsis leaf spot',null,       [null,'L','L',null,null,null]],
      ['Myrothecium leaf spot','myrothecium', [null,null,null,'L','L',null]]
    ]
  },
  south:{
    name:'South', states:'Andhra Pradesh, Telangana, Karnataka, Tamil Nadu', sowing:'June to August', water:'rainfed and irrigated',
    rows:[
      ['Bacterial leaf blight','bacterial-leaf-blight', [null,'M','J','J','J',null]],
      ['Alternaria leaf spot','alternaria', [null,'M','M','M','M',null]],
      ['Internal boll rot','internal-boll-rot', [null,null,null,'M','M',null]],
      ['Grey mildew','grey-mildew',      [null,null,'L','M','M','M']],
      ['Root rot','root-rot',            ['L','L','L','L','L',null]],
      ['Target spot','target-spot',      [null,'L','L','L','L',null]],
      ['Cotton rust','cotton-rust',      [null,null,'L','L','L','L']],
      ['Tobacco streak virus','tsv',     [null,'L','L','L',null,null]],
      ['Boll rot (outside)','fungal-boll-rot', [null,null,null,'L','L',null]],
      ['Anthracnose','anthracnose',      [null,null,null,'L','L',null]],
      ['Verticillium wilt',null,         [null,'L','L','L','L',null]],
      ['Helminthosporium leaf spot',null,[null,null,null,'L','L',null]],
      ['Cercospora leaf spot',null,      [null,null,null,'N',null,null]]
    ]
  }
};

/* ---------- History ---------- */
const HISTORY = [
  {when:'6th millennium BC', title:'Thread at Mehrgarh',
   text:'Cotton thread, preserved inside a copper bead in a Neolithic burial at Mehrgarh in present-day Pakistan, is an early trace of cotton use in the Indian subcontinent.'},
  {when:'About 4200 to 2300 BC', title:'Two more beginnings, in the Americas',
   text:'Sea Island cotton (Gossypium barbadense) was in use at Ancón, Peru, by about 4200 BC. Upland cotton (G. hirsutum), now over 90% of the world’s fibre, was in use in Mexico between about 3400 and 2300 BC.'},
  {when:'3rd millennium BC', title:'Cloth at Mohenjo-daro',
   text:'Fragments of cotton fabric and string were found at Mohenjo-daro, a city of the Indus Valley civilisation.'},
  {when:'7th century AD', title:'Muslin that Xuanzang admired',
   text:'The Chinese pilgrim Xuanzang compared Bengal’s finest cloth to the light vapours of dawn. Under the Mughals, Dhaka became a hub of fine muslin, and the Ain-i-Akbari lists dozens of varieties sold from Persia and Arabia to Europe and Southeast Asia.'},
  {when:'Around 1350', title:'The spinning wheel reaches Europe',
   text:'The spinning wheel reached Europe around this time.'},
  {when:'From 1757', title:'The weavers of Bengal lose their market',
   text:'East India Company tariffs and cheap cloth from Lancashire hurt Bengal’s weavers. By 1800, British observers were calling Dhaka muslin extinct. In 2020 Dhaka muslin received a Geographical Indication tag.'},
  {when:'1764 to 1793', title:'Machines take over spinning and ginning',
   text:'The spinning jenny (1764), Arkwright’s spinning frame (1769), Crompton’s mule (1775) and Whitney’s cotton gin (1793) mechanised the work that hands had done for millennia.'},
  {when:'1917 to 1957', title:'Khadi becomes a movement',
   text:'Gandhi had his first hand-woven khadi made at Sabarmati Ashram in 1917 and 1918. He asked Congress for a khadi department in 1922, the All India Spinners Association followed in 1925, and the Khadi and Village Industries Commission was set up by law in 1956 and 1957.'},
  {when:'2002 and 2006', title:'Bt cotton arrives',
   text:'Bollgard (2002) and Bollgard II (2006) brought Bt cotton to India. It now covers over 95% of the country’s cotton area.'},
  {when:'2026', title:'The CICR guide',
   text:'ICAR-CICR, Nagpur, publishes its illustrated guide to cotton pests, diseases and nematodes. It is the guide Kapas answers from.'}
];

/* ---------- Illustrations (simple drawings, not photographs) ---------- */
function rng(seed){ let s = (seed >>> 0) || 1; return function(){ s = (Math.imul(s, 1664525) + 1013904223) >>> 0; return s / 4294967296; }; }

const LEAF_D = 'M60 114 C57 102 55 93 53 85 C42 88 26 83 9 64 C25 60 36 60 45 63 C34 51 30 36 32 19 C45 29 54 43 58 58 C58 42 58 25 60 5 C62 25 62 42 62 58 C66 43 75 29 88 19 C90 36 86 51 75 63 C84 60 95 60 111 64 C94 83 78 88 67 85 C65 93 63 102 60 114Z';
const VEINS = 'M60 112 L60 14 M60 84 Q36 78 15 64 M60 84 Q84 78 105 64 M60 66 Q46 46 37 25 M60 66 Q74 46 83 25';

function svg(inner, uid, extra){
  return '<svg class="art' + (extra ? ' ' + extra : '') + '" viewBox="0 0 120 120" aria-hidden="true" focusable="false">' + inner + '</svg>';
}
function leaf(uid, over, opt){
  opt = opt || {};
  const tf = opt.tf ? ' transform="' + opt.tf + '"' : '';
  return svg('<defs><clipPath id="lc-' + uid + '"><path d="' + LEAF_D + '"/></clipPath></defs>' +
    '<g' + tf + '><path class="lf" d="' + LEAF_D + '"/>' +
    '<path class="vn' + (opt.thick ? ' thick' : '') + '" d="' + VEINS + '"/>' +
    '<g clip-path="url(#lc-' + uid + ')">' + over + '</g>' +
    (opt.after || '') + '</g>', uid);
}
const SPOTS = [[44,40],[76,44],[60,58],[32,66],[88,68],[50,76],[70,78],[60,34]];

function artTarget(uid){
  let o = '', k = 0;
  [[44,40,9],[77,45,7.5],[33,67,8],[87,69,10],[60,64,8],[58,32,6]].forEach(function(p){
    o += '<g class="les" style="--k:' + (k++) + '"><circle cx="' + p[0] + '" cy="' + p[1] + '" r="' + p[2] + '" fill="rgba(120,80,40,.28)" stroke="#6B4423" stroke-width="1.2"/>' +
         '<circle cx="' + p[0] + '" cy="' + p[1] + '" r="' + (p[2]*.62).toFixed(1) + '" fill="none" stroke="#6B4423" stroke-width="1.1"/>' +
         '<circle cx="' + p[0] + '" cy="' + p[1] + '" r="' + (p[2]*.26).toFixed(1) + '" fill="#6B4423"/></g>';
  });
  return leaf(uid, o);
}
function artAlternaria(uid){
  let o = '', k = 0;
  [[42,42,8],[78,46,6.5],[30,66,7],[90,68,8],[58,66,6],[64,30,5]].forEach(function(p){
    o += '<g class="les" style="--k:' + (k++) + '"><circle cx="' + p[0] + '" cy="' + p[1] + '" r="' + p[2] + '" fill="#B58A5C" stroke="#6A3D6E" stroke-width="2"/>' +
         '<circle cx="' + p[0] + '" cy="' + p[1] + '" r="' + (p[2]*.55).toFixed(1) + '" fill="none" stroke="#7A5A3A" stroke-width=".9" stroke-dasharray="3 2"/>' +
         '<path d="M' + (p[0]-p[2]*.4) + ' ' + p[1] + ' L' + (p[0]+p[2]*.4) + ' ' + (p[1]+1) + '" stroke="#4A3320" stroke-width=".9"/></g>';
  });
  return leaf(uid, o);
}
function artMyro(uid){
  let o = '', k = 0;
  [[44,42,9],[78,46,8],[32,67,8],[88,68,9],[60,64,7]].forEach(function(p){
    o += '<g class="les" style="--k:' + (k++) + '"><circle cx="' + p[0] + '" cy="' + p[1] + '" r="' + p[2] + '" fill="#D7C8A4" stroke="#7A4A82" stroke-width="2.2"/>' +
         '<circle cx="' + (p[0]-1.5) + '" cy="' + (p[1]-1) + '" r="2.2" style="fill:var(--tile,#e8efe9)" stroke="#7A4A82" stroke-width=".8"/>' +
         '<circle cx="' + (p[0]+2.5) + '" cy="' + (p[1]+2) + '" r="1.5" style="fill:var(--tile,#e8efe9)" stroke="#7A4A82" stroke-width=".7"/>' +
         '<circle cx="' + (p[0]+1) + '" cy="' + (p[1]-3) + '" r=".9" fill="#1d1a16"/></g>';
  });
  return leaf(uid, o);
}
function artRust(uid){
  const r = rng(7); let o = '';
  for(let i = 0; i < 46; i++){
    const x = 14 + r() * 92, y = 14 + r() * 92;
    o += '<g class="les" style="--k:' + (i % 9) + '"><circle cx="' + x.toFixed(1) + '" cy="' + y.toFixed(1) + '" r="3" fill="rgba(214,150,70,.35)"/><circle cx="' + x.toFixed(1) + '" cy="' + y.toFixed(1) + '" r="1.5" fill="#B5612A"/></g>';
  }
  return leaf(uid, o);
}
const ANG = [
  '38,32 51,36 49,50 37,47', '70,34 84,30 82,47 69,49', '19,62 35,58 40,72 25,75',
  '80,60 99,62 97,74 84,72', '51,60 67,62 64,76 50,74', '56,80 66,80 64,92 57,92'
];
function artGrey(uid){
  let o = '', k = 0;
  ANG.forEach(function(p){
    const c = p.split(' ').map(function(s){ return s.split(',').map(Number); });
    const cx = c.reduce(function(a, v){ return a + v[0]; }, 0) / c.length, cy = c.reduce(function(a, v){ return a + v[1]; }, 0) / c.length;
    o += '<g class="les" style="--k:' + (k++) + '"><polygon points="' + p + '" fill="#D5E1A2" stroke="#B2C477" stroke-width="1"/>' +
         '<circle cx="' + cx.toFixed(1) + '" cy="' + cy.toFixed(1) + '" r="3.2" fill="rgba(255,255,255,.8)"/><circle cx="' + (cx+3).toFixed(1) + '" cy="' + (cy+2).toFixed(1) + '" r="1.8" fill="rgba(255,255,255,.7)"/></g>';
  });
  return leaf(uid, o);
}
function artBlight(uid){
  let o = '', k = 0;
  ANG.forEach(function(p){
    o += '<g class="les" style="--k:' + (k++) + '"><polygon points="' + p + '" fill="rgba(170,180,60,.55)" stroke="rgba(170,180,60,.55)" stroke-width="5" stroke-linejoin="round"/>' +
         '<polygon points="' + p + '" fill="#2E2118"/></g>';
  });
  o += '<path class="les" style="--k:6" d="M60 100 L60 62" stroke="#2E2118" stroke-width="2.6" stroke-linecap="round" fill="none"/>';
  o += '<circle class="les" style="--k:7" cx="67" cy="44" r="1.7" fill="#E0A030"/>';
  return leaf(uid, o);
}
function artCurl(uid){
  const edge = '<path d="' + LEAF_D + '" fill="none" stroke="#12402A" stroke-width="3.4" stroke-dasharray="46 12" opacity=".55"/>';
  let tri = '';
  [[48,50],[72,52],[60,76],[40,70]].forEach(function(p, i){
    tri += '<path class="les" style="--k:' + i + '" d="M' + p[0] + ' ' + p[1] + ' l3 -6 l3 6z" fill="#14502F"/>';
  });
  return leaf(uid, edge + tri, {tf:'translate(14 4) scale(.76 .96)', thick:true});
}
function artTsv(uid){
  let o = '<path d="' + VEINS + '" stroke="#6A3A4A" stroke-width="3.2" fill="none" opacity=".5"/>', k = 0;
  [[44,42,7],[78,46,6],[32,67,6],[88,69,7],[56,70,5]].forEach(function(p){
    o += '<g class="les" style="--k:' + (k++) + '"><circle cx="' + p[0] + '" cy="' + p[1] + '" r="' + (p[2]+3) + '" fill="rgba(215,220,80,.5)"/>' +
         '<circle cx="' + p[0] + '" cy="' + p[1] + '" r="' + p[2] + '" fill="rgba(110,50,90,.2)" stroke="#5A2A5A" stroke-width="1.6"/><circle cx="' + p[0] + '" cy="' + p[1] + '" r="1.6" fill="#3C1B3C"/></g>';
  });
  return leaf(uid, o);
}
function artSooty(uid){
  const blob1 = 'M18 62 C28 50 46 54 52 44 C60 32 76 38 84 52 C94 56 104 64 94 74 C82 82 70 74 60 84 C46 88 28 80 18 62Z';
  const blob2 = 'M44 22 C52 18 58 26 56 34 C52 40 42 36 44 22Z';
  let o = '<path class="les" style="--k:0" d="' + blob1 + '" fill="#17140F" opacity=".9"/><path class="les" style="--k:1" d="' + blob2 + '" fill="#17140F" opacity=".9"/>';
  [[38,56],[66,48],[80,64],[56,70]].forEach(function(p, i){
    o += '<ellipse class="les" style="--k:' + (i + 2) + '" cx="' + p[0] + '" cy="' + p[1] + '" rx="3.2" ry="1.8" fill="#fff" stroke="#8a8a8a" stroke-width=".5" transform="rotate(-25 ' + p[0] + ' ' + p[1] + ')"/>';
  });
  return leaf(uid, o);
}
function artAnthracnose(uid){
  return leaf(uid,
    '<path class="les" style="--k:0" d="M30 56 C38 46 52 50 54 60 C56 72 42 78 32 72 C24 68 24 60 30 56Z" fill="#9B7B54" stroke="#5C4129" stroke-width="1.6"/>' +
    '<path class="les" style="--k:1" d="M72 42 C82 36 94 44 92 54 C90 64 78 66 72 60 C66 54 66 46 72 42Z" fill="#9B7B54" stroke="#5C4129" stroke-width="1.6"/>' +
    '<path class="les" style="--k:2" d="M46 28 C52 24 60 28 58 36 C54 42 44 38 46 28Z" fill="#A98A63" stroke="#5C4129" stroke-width="1.3"/>');
}
function artRootRot(uid){
  const r = rng(11); let dots = '';
  for(let i = 0; i < 26; i++) dots += '<circle cx="' + (10 + r() * 100).toFixed(1) + '" cy="' + (64 + r() * 52).toFixed(1) + '" r="' + (0.6 + r() * 0.9).toFixed(1) + '" style="fill:var(--soil-dot,#8A6A4A)" opacity=".5"/>';
  return svg(
    '<rect x="4" y="60" width="112" height="56" rx="6" style="fill:var(--soil,#D9C7AC)" opacity=".7"/>' + dots +
    '<path d="M4 60 H116" style="stroke:var(--soil-dot,#8A6A4A)" stroke-width="1.6"/>' +
    '<path d="M60 60 V34" stroke="#4F8A5E" stroke-width="3.6" stroke-linecap="round" fill="none"/>' +
    '<path d="M60 38 C70 28 88 34 92 52 C80 46 70 44 60 46Z" fill="#6E9A6B"/>' +
    '<path d="M60 40 C50 30 32 36 28 54 C40 48 50 46 60 48Z" fill="#6E9A6B"/>' +
    '<path d="M60 60 V108" stroke="#8B6540" stroke-width="5" stroke-linecap="round" fill="none"/>' +
    '<path d="M60 74 Q44 78 34 92 M60 84 Q76 88 86 100 M60 96 Q50 102 46 112" stroke="#8B6540" stroke-width="3" stroke-linecap="round" fill="none"/>' +
    '<g class="les" style="--k:0"><path d="M60 88 V108" stroke="#2B1B12" stroke-width="5.4" stroke-linecap="round" fill="none"/><path d="M40 86 L34 92 M80 94 L86 100 M48 106 L46 112" stroke="#2B1B12" stroke-width="3.4" stroke-linecap="round" fill="none"/></g>', uid);
}
function artFusarium(uid){
  let cracks = '';
  for(let i = 0; i < 10; i++){ const a = i * Math.PI / 5 + .3; cracks += '<path d="M' + (60 + Math.cos(a) * 36).toFixed(1) + ' ' + (60 + Math.sin(a) * 36).toFixed(1) + ' L' + (60 + Math.cos(a) * 43).toFixed(1) + ' ' + (60 + Math.sin(a) * 43).toFixed(1) + '" stroke="#6E5230" stroke-width="1.2"/>'; }
  return svg(
    '<circle cx="60" cy="60" r="46" fill="#A98458"/>' + cracks +
    '<circle cx="60" cy="60" r="37" fill="#EBDDBB"/>' +
    '<circle class="les" style="--k:0" cx="60" cy="60" r="26" fill="none" stroke="#5B3220" stroke-width="7" stroke-dasharray="6 3"/>' +
    '<circle cx="60" cy="60" r="10" fill="#F6ECD2"/>' +
    '<path d="M60 60 L60 24 M60 60 L90 76 M60 60 L30 76" stroke="#D9C79F" stroke-width="1" opacity=".7"/>', uid);
}
const BOLL = 'M60 16 C86 16 101 38 99 66 C97 91 81 105 60 105 C39 105 23 91 21 66 C19 38 34 16 60 16Z';
function artBollInside(uid){
  return svg(
    '<defs><clipPath id="bc-' + uid + '"><path d="' + BOLL + '"/></clipPath></defs>' +
    '<path d="' + BOLL + '" fill="#6E9F68"/>' +
    '<g clip-path="url(#bc-' + uid + ')"><rect x="60" y="0" width="70" height="120" fill="#CBA24A"/>' +
    '<g class="les" style="--k:0"><ellipse cx="74" cy="48" rx="6" ry="9" fill="#5B3A22"/><ellipse cx="86" cy="66" rx="6" ry="9" fill="#5B3A22" transform="rotate(20 86 66)"/><ellipse cx="72" cy="84" rx="6" ry="9" fill="#5B3A22" transform="rotate(-15 72 84)"/>' +
    '<path d="M64 36 Q74 56 66 74 M90 40 Q96 58 90 80" stroke="#E7CD8A" stroke-width="2" fill="none" opacity=".8"/></g></g>' +
    '<path d="M60 16 V105" stroke="#3E5E3A" stroke-width="1.6" stroke-dasharray="3 2"/>' +
    '<path d="M40 24 Q34 36 33 52" stroke="rgba(255,255,255,.4)" stroke-width="2.4" fill="none" stroke-linecap="round"/>' +
    '<path d="M50 104 C54 112 66 112 70 104" fill="#3E7A4B"/>', uid);
}
function artBollFungal(uid){
  return svg(
    '<path d="' + BOLL + '" fill="#8A9A62"/>' +
    '<path class="les" style="--k:0" d="M62 30 C80 28 92 44 88 60 C84 74 70 72 64 62 C56 52 52 34 62 30Z" fill="#3B2A1E"/>' +
    '<path class="les" style="--k:1" d="M30 70 C38 60 52 66 52 80 C50 92 36 94 30 86 C26 80 26 74 30 70Z" fill="#4A3724"/>' +
    '<g class="les" style="--k:2" fill="#F4E4E8" stroke="#D9B7C0" stroke-width=".6"><circle cx="64" cy="34" r="3.2"/><circle cx="70" cy="30" r="2.6"/><circle cx="80" cy="34" r="3"/><circle cx="86" cy="46" r="2.8"/><circle cx="34" cy="68" r="2.8"/><circle cx="44" cy="66" r="3.2"/><circle cx="50" cy="76" r="2.6"/></g>' +
    '<path d="M60 16 V28" stroke="#5B6B3A" stroke-width="2"/>' +
    '<path d="M50 104 C54 112 66 112 70 104" fill="#5F7A3E"/>', uid);
}

const ART = {
  'root-rot':artRootRot, 'fusarium-wilt':artFusarium, 'internal-boll-rot':artBollInside, 'fungal-boll-rot':artBollFungal,
  'target-spot':artTarget, 'alternaria':artAlternaria, 'myrothecium':artMyro, 'cotton-rust':artRust, 'grey-mildew':artGrey,
  'bacterial-leaf-blight':artBlight, 'leaf-curl':artCurl, 'tsv':artTsv, 'sooty-mould':artSooty, 'anthracnose':artAnthracnose
};
function art(id, uid){ return ART[id] ? ART[id](uid) : ''; }

/* Photo-check class name (as the model reports it) for each disease id */
const PHOTO = {};
DISEASES.forEach(function(d){ if(d.photo) PHOTO[d.photo] = d.id; });

window.KAPAS = {GROUPS:GROUPS, DISEASES:DISEASES, STAGES:STAGES, ZONES:ZONES, HISTORY:HISTORY, art:art, PHOTO:PHOTO, LEAF_D:LEAF_D, VEINS:VEINS};
})();
