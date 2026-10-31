import random
import unittest
from lumina_route_finder.solver import solve


def brute(nodes, edges):
    adj = {n: set() for n in nodes}
    for u, v in edges:
        adj[u].add(v)
        if u[0] == v[0]:
            adj[v].add(u)
    paths = []
    last = max(r for r, c in nodes)
    def walk(path):
        if path[-1][0] == last:
            paths.append(tuple(path))
        for nxt in adj[path[-1]]:
            if nxt not in path:
                walk(path + [nxt])
    for n in nodes:
        if n[0] == 0:
            walk([n])
    best = max(map(len, paths), default=0)
    return best, {p for p in paths if len(p) == best}


class SolverTests(unittest.TestCase):
    def test_random_against_independent_exhaustive_search(self):
        rng = random.Random(42)
        nodes = [(r, c) for r in range(3) for c in range(3)]
        candidates = [(u, v) for u in nodes for v in nodes
                      if (u[0] == v[0] and u[1] + 1 == v[1])
                      or (v[0] == u[0] + 1 and abs(v[1] - u[1]) <= 1)]
        for _ in range(100):
            edges = [e for e in candidates if rng.random() < .35]
            best, expected = brute(nodes, edges)
            result = solve(nodes, edges, limit=10000)
            self.assertEqual(result['max_count'] or 0, best)
            self.assertEqual(result['optimal_path_count'], len(expected))
            self.assertEqual({tuple(map(tuple, p)) for p in result['paths']}, expected)

    def test_best_start_is_not_leftmost_and_uses_top_horizontal_edges(self):
        nodes = [(r, c) for r in range(2) for c in range(5)]
        edges = [((0, 1), (0, 2)), ((0, 2), (0, 3)),
                 ((0, 1), (1, 1)), ((0, 0), (1, 0))]
        result = solve(nodes, edges)
        self.assertEqual(result['max_count'], 4)
        self.assertEqual(result['paths'], [[(0, 3), (0, 2), (0, 1), (1, 1)]])

    def test_crossing_does_not_create_turn(self):
        nodes = [(r, c) for r in range(2) for c in range(2)]
        result = solve(nodes, [((0, 0), (1, 1)), ((0, 1), (1, 0))])
        self.assertEqual(result['max_count'], 2)
        self.assertEqual(result['optimal_path_count'], 2)

    def test_no_path(self):
        self.assertEqual(solve([(0, 0), (1, 0)], [])['status'], 'no_path')

    def test_truncation(self):
        result = solve([(0, 0), (0, 1)], [((0, 0), (0, 1))], limit=1)
        self.assertEqual(result['max_count'], 2)
        self.assertEqual(result['optimal_path_count'], 2)
        self.assertTrue(result['paths_truncated'])

    def test_filtered_results_match_exhaustive_search(self):
        rng = random.Random(73)
        nodes = [(r,c) for r in range(3) for c in range(3)]
        candidates = [(u,v) for u in nodes for v in nodes
                      if (u[0]==v[0] and u[1]+1==v[1])
                      or (v[0]==u[0]+1 and abs(v[1]-u[1])<=1)]
        for _ in range(50):
            edges = [e for e in candidates if rng.random()<.5]
            types = {n:rng.choice(['a','b','c']) for n in nodes}
            for repeat,excluded in [(False,()),(True,()),(False,('a',)),(True,('a',))]:
                allowed = [n for n in nodes if types[n] not in excluded]
                valid = [(u,v) for u,v in edges if u in allowed and v in allowed
                         and (not repeat or types[u]!=types[v])]
                # Preserve the original start/goal rows even when an entire row is excluded.
                if not any(r==0 for r,c in allowed) or not any(r==2 for r,c in allowed):
                    best,expected = 0,set()
                else:
                    best,expected = brute(allowed,valid)
                result = solve(nodes,edges,limit=10000,node_types=types,
                               excluded_types=excluded,avoid_repeated=repeat)
                self.assertEqual(result['max_count'] or 0,best)
                self.assertEqual(result['optimal_path_count'],len(expected))
                self.assertEqual({tuple(map(tuple,p)) for p in result['paths']},expected)

    def test_filtering_requires_labels_and_can_block_entire_start_or_goal(self):
        nodes = [(0,0),(1,0)]
        edges = [(nodes[0],nodes[1])]
        with self.assertRaises(ValueError):
            solve(nodes,edges,avoid_repeated=True)
        for blocked in nodes:
            types = {n:('blocked' if n==blocked else 'ok') for n in nodes}
            self.assertEqual(solve(nodes,edges,node_types=types,excluded_types=['blocked'])['status'],'no_path')

    def test_upward_rejected(self):
        with self.assertRaises(ValueError):
            solve([(0, 0), (1, 0)], [((1, 0), (0, 0))])


if __name__ == '__main__':
    unittest.main()
