import random,unittest
from lumina_route_finder.domain.solver import solve
class WeightTests(unittest.TestCase):
    def test_objectives_match_exhaustive_paths_including_negative_weights(self):
        rng=random.Random(392)
        nodes=[(r,c) for r in range(3) for c in range(3)]
        candidates=[(u,v) for u in nodes for v in nodes if (u[0]==v[0] and v[1]==u[1]+1) or (v[0]==u[0]+1 and abs(v[1]-u[1])<=1)]
        for _ in range(50):
            edges=[e for e in candidates if rng.random()<.4];types={n:rng.choice(['a','b']) for n in nodes};weights={'a':rng.randint(-3,4),'b':rng.randint(-3,4)}
            adj={n:set() for n in nodes}
            for u,v in edges:
                adj[u].add(v)
                if u[0]==v[0]:adj[v].add(u)
            paths=[]
            def walk(p):
                paths.append(tuple(p))
                for n in adj[p[-1]]:
                    if n not in p:walk(p+[n])
            for n in nodes:
                if n[0]==0:walk([n])
            goals=[p for p in paths if p[-1][0]==2]
            for objective in ('count','weight','count_then_weight'):
                def metric(p):
                    score=sum(weights[types[n]] for n in p)
                    return (score,len(p)) if objective=='weight' else (len(p),score if objective=='count_then_weight' else 0)
                for priority in ('stage','count'):
                    pool=goals or paths
                    key=metric if goals or priority=='count' else lambda p:(p[-1][0],metric(p))
                    best=max(map(key,pool));expected={p for p in pool if key(p)==best}
                    result=solve(nodes,edges,limit=10000,node_types=types,objective=objective,weights=weights,fallback_priority=priority)
                    self.assertEqual({tuple(p) for p in result['paths']},expected)
                    self.assertEqual(result['optimal_path_count'],len(expected))
                    self.assertTrue(all(len(p)==result['max_count'] for p in result['paths']))
    def test_decimal_weights_have_exact_ties(self):
        nodes=[(0,0),(0,1),(1,0),(1,1)]
        edges=[((0,0),(1,0)),((0,1),(1,1))]
        labels={(0,0):'a',(1,0):'b',(0,1):'c',(1,1):'d'}
        result=solve(nodes,edges,node_types=labels,objective='weight',weights={'a':.1,'b':.2,'c':.3,'d':0})
        self.assertEqual(result['optimal_path_count'],2)

    def test_invalid_weights(self):
        for value in (float('nan'),float('inf'),True,1000001):
            with self.assertRaises(ValueError):solve([(0,0)],[],node_types={(0,0):'a'},objective='weight',weights={'a':value})
if __name__=='__main__':unittest.main()
