import io,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from PIL import Image
from lumina_route_finder.route_export import candidate_image,save_candidate,dib_bytes
class ExportTests(unittest.TestCase):
    def test_export_uses_selected_page_and_highlight_and_survives_cleanup(self):
        from lumina_route_finder.session import SessionOutputs
        board=np.zeros((500,260,3),dtype=np.uint8)
        result={'status':'ok','paths':[[[1,1],[2,1]],[[1,2],[2,2]]]}
        a=candidate_image(board,result,0);b=candidate_image(board,result,1)
        self.assertFalse(np.array_equal(a,b))
        self.assertFalse(np.array_equal(b,candidate_image(board,result,1,0)))
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);out=root/'outputs';out.mkdir();session=SessionOutputs(out)
            target=root/'chosen.png';save_candidate(target,board,result,1,out)
            session.cleanup();self.assertTrue(target.exists())
            with self.assertRaises(ValueError):save_candidate(out/'route.png',board,result,0,out)
        data=dib_bytes(b)
        # A BMP file header can wrap the DIB for independent Pillow decoding.
        import struct
        bmp=b'BM'+struct.pack('<IHHI',len(data)+14,0,0,54)+data
        image=Image.open(io.BytesIO(bmp));self.assertEqual(image.size,(520,1000));image.load()
if __name__=='__main__':unittest.main()
