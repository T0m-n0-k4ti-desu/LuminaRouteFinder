"""Canonical board coordinates and exported path coordinates."""
def center(node):
    r, c = node
    return 29 + 50*c, 25 + 50*r

def export_solution(result):
    result = dict(result)
    result['paths'] = [[[r+1,c+1] for r,c in path] for path in result['paths']]
    return result
