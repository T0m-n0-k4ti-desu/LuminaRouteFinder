"""Longest simple paths on a downward layered board."""
from collections import defaultdict


def solve(nodes, edges, limit=20):
    """Return optimal paths; horizontal travel is bidirectional, upward travel forbidden.

    Keep exact optimal path count, but materialize at most ``limit`` examples.
    Nodes are (zero-based row, column) tuples.
    """
    if limit < 1:
        raise ValueError('limit must be positive')
    nodes = set(map(tuple, nodes))
    if not nodes:
        return {'status': 'no_path', 'max_count': None, 'paths': [], 'optimal_path_count': 0}
    rows = sorted({r for r, _ in nodes})
    if rows != list(range(rows[-1] + 1)):
        raise ValueError('rows must be contiguous from zero')
    horizontal = defaultdict(set)
    down = defaultdict(set)
    for u, v in edges:
        u, v = tuple(u), tuple(v)
        if u not in nodes or v not in nodes or u == v:
            raise ValueError('invalid edge endpoint')
        if u[0] == v[0]:
            horizontal[u].add(v)
            horizontal[v].add(u)
        elif v[0] == u[0] + 1:
            down[u].add(v)
        else:
            raise ValueError('edges must be horizontal or one row downward')
    # state = (best length, exact count, bounded example paths)
    states = {n: (0, 1, [[]]) for n in sorted(nodes) if n[0] == 0}
    for row in rows:
        ends = {}
        def visit(path, previous):
            n = path[-1]
            length = previous[0] + len(path)
            examples = [prefix + path for prefix in previous[2]][:limit]
            current = ends.get(n)
            if current is None or length > current[0]:
                ends[n] = (length, previous[1], examples)
            elif length == current[0]:
                ends[n] = (length, current[1] + previous[1], (current[2] + examples)[:limit])
            for nxt in sorted(horizontal[n]):
                if nxt not in path:
                    visit(path + [nxt], previous)
        for start, previous in sorted(states.items()):
            visit([start], previous)
        if row == rows[-1]:
            break
        states = {}
        for end, value in sorted(ends.items()):
            for nxt in sorted(down[end]):
                old = states.get(nxt)
                if old is None or value[0] > old[0]:
                    states[nxt] = value
                elif value[0] == old[0]:
                    states[nxt] = (old[0], old[1] + value[1], (old[2] + value[2])[:limit])
    if not ends:
        return {'status': 'no_path', 'max_count': None, 'paths': [], 'optimal_path_count': 0}
    best = max(v[0] for v in ends.values())
    winners = [v for _, v in sorted(ends.items()) if v[0] == best]
    paths = [path for v in winners for path in v[2]][:limit]
    count = sum(v[1] for v in winners)
    return {'status': 'ok', 'max_count': best, 'paths': paths,
            'optimal_path_count': count, 'paths_truncated': count > len(paths)}
