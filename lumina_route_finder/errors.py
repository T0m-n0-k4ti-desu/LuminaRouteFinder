"""Recognition failures shared by image input and board analysis."""
class RecognitionError(Exception):
    def __init__(self, issues, board=None, origin=None):
        self.issues, self.board, self.origin = issues, board, origin
        super().__init__('; '.join(i['code'] for i in issues))

def issue(code, message, box=None):
    item = {'code': code, 'message': message}
    if box is not None:
        item['board_box'] = list(map(int, box))
    return item
