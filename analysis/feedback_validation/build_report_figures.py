"""Build source-linked figures for the feedback revision; no analysis mutation."""
import csv,json,math
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch
from shapely.geometry import shape
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'analysis/feedback_validation/figures';OUT.mkdir(exist_ok=True)
font_manager.fontManager.addfont('/System/Library/Fonts/Supplemental/AppleGothic.ttf')
plt.rcParams.update({'font.family':'AppleGothic','axes.unicode_minus':False,'font.size':12,'figure.facecolor':'white','savefig.facecolor':'white'})
C={'navy':'#19354B','teal':'#167B75','gold':'#B16A23','muted':'#536674','light':'#EAF3F3'}
B=ROOT/'analysis/theory_validation'
s=json.loads((B/'spatial/route_inputs/jeonbuk_route_scenario.json').read_text())
comp=json.loads((B/'comparison/final_expanded_input/comparison_results.json').read_text())
r=next(a for a in comp['results'] if a['max_stops_per_route']==4 and a['method']=='exact_dp' and a['allocation_method']=='target_count_reference')
base=next(a for a in comp['results'] if a['max_stops_per_route']==4 and a['method']=='priority_nearest' and a['allocation_method']=='target_count_reference')
route=next(a for a in r['routes'] if a['service_zone']=='고창군')
z=next(a['engine_input'] for a in s['engine_input']['zones'] if a['zone_id']=='고창군'); candidates={a['candidate_id']:a for a in z['candidates']};targets={a['target_id']:a for a in z['targets']}
depot=s['depots_by_zone']['고창군']['start']
raw=(ROOT/'docs/demo-jeonbuk/map-data.js').read_text();md=json.JSONDecoder().raw_decode(raw[raw.find('{'):])[0]
legs={(a['origin_id'],a['destination_id']):a for a in md['route_legs'] if a['zone_id']=='고창군'}
sequence=[route['start_node_id']]+[a['candidate_id'] for a in route['stops']]+[route['end_node_id']]
# Actual stored OSM path geometry, with cartographic points simplified by the dashboard exporter.
fig,ax=plt.subplots(figsize=(9.0,5.5));fig.subplots_adjust(left=.025,right=.985,top=.97,bottom=.075)
for a in md['boundaries']:
 if a['service_zone']!='고창군':continue
 for poly in a['polygons']:
  xy=poly[0];ax.fill([p[0] for p in xy],[p[1] for p in xy],color='#F2F5F4',edgecolor='#BBC8CC',lw=.65,zorder=1)
colors=[C['teal'],'#4279A5','#977547','#8E637D',C['navy']]
for i,(a,b) in enumerate(zip(sequence,sequence[1:])):
 leg=legs[(a,b)];x,y=zip(*leg['path']);ax.plot(x,y,color=colors[i],lw=2.5,zorder=3)
 q=len(x)//2
 if q+1<len(x):ax.annotate('',xy=(x[q+1],y[q+1]),xytext=(x[q-1],y[q-1]),arrowprops={'arrowstyle':'-|>','color':colors[i],'lw':2,'mutation_scale':15},zorder=4)
labels=[]
for i,st in enumerate(route['stops'],1):
 c=candidates[st['candidate_id']];t=targets[st['target_ids'][0]];ax.scatter(c['lon'],c['lat'],s=270,c=C['teal'],edgecolors='white',linewidth=1.8,zorder=5);ax.text(c['lon'],c['lat'],str(i),ha='center',va='center',color='white',weight='bold',zorder=6,fontsize=11)
 offsets={1:(-95,16),2:(13,4),3:(12,-19),4:(12,5)}
 ax.annotate(t['name']+' '+c['name'],(c['lon'],c['lat']),xytext=offsets[i],textcoords='offset points',color=C['navy'],fontsize=11,bbox={'boxstyle':'round,pad=.3','fc':'white','ec':'none','alpha':.94},zorder=7)
 labels.append({'순서':i,'지역':t['name'],'방문장소':c['name'],'주소':c['addr'],'도착':st['arrival'],'서비스시작':st['service_start'],'서비스종료':st['service_end'],'이전장소로부터_km':st['travel_km_from_previous'],'이전장소로부터_분':st['travel_minutes_from_previous']})
ax.scatter(depot['lon'],depot['lat'],s=150,c=C['navy'],marker='s',edgecolors='white',zorder=7)
ax.annotate('출발·복귀\n고창해리우체국',(depot['lon'],depot['lat']),xytext=(-108,-43),textcoords='offset points',fontsize=11,color=C['navy'],bbox={'boxstyle':'round,pad=.3','fc':'white','ec':'none','alpha':.95},zorder=8)
ax.set_xlim(126.46,126.73);ax.set_ylim(35.29,35.565);ax.set_aspect(1/math.cos(math.radians(35.4)));ax.axis('off');ax.text(.02,.97,'고창군 하루 방문 예시',transform=ax.transAxes,fontsize=16,weight='bold',color=C['navy']);ax.text(.98,.04,'N ↑',transform=ax.transAxes,ha='right',color=C['muted']);fig.text(.04,.018,'자료: 저장된 최적화 결과와 OpenStreetMap 도로 경로 | 현장 운행·장소 사용 승인은 확인 전입니다.',fontsize=10,color=C['muted']);fig.savefig(OUT/'route_gocang.png',dpi=220);plt.close(fig)
# Headline flow.
fig,ax=plt.subplots(figsize=(10,2.25));ax.set_xlim(0,10);ax.set_ylim(0,2.25);ax.axis('off')
for x,num,label in [(0.05,'70곳','보완 전 방문 검토 대상'),(3.48,'54곳','접점 자료 보완 후 대상'),(6.91,'50곳','동선 계획에 포함한 대상')]:
 ax.add_patch(FancyBboxPatch((x,.58),2.98,1.55,boxstyle='round,pad=.02,rounding_size=.10',facecolor=C['light'],edgecolor='none'));ax.text(x+1.49,1.51,num,ha='center',va='center',color=C['teal'],fontsize=28,weight='bold');ax.text(x+1.49,.93,label,ha='center',fontsize=12,color=C['navy'])
for x in [3.25,6.68]:ax.text(x,1.33,'→',ha='center',fontsize=23,color=C['muted'])
ax.text(5,.20,'같은 50곳 방문  ·  1,103.950 km → 1,003.716 km  ·  이동거리 9.08% 감소',ha='center',fontsize=13,color=C['navy']);fig.subplots_adjust(left=.015,right=.985,top=.99,bottom=.01);fig.savefig(OUT/'summary_flow.png',dpi=220);plt.close(fig)
# Actual Wido boundary demonstrates why all-area centroid is not the main origin.
with (B/'spatial/results/access_expanded_internal.csv').open(encoding='utf-8-sig') as f:internal={a['code']:a for a in csv.DictReader(f)}
with (B/'spatial/results/access_expanded_centroid.csv').open(encoding='utf-8-sig') as f:centroid={a['code']:a for a in csv.DictReader(f)}
geoj=json.loads((B/'inputs/hjd2026.geojson').read_text());feature=next(f for f in geoj['features'] if f['properties']['adm_cd2']=='5280042000');geom=shape(feature['geometry']);a=internal['5280042000'];b=centroid['5280042000']
fig,(ax,tx)=plt.subplots(1,2,figsize=(9,3.8),gridspec_kw={'width_ratios':[1.05,1]});fig.subplots_adjust(left=.04,right=.99,top=.94,bottom=.10,wspace=.06)
for poly in geom.geoms if geom.geom_type=='MultiPolygon' else [geom]:
 x,y=poly.exterior.xy;ax.fill(x,y,color='#DDEEEE',edgecolor='#82ABA9',lw=.8)
ax.scatter(float(a['lon']),float(a['lat']),s=100,c=C['teal'],zorder=4);ax.annotate('분석에 쓴 기준 위치',(float(a['lon']),float(a['lat'])),xytext=(.04,.29),textcoords='axes fraction',arrowprops={'arrowstyle':'-','color':C['teal']},fontsize=10,color=C['teal'],bbox={'fc':'white','ec':'none','alpha':.94})
ax.scatter(float(b['lon']),float(b['lat']),s=95,c=C['gold'],marker='x',linewidth=2,zorder=4);ax.annotate('전체 모양의 중심\n(지역 바깥에 놓입니다)',(float(b['lon']),float(b['lat'])),xytext=(.03,.55),textcoords='axes fraction',arrowprops={'arrowstyle':'-','color':C['gold']},fontsize=10,color=C['gold'],bbox={'fc':'white','ec':'none','alpha':.94})
ax.set_aspect(1/math.cos(math.radians(35.6)));ax.axis('off');ax.set_title('부안군 위도면 실제 경계 예시',loc='left',fontsize=12,color=C['navy'],pad=6)
tx.axis('off');tx.text(.0,.88,'거리의 출발점은 지역 안의 한 지점입니다',fontsize=13,weight='bold',color=C['navy']);tx.text(.0,.66,'가장 큰 땅덩어리의 가운데를 우선 씁니다.\n그 점이 경계 밖이면 안쪽 지점으로 옮깁니다.',fontsize=11,linespacing=1.65,color=C['navy']);tx.text(.0,.37,'기준 위치 → 연결 도로 → 금융접점',fontsize=12,color=C['teal'],weight='bold');tx.text(.0,.16,'주민 집이나 행정복지센터의 위치는 아닙니다.\n주민 개인의 실제 이동거리로 해석하지 않습니다.',fontsize=11,linespacing=1.65,color=C['muted']);fig.text(.035,.035,'자료: SGIS 행정동 경계와 금방 기준 위치 비교 결과 | 전체 모양의 중심은 비교 분석에만 사용했습니다.',fontsize=9,color=C['muted']);fig.savefig(OUT/'origin_explainer.png',dpi=220);plt.close(fig)
with (OUT/'route_example.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(labels[0]));w.writeheader();w.writerows(labels)
meta={'zone':'고창군','depot':depot,'route':route,'stops_named':labels,'assumptions':{'speed_kmh':40,'service_minutes':45,'operating_hours':'09:00–17:00','venue_window':'09:00–16:30','road_geometry':'stored directed OSM route with at most 64 display points per leg','operational_ready':False},'sources':{'scenario':str((B/'spatial/route_inputs/jeonbuk_route_scenario.json').relative_to(ROOT)),'comparison':str((B/'comparison/final_expanded_input/comparison_results.json').relative_to(ROOT)),'map':'docs/demo-jeonbuk/map-data.js'},'origin_example':{'code':'5280042000','name':'부안군 위도면','main_origin':[float(a['lon']),float(a['lat'])],'centroid':[float(b['lon']),float(b['lat'])]}}
(OUT/'route_example.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2))
print(json.dumps({'figures':[str(p) for p in OUT.glob('*.png')],'route_stops':labels,'end_time':route['end_time'],'distance_km':route['travel_km']},ensure_ascii=False,indent=2))
