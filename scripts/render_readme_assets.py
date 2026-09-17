#!/usr/bin/env python3
"""Render original README illustrations. Requires Pillow and locally supplied fonts."""
import argparse
from pathlib import Path
import math
from PIL import Image, ImageDraw, ImageFont

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--font-dir', type=Path, required=True)
parser.add_argument('--cjk-font', type=Path, required=True)
args = parser.parse_args()
OUT = Path(__file__).resolve().parents[1] / 'docs/assets/readme'
OUT.mkdir(parents=True, exist_ok=True)
BG='#F6F3EE'; INK='#242522'; MUTED='#73766E'; RED='#C83127'; LINE='#D9D6CE'; PALE='#ECE9E2'; WHITE='#FFFEFA'

def font(size, bold=False, mono=False, zh=False):
    path=args.cjk_font if zh else args.font_dir / ('IBMPlexMono-Regular.ttf' if mono else 'InstrumentSans-Bold.ttf' if bold else 'InstrumentSans-Regular.ttf')
    return ImageFont.truetype(str(path),size)

def canvas(h):
    im=Image.new('RGB',(1800,h),BG)
    return im,ImageDraw.Draw(im)

def text(d,x,y,t,size=30,color=INK,bold=False,mono=False):
    f=font(size,bold,mono,any(ord(c)>127 for c in t))
    d.text((x,y),t,font=f,fill=color,anchor='lt')

def line(d,points,color=LINE,w=2):d.line(points,fill=color,width=w,joint='curve')

def arrow(d,points,color=MUTED,w=3):
    line(d,points,color,w)
    x,y=points[-1];a,b=points[-2];angle=math.atan2(y-b,x-a)
    d.polygon([(x,y),(x-12*math.cos(angle-.5),y-12*math.sin(angle-.5)),(x-12*math.cos(angle+.5),y-12*math.sin(angle+.5))],fill=color)

def dot(d,x,y,r=8,fill=RED):d.ellipse((x-r,y-r,x+r,y+r),fill=fill)

def footer(d,y,left,right):
    line(d,[(76,y),(1724,y)])
    text(d,76,y+24,left,20,MUTED,mono=True)
    f=font(20,mono=True);text(d,1724-d.textlength(right,font=f),y+24,right,20,MUTED,mono=True)

def banner(lang):
    zh=lang=='zh'; im,d=canvas(740)
    text(d,78,66,'M E M P U L S E   /   L O C A L   M E M O R Y',21,MUTED,mono=True)
    text(d,72,156,'MemPulse',116,bold=True)
    text(d,79,319,'记忆，沿着话题生长。' if zh else 'Memory follows the thread.',43)
    text(d,80,397,'让 Agent 在下一次会话中，接着完成。' if zh else 'Give your agent a place to pick up where it left off.',27,MUTED)
    labels=['本地优先','话题记忆','上下文恢复'] if zh else ['LOCAL FIRST','TOPIC MEMORY','CONTEXT RESTORE']
    x=80
    for label in labels:
        f=font(18,mono=not zh,zh=zh);w=d.textlength(label,font=f)+34
        d.rounded_rectangle((x,487,x+w,529),radius=6,outline=LINE,width=2)
        text(d,x+17,499,label,18,MUTED,mono=not zh);x+=w+13
    # Three parallel memory traces, with one active trajectory and contextual branches.
    for k in range(3):
        pts=[(1020,190+k*170),(1130,190+k*170),(1240,240+k*110),(1390,240+k*110),(1500,175+k*145),(1710,175+k*145)]
        line(d,pts,LINE,3)
        for x,y in pts:dot(d,x,y,5,LINE)
    pts=[(980,360),(1090,360),(1170,285),(1300,285),(1400,395),(1540,395),(1630,290),(1730,290)]
    line(d,pts,RED,5)
    for x,y in pts[1:-1]:
        d.ellipse((x-16,y-16,x+16,y+16),fill=BG,outline=RED,width=3);dot(d,x,y,5)
    text(d,1040,118,'01 / CAPTURE',18,MUTED,mono=True)
    text(d,1460,487,'02 / CONNECT',18,MUTED,mono=True)
    text(d,1480,220,'03 / RECALL',18,RED,mono=True)
    footer(d,642,'PERSISTENT CONTEXT FOR AGENTS','SQLITE  /  ONNX  /  ELECTRON')
    im.save(OUT/f'hero-{lang}.png',optimize=True)

def box(d,x,y,w,h,kicker,title,sub,accent=False):
    d.rounded_rectangle((x,y,x+w,y+h),radius=14,fill=WHITE,outline=RED if accent else LINE,width=2)
    text(d,x+27,y+23,kicker,18,RED if accent else MUTED,mono=True)
    text(d,x+27,y+57,title,31,bold=True)
    text(d,x+27,y+106,sub,23,MUTED)

def architecture(lang):
    zh=lang=='zh';im,d=canvas(1070)
    text(d,76,58,'SYSTEM / 01',20,RED,mono=True)
    text(d,76,110,'一个本地记忆核心，多种访问入口。' if zh else 'One local memory core. Multiple entry points.',49,bold=True)
    text(d,76,181,'桌面集成、Agent 工具与独立接口共享同一套记忆能力。' if zh else 'Desktop integration, agent tools and standalone adapters share the same memory service.',27,MUTED)
    box(d,76,272,426,162,'CLIENT','桌面界面' if zh else 'Desktop UI','SolidJS / Electron renderer')
    box(d,638,272,410,162,'BRIDGE','MemoryBridge','Electron main process',True)
    box(d,1184,272,540,162,'SERVICE','MemPulse / Python','DesktopService / TopicFacade',True)
    arrow(d,[(502,352),(638,352)],RED);text(d,541,315,'IPC',21,MUTED,mono=True)
    arrow(d,[(1048,352),(1184,352)],RED);text(d,1066,305,'JSON',19,MUTED,mono=True);text(d,1066,328,'lines',19,MUTED,mono=True)
    box(d,76,535,426,162,'AGENT','OpenCode 插件' if zh else 'OpenCode plugin','memory_* tools / context')
    arrow(d,[(502,610),(567,610),(567,403),(638,403)])
    text(d,78,734,'Loopback HTTP + per-launch bearer token',19,MUTED,mono=True)
    box(d,638,535,410,162,'ADAPTERS','CLI / MCP / HTTP','独立服务入口' if zh else 'Standalone access')
    arrow(d,[(1048,610),(1108,610),(1108,402),(1184,402)])
    arrow(d,[(1454,434),(1454,501)],RED)
    d.rounded_rectangle((1184,501,1724,803),radius=14,fill=PALE)
    text(d,1214,530,'LOCAL RESOURCES',18,MUTED,mono=True)
    text(d,1214,577,'SQLite + FTS5',30,bold=True)
    text(d,1214,624,'话题 · 事件 · 偏好 · 检查点' if zh else 'Topics / events / preferences / checkpoints',23,MUTED)
    line(d,[(1214,674),(1694,674)])
    text(d,1214,706,'TIDE / ONNX FP32',30,bold=True)
    text(d,1214,750,'本地检索编码器' if zh else 'Local retrieval encoder',23,MUTED)
    d.rounded_rectangle((76,847,1724,936),radius=10,fill=INK)
    text(d,106,879,'写入控制：桌面 Agent 先提出变更，由用户确认后执行。' if zh else 'WRITE CONTROL  /  Desktop agent mutations are proposed first, then confirmed by the user.',27,WHITE)
    footer(d,985,'MEMPULSE / ARCHITECTURE','SIMPLIFIED REQUEST FLOW')
    im.save(OUT/f'architecture-{lang}.png',optimize=True)

def lifecycle(lang):
    zh=lang=='zh';im,d=canvas(640)
    text(d,76,57,'MEMORY / 02',20,RED,mono=True)
    text(d,76,108,'从一次交互，到可恢复的工作脉络。' if zh else 'From a single interaction to a recoverable thread.',46,bold=True)
    rows=[('01','记录与归属','事件保留来源，未归属内容进入待处理区。','Capture & associate','Keep event provenance; unbound capture stays pending.'),('02','按话题组织','连接事件、偏好、知识与检查点。','Organize by topic','Connect events, preferences, knowledge and checkpoints.'),('03','检索与恢复','返回相关证据、当前状态及待补信息。','Retrieve & restore','Return relevant evidence, current state and missing context.')]
    for i,(n,a,b,c,e) in enumerate(rows):
        x=76+i*565
        line(d,[(x,245),(x+516,245)],LINE,2)
        dot(d,x+12,245,10,RED if i==2 else MUTED)
        if i<2:arrow(d,[(x+520,245),(x+550,245)])
        text(d,x,295,n,23,RED,mono=True)
        text(d,x,349,a if zh else c,35,bold=True)
        if zh:text(d,x,416,b,23,MUTED)
        else:
            lines=[['Keep event provenance;','unbound capture stays pending.'],['Connect events, preferences,','knowledge and checkpoints.'],['Return relevant evidence, current','state and missing context.']][i]
            for j,t in enumerate(lines):text(d,x,411+j*33,t,24,MUTED)
    footer(d,550,'MEMPULSE / TOPIC MEMORY','CAPTURE  >  ORGANIZE  >  RESTORE')
    im.save(OUT/f'lifecycle-{lang}.png',optimize=True)

for lang in ['en','zh']:
    banner(lang);architecture(lang);lifecycle(lang)
