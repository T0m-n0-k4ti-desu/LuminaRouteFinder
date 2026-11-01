"""Canonical board coordinates and exported path coordinates."""
def center(node):
    r, c = node
    return 29 + 50*c, 25 + 50*r

def export_solution(result):
    result = dict(result)
    result['paths'] = [[[r+1,c+1] for r,c in path] for path in result['paths']]
    return result


def candidates():
    for r in range(10):
        for c in range(5):
            if c < 4:
                yield (r,c), (r,c+1)
            if r < 9:
                for nc in range(max(0,c-1), min(5,c+2)):
                    yield (r,c), (r+1,nc)
