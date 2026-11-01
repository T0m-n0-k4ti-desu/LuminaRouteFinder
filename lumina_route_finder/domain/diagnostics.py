"""Pure reachability diagnostics and bounded, explicit relaxation proposals."""
from collections import deque
from .solver import solve


def effective_exclusions(options):return tuple(options.get('excluded_types',())) if options.get('exclude_enabled') else ()


def validate_types(labels,options):
    if (options.get('avoid_repeated') or effective_exclusions(options) or options.get('objective','count')!='count') and any(v is None for v in labels.values()):
        raise ValueError('コンテンツ種類が未確定です。認識確認で種類を指定してください。')


def diagnose(nodes,edges,labels,options):
    nodes=set(nodes);validate_types(labels,options);excluded=set(effective_exclusions(options))
    blocked={n for n in nodes if labels.get(n) in excluded};adj={n:set() for n in nodes};denied=[]
    for u,v in edges:
        directions=[(u,v),(v,u)] if u[0]==v[0] else [(u,v)]
        for a,b in directions:
            reason='excluded' if a in blocked or b in blocked else ('repeat' if options.get('avoid_repeated') and labels[a]==labels[b] else None)
            if reason:denied.append((a,b,reason))
            else:adj[a].add(b)
    reachable={n for n in nodes if n[0]==0 and n not in blocked};queue=deque(reachable)
    while queue:
        for n in adj[queue.popleft()]-reachable:reachable.add(n);queue.append(n)
    furthest=max((n[0]+1 for n in reachable),default=0);goal=max(n[0] for n in nodes)+1
    def export(n):return [n[0]+1,n[1]+1]
    return {'furthest_stage':furthest,'goal_stage':goal,'goal_reachable':furthest==goal,
            'reachable_nodes':[export(n) for n in sorted(reachable)],'blocked_nodes':[export(n) for n in sorted(blocked)],
            'frontier_edges':[{'from':export(a),'to':export(b),'reason':reason} for a,b,reason in denied if a in reachable],
            'terminal_nodes':[export(n) for n in sorted(reachable) if n[0]+1==furthest]}


def relaxation_variants(options):
    base=dict(options);base['weights']=dict(options.get('weights',{}));base['excluded_types']=list(options.get('excluded_types',[]))
    proposals=[('現在の条件',base)]
    if base.get('avoid_repeated'):proposals.append(('連続禁止を解除',dict(base,avoid_repeated=False)))
    for key in effective_exclusions(base):
        remaining=[k for k in base['excluded_types'] if k!=key]
        proposals.append(('除外解除: '+key,dict(base,excluded_types=remaining,exclude_enabled=bool(remaining))))
    if base.get('avoid_repeated') or effective_exclusions(base):proposals.append(('除外・連続禁止を解除',dict(base,avoid_repeated=False,exclude_enabled=False)))
    result=[];seen=set()
    for name,values in proposals:
        key=(bool(values.get('avoid_repeated')),tuple(sorted(effective_exclusions(values))))
        if key not in seen:result.append((name,values));seen.add(key)
    return result


def compare_relaxations(nodes,edges,labels,options,cancel=None,progress=None):
    rows=[]
    for name,values in relaxation_variants(options):
        if cancel is not None and cancel.is_set():
            from .jobs import AnalysisCancelled
            raise AnalysisCancelled()
        if progress:progress(name)
        try:
            validate_types(labels,values)
            result=solve(nodes,edges,limit=1,node_types=labels,excluded_types=effective_exclusions(values),avoid_repeated=values.get('avoid_repeated',False),
                         fallback_priority=None if values.get('fallback_priority')=='none' else values.get('fallback_priority','stage'),
                         objective=values.get('objective','count'),weights=values.get('weights'),cancel=cancel)
        except ValueError as exc:result={'status':'error','message':str(exc)}
        if result['status']=='no_path':result['reached_stage']=diagnose(nodes,edges,labels,values)['furthest_stage']
        rows.append({'name':name,'options':values,'result':result})
    return rows
