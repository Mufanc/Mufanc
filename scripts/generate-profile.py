from pathlib import Path
from xml.etree import ElementTree as E
from copy import deepcopy
import base64
import json
from codex_usage import panel
import argparse
import re
import time
from urllib.request import urlopen, Request
N='{http://www.w3.org/2000/svg}';E.register_namespace('',N[1:-1]);P=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('--usage', type=Path, required=True, help='Daily aggregate JSON from the usage-data branch')
parser.add_argument('--assets',type=Path,help='Use local SVG inputs instead of fetching')
parser.add_argument('--output',type=Path,default=Path('dist'))
args=parser.parse_args()
args.output.mkdir(parents=True,exist_ok=True)
P=args.assets or args.output / 'inputs'
P.mkdir(parents=True,exist_ok=True)
URLS={
 'icons':'https://skillicons.dev/icons?i=py,ts,rust,linux,androidstudio&theme=light',
 'stats':'https://readme-stats.mufanc.xyz/api?username=Mufanc&show_icons=true&include_all_commits=true&hide_border=true',
 'wakatime':'https://readme-stats.mufanc.xyz/api/wakatime?username=@Mufanc&theme=transparent&hide_border=true&langs_count=5&range=all_time&hide=Text,AUTO_DETECTED,Other',
 'languages':'https://readme-stats.mufanc.xyz/api/top-langs?username=Mufanc&theme=transparent&layout=compact&count_private=true&count_archive=false&hide_border=true&langs_count=8',
}
if not args.assets:
 for name,url in URLS.items():
  for attempt in range(3):
   try:
    with urlopen(Request(url,headers={'User-Agent':'Mufanc-profile-generator'}),timeout=30) as response:
     data=response.read(2_000_001)
    if len(data)>2_000_000 or E.fromstring(data).tag!=N+'svg':
     raise ValueError(f'Invalid SVG response: {name}')
    (P/f'{name}.svg').write_bytes(data)
    break
   except Exception:
    if attempt==2:raise
    time.sleep(2 ** attempt)
 for name in ['github-snake.svg','github-snake-dark.svg']:
  data=(args.output/name).read_bytes()
  E.fromstring(data)
  (P/name.replace('github-','')).write_bytes(data)

def read(name):return E.parse(P/f'{name}.svg').getroot()
def texts(root):return [''.join(e.itertext()).strip() for e in root.iter(N+'text')]
stats=read('stats');st=texts(stats);waka=read('wakatime');wt=texts(waka)[1:];langs=texts(read('languages'))[1:]
icons=[e for e in stats.iter() if e.get('class')=='icon']
ratios=[float(e.get('width').rstrip('%'))/100 for e in waka.iter() if e.get('data-testid')=='lang-progress']
if len(st)!=12 or len(icons)!=5 or len(ratios)!=5 or len(wt)!=10 or len(langs)!=8:
 raise ValueError('Unexpected stats response; refusing to publish incomplete profile')
if any(not 0 <= v <= 1 for v in ratios):raise ValueError('Invalid WakaTime percentages')
rank_match=re.search(r'@keyframes rankAnimation.*?to\s*\{\s*stroke-dashoffset:\s*([\d.]+)', ''.join(stats.itertext()), re.S)
if not rank_match:raise ValueError('Missing rank percentage')
rank_fraction=1-float(rank_match[1])/251.32741228718345
colors=[e.get('fill') for e in read('languages').iter(N+'circle')]
if len(colors)!=8:raise ValueError('Missing language colors')
for dark in [False,True]:
 theme='dark' if dark else 'light'
 ink,muted,accent,line,track=('#e6edf3','#919ba7','#69b5ff','#30363d','#212a35') if dark else ('#202932','#6b7785','#0969da','#e1e6ec','#edf1f5')
 r=E.Element(N+'svg',{'width':'900','height':'710','viewBox':'0 0 900 710','role':'img','aria-labelledby':'title desc'})
 E.SubElement(r,N+'title',{'id':'title'}).text='Mufanc — developer profile'
 E.SubElement(r,N+'desc',{'id':'desc'}).text='Skills, GitHub statistics, coding time, programming languages and animated contributions.'
 def el(tag,**a):return E.SubElement(r,N+tag,{k.replace('_','-'):str(v) for k,v in a.items()})
 def text(x,y,s,size=13,color=None,weight='400',mono=False,**a):
  e=el('text',x=x,y=y,fill=color or ink,font_family='Menlo,Consolas,monospace' if mono else 'Arial,Helvetica,sans-serif',font_size=size,font_weight=weight,**a);e.text=s;return e
 def image(data,x,y,w,h):el('image',x=x,y=y,width=w,height=h,href='data:image/svg+xml;base64,'+base64.b64encode(data).decode())
 def label(x,y,s):text(x,y,s,11,accent,'500',True)
 label(28,27,'mufanc@github:~')
 text(26,93,'Mufanc',56,weight='700',letter_spacing='-2')
 text(29,122,'Code. Design. Explore.',16,muted)
 label(599,41,'$ ./toolchain')
 image((P/'icons.svg').read_bytes(),599,59,273,48)
 # A single compact GitHub summary with the five original Octicons.
 label(28,176,'$ gh stats')
 for i,(name,value) in enumerate(zip(['Stars earned','Commits','Pull requests','Issues','Repos contributed'],st[3::2])):
  x=28+i*141
  ic=deepcopy(icons[i]);ic.attrib.update(x=str(x),y='192',width='16',height='16',fill=accent);r.append(ic)
  text(x,246,value,34,weight='700',letter_spacing='-1')
  text(x,269,name,12,muted)
  if i==4:text(x,287,'last year',10,muted)
 cx,cy=810,228
 el('circle',cx=cx,cy=cy,r=35,fill='none',stroke=track,stroke_width=6)
 el('circle',cx=cx,cy=cy,r=35,fill='none',stroke=accent,stroke_width=6,stroke_dasharray=f'{219.9114857513*rank_fraction} 219.9114857513',stroke_linecap='round',transform=f'rotate(-90 {cx} {cy})')
 text(cx,237,st[1],25,weight='700',text_anchor='middle');text(cx,282,'GitHub rank',11,muted,text_anchor='middle')
 el('path',d='M28 308H872',stroke=line)
 label(28,339,'$ wakatime --stats');label(535,339,'$ gh languages')
 for i,ratio in enumerate(ratios):
  y=371+i*35
  text(28,y,wt[i*2].rstrip(':'),13,weight='600')
  text(454,y,wt[i*2+1],12,muted,text_anchor='end')
  el('rect',x=28,y=y+9,width=426,height=5,rx=2.5,fill=track)
  el('rect',x=28,y=y+9,width=426*ratio,height=5,rx=2.5,fill=accent)
 defs=el('defs')
 clip=E.SubElement(defs,N+'clipPath',{'id':'language-bar'})
 E.SubElement(clip,N+'rect',{'x':'535','y':'363','width':'337','height':'9','rx':'4.5'})
 x=535
 for s,c in zip(langs,colors):
  pct=float(s.rsplit(' ',1)[1][:-1]);w=337*pct/100
  el('rect',x=x,y=363,width=w,height=9,fill=c,clip_path='url(#language-bar)');x+=w
 for i,(s,c) in enumerate(zip(langs,colors)):
  name,pct=s.rsplit(' ',1);x=535+(i//4)*180;y=404+(i%4)*35
  el('circle',cx=x+4,cy=y-4,r=4,fill=c)
  text(x+15,y,name,12);text(x+157,y,pct,11,muted,text_anchor='end')
 el('path',d='M28 548H872',stroke=line)
 label(28,580,'$ git log --graph')
 text(872,580,'CONTRIBUTION ACTIVITY',10,muted,mono=True,text_anchor='end')
 snake=(P/('snake-dark.svg' if dark else 'snake.svg')).read_bytes()
 # Crop only the original SVG's blank margins; keep every animation definition.
 sr=E.fromstring(snake);sr.set('viewBox','-16 -18 880 132');sr.set('height','132')
 sr.attrib.update(id='contribution-snake', x='10', y='582', width='880', height='132')
 # Inline the animated nodes: nested image resources can render only a static frame.
 for style in sr.iter(N+'style'):
  style.text=style.text.replace(':root', '#contribution-snake')
 r.append(sr)
 assert len(r.findall(N+'image'))==1 and b'@keyframes' in E.tostring(sr)
 el('path', d='M28 720H872', stroke=line)
 r.append(panel(json.loads(args.usage.read_text()), dark))
 r.set('height', '953'); r.set('viewBox', '0 0 900 953')
 target=args.output/f'profile-{theme}.svg'
 E.ElementTree(r).write(target,encoding='unicode')
 print(f'Generated {target}')
