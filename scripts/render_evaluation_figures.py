#!/usr/bin/env python3
"""Render bilingual topic rationale and measured charts (Matplotlib; no invented metrics)."""
import argparse
from pathlib import Path
import json
import math
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Patch

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--data',type=Path,default=Path(__file__).resolve().parents[1]/'docs/evaluation/2026-09-17/measurements.json')
p.add_argument('--cjk-font',type=Path,required=True)
p.add_argument('--output',type=Path,default=Path(__file__).resolve().parents[1]/'docs/assets/evaluation')
a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
D=json.loads(a.data.read_text());font_manager.fontManager.addfont(str(a.cjk_font))
CJK=font_manager.FontProperties(fname=str(a.cjk_font)).get_name()
BG='#f6f3ee';INK='#242522';MUTED='#68736c';GRID='#d9d6ce';RED='#c83127';BASE='#85938c';TEAL='#286a80';WHITE='#fffefa'
plt.rcParams.update({'svg.fonttype':'path','axes.unicode_minus':False,'font.size':12,'axes.labelcolor':MUTED,'xtick.color':MUTED,'ytick.color':INK,'axes.edgecolor':GRID,'savefig.facecolor':BG})

def start(lang,size):
    plt.rcParams['font.family']=CJK if lang=='zh' else 'DejaVu Sans'
    return plt.figure(figsize=size,facecolor=BG)

def save(fig,name,lang):
    for ext in ['png','svg']:
        target=a.output/f'{name}-{lang}.{ext}'
        fig.savefig(target,dpi=170)
        if ext=='svg':
            target.write_text('\n'.join(line.rstrip() for line in target.read_text().splitlines())+'\n')
    plt.close(fig)

def clean(ax):
    ax.set_facecolor(WHITE)
    for side in ['top','right','left']:ax.spines[side].set_visible(False)
    ax.tick_params(axis='both',length=0,pad=8)
    ax.grid(axis='x',color=GRID,linewidth=.6,zorder=0)
    ax.set_axisbelow(True)

def labels(lang):
    return ['词法 / 结构化（无模型）','相同话题结构 + TIDE FP32'] if lang=='zh' else ['Lexical / structured (no encoder)','Same topic structure + TIDE FP32']

def rationale(lang):
    zh=lang=='zh';fig=start(lang,(12,7.2));ax=fig.add_axes([0,0,1,1]);ax.set_xlim(0,1800);ax.set_ylim(1080,0);ax.axis('off')
    def text(x,y,s,size=12,color=INK,weight='normal',**kw):ax.text(x,y,s,fontsize=size,color=color,weight=weight,va='top',**kw)
    def box(x,y,w,h,fill=WHITE,edge=GRID):ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0,rounding_size=13',facecolor=fill,edgecolor=edge,linewidth=1))
    text(80,50,'MEMPULSE / WHY TOPICS',10,RED)
    text(80,100,'会话会切换，正在推进的事仍要接得上。' if zh else 'Sessions change. The work still needs continuity.',23,weight='bold')
    text(80,170,'交互按时间发生' if zh else 'Interactions arrive over time',13,MUTED)
    text(1040,170,'记忆按持续事项组织' if zh else 'Memory follows each ongoing matter',13,MUTED)
    rows=[
        [('青禾报告 · 确认需求','Report / confirm requirements',RED),('网络排障 · 定位故障','Network / diagnose failure',TEAL)],
        [('网络排障 · 验证补丁','Network / validate patch',TEAL),('青禾报告 · 改用 V3','Report / switch to V3',RED)],
        [('青禾报告 · 初稿复核','Report / review the draft',RED),('网络排障 · 复测结果','Network / record retest',TEAL)],
    ]
    points=[]
    for i,row in enumerate(rows):
        y=235+i*195;box(80,y,535,162)
        text(108,y+18,('会话 ' if zh else 'SESSION ')+str(i+1),10,MUTED)
        for j,(cn,en,color) in enumerate(row):
            yy=y+66+j*49;ax.plot(111,yy+10,'o',color=color,markersize=5)
            text(133,yy,cn if zh else en,12.5)
            points.append((615,yy+12,color))
    slots={RED:iter([297,347,397]),TEAL:iter([577,627,677])}
    for x,y,color in points:
        target=next(slots[color])
        ax.add_patch(FancyArrowPatch((x+12,y),(1024,target),arrowstyle='-|>',mutation_scale=12,linewidth=1.25,color=color,alpha=.55,connectionstyle='arc3,rad=0.06'))
    box(716,452,233,48,BG,BG);text(832,464,'明确归属后' if zh else 'After association',11,MUTED,ha='center')
    for y,color,title,goal,steps in [
        (236,RED,'话题 A · 青禾交付报告' if zh else 'TOPIC A / Qinghe delivery report','目标：完成报告交付与复核' if zh else 'Goal: complete and review the report','需求确认 → 模板 V3 → 初稿复核' if zh else 'Requirements → V3 → Draft review'),
        (516,TEAL,'话题 B · 网络排障' if zh else 'TOPIC B / Network troubleshooting','目标：恢复连接并保留诊断依据' if zh else 'Goal: restore connectivity','定位故障 → 验证补丁 → 复测结果' if zh else 'Diagnosis → Patch → Retest'),
    ]:
        box(1040,y,680,230,WHITE,color);text(1074,y+30,title,15,color,'bold');text(1074,y+89,goal,12.5);text(1074,y+145,steps,12,MUTED)
    benefits=[('跨会话接续','Continue across sessions','事项身份不随聊天窗口改变','Preserve the identity of the work'),('找回前因后果','Recover the history','按事项汇集来源证据与版本变化','Connect evidence and version changes'),('分清事项边界','Keep matters distinct','同一项目里的不同目标分别维护','Separate goals within the same project')]
    for i,(cn,en,subcn,suben) in enumerate(benefits):
        x=80+i*565;text(x,842,cn if zh else en,15,weight='bold');text(x,893,subcn if zh else suben,11.5,MUTED)
    ax.plot([80,1720],[984,984],color=GRID,lw=.8)
    text(80,1010,'组织方式示意；保留来源，不代表有无话题的性能对照实验。' if zh else 'Conceptual organization diagram; preserves provenance. Not a topic-vs-flat-memory experiment.',10,MUTED)
    save(fig,'why-topics',lang)

def comparison(lang):
    zh=lang=='zh';fig=start(lang,(12.4,6.9))
    fig.text(.045,.938,'同一话题结构下的检索效果与耗时' if zh else 'Retrieval quality and latency within the same topic structure',fontsize=21,weight='bold',color=INK)
    fig.text(.045,.882,f"{D['dataset']['topics']} 个话题 · {D['dataset']['events']} 条事件 · {D['dataset']['positive_queries']} 个正例 / {D['dataset']['unique_queries']} 个唯一问题 · {D['dataset']['rounds']} 轮计时" if zh else f"{D['dataset']['topics']} topics · {D['dataset']['events']} events · {D['dataset']['positive_queries']} positive / {D['dataset']['unique_queries']} unique queries · {D['dataset']['rounds']} timing rounds",fontsize=11.5,color=MUTED)
    fig.legend(handles=[Patch(color=BASE,label=labels(lang)[0]),Patch(color=RED,label=labels(lang)[1])],loc='upper left',bbox_to_anchor=(.04,.852),ncol=2,frameon=False,fontsize=11)
    ax=fig.add_axes([.235,.235,.425,.49]);clean(ax)
    metrics=[('topic_top1','话题 Top-1','Topic Top-1'),('topic_recall_at_3','话题 Recall@3','Topic Recall@3'),('evidence_recall_macro','证据 Recall@10\n宏平均','Evidence Recall@10\nmacro average'),('evidence_complete','全部证据覆盖','Complete evidence\ncoverage')]
    for j,(mode,color) in enumerate([('lexical',BASE),('fp32',RED)]):
        vals=[D['retrieval'][mode]['overall'][k]*100 for k,_,_ in metrics]
        ys=[i+(j-.5)*.29 for i in range(4)]
        ax.barh(ys,vals,height=.25,color=color,zorder=3)
        for y,v in zip(ys,vals):ax.text(v+1.5,y,f'{v:.2f}%',ha='left',va='center',fontsize=10,color=INK)
    ax.set_yticks(range(4),[cn if zh else en for _,cn,en in metrics],fontsize=11);ax.invert_yaxis();ax.set_xlim(0,117);ax.set_xticks([0,25,50,75,100]);ax.set_xlabel('比例（%）· 越高越好' if zh else 'Percent · higher is better',fontsize=11)
    ax2=fig.add_axes([.77,.235,.19,.49]);clean(ax2)
    for j,(mode,color) in enumerate([('lexical',BASE),('fp32',RED)]):
        vals=[D['retrieval'][mode]['overall']['timing'][k] for k in ['p50_ms','p95_ms']]
        ys=[i+(j-.5)*.29 for i in range(2)]
        ax2.barh(ys,vals,height=.25,color=color,zorder=3)
        for y,v in zip(ys,vals):ax2.text(v+1.5,y,f'{v:.2f}',va='center',fontsize=10)
    ax2.set_yticks([0,1],['P50','P95'],fontsize=11);ax2.invert_yaxis()
    mx=max(D['retrieval'][m]['overall']['timing']['p95_ms'] for m in ['lexical','fp32']);limit=math.ceil(mx/20)*20+25
    ax2.set_xlim(0,limit);ax2.set_xticks(range(0,int(limit),40));ax2.set_xlabel('耗时（ms）· 越低越好' if zh else 'Latency (ms) · lower is better',fontsize=11)
    fig.text(.045,.12,f"{D['created_at'][:10]} · {D['environment']['cpu']} / {D['environment']['memory_gib']:g} GiB · ONNX Runtime {D['environment']['onnxruntime_version']} / {D['environment']['execution_provider'].removesuffix('ExecutionProvider')}",fontsize=10,color=MUTED)
    fig.text(.045,.068,'合成开发语料；不是独立盲测。准确率按首轮唯一问题计算；计时不含启动、Electron 和大模型生成。' if zh else 'Synthetic development corpus, not a blind holdout. Accuracy: unique first-round queries. Timing excludes startup, Electron and LLM generation.',fontsize=9.5,color=MUTED)
    save(fig,'retrieval-tradeoff',lang)

KINDS={
 'legacy_detail':('历史细节','Legacy detail'),'legacy_cross_session':('历史跨会话','Legacy cross-session'),'detail':('事项细节','Task detail'),'cross_session':('跨会话','Cross-session'),'person':('人物','Person'),'confusion':('相似事项混淆','Confusable matters'),'time':('时间','Time'),'fallback_scope':('临时选择 / 作用域','Fallback / scope'),'legacy_boundary':('历史边界','Legacy boundary'),'late_import':('旧信息晚导入','Late import'),'version':('版本','Version'),'resource_move':('资源移动','Resource move')}

def categories(lang):
    zh=lang=='zh';fig=start(lang,(12,9.5))
    fig.text(.055,.95,'分场景看：收益并不均匀' if zh else 'By query category: gains are uneven',fontsize=22,weight='bold',color=INK)
    fig.text(.055,.906,'话题 Top-1；展示全部正例类别，样本数量随类别列出。' if zh else 'Topic Top-1 across every positive-query category, with sample counts.',fontsize=12,color=MUTED)
    fig.legend(handles=[Patch(color=BASE,label=labels(lang)[0]),Patch(color=RED,label=labels(lang)[1])],loc='upper left',bbox_to_anchor=(.05,.88),ncol=2,frameon=False,fontsize=11)
    ax=fig.add_axes([.295,.145,.64,.665]);clean(ax)
    keys=list(KINDS)
    for j,(mode,color) in enumerate([('lexical',BASE),('fp32',RED)]):
        vals=[D['retrieval'][mode]['by_kind'][k]['topic_top1']*100 for k in keys];ys=[i+(j-.5)*.28 for i in range(len(keys))]
        ax.barh(ys,vals,height=.235,color=color,zorder=3)
        for y,v in zip(ys,vals):ax.text(v+1.0,y,f'{v:.1f}%',va='center',fontsize=9)
    ax.set_yticks(range(len(keys)),[(KINDS[k][0] if zh else KINDS[k][1])+f"  (n={D['retrieval']['fp32']['by_kind'][k]['positive_queries']})" for k in keys],fontsize=11)
    ax.invert_yaxis();ax.set_xlim(0,112);ax.set_xticks([0,25,50,75,100]);ax.set_xlabel('话题 Top-1（%）' if zh else 'Topic Top-1 (%)',fontsize=11)
    fig.text(.055,.065,'小样本类别只作描述；例如 n=2 的 100% 不能推导真实场景可靠性。词法配置在重复轮次存在排序变化。' if zh else 'Small categories are descriptive: 100% at n=2 is not a reliability claim. Lexical rankings vary across repeated rounds.',fontsize=10,color=MUTED)
    fig.text(.055,.034,'来源：measurements.json（附可复核明细）' if zh else 'Source: measurements.json (auditable request-level data included)',fontsize=9,color=MUTED)
    save(fig,'category-results',lang)

for lang in ['zh','en']:
    rationale(lang);comparison(lang);categories(lang)
