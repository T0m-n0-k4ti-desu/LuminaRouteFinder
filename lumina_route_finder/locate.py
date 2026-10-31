"""Find a complete 5x10 diamond lattice without relying on surrounding UI."""
import cv2
import numpy as np


def diamond_centers(image):
    gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
    contours,_=cv2.findContours(cv2.Canny(gray,35,90),cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)
    points=[]
    for contour in contours:
        area=cv2.contourArea(contour)
        x,y,w,h=cv2.boundingRect(contour)
        if not (15<w<180 and 15<h<180 and .5<w/h<2 and .28<area/(w*h)<.7):
            continue
        q=cv2.approxPolyDP(contour,.035*cv2.arcLength(contour,True),True).reshape(-1,2)
        if len(q)!=4 or not cv2.isContourConvex(q):
            continue
        expected=np.array([[x+w/2,y],[x+w/2,y+h],[x,y+h/2],[x+w,y+h/2]])
        if max(min(np.linalg.norm(q-v,axis=1)) for v in expected)>max(w,h)*.19:
            continue
        point=np.array([x+(w-1)/2,y+(h-1)/2])
        if not any(np.linalg.norm(point-v)<max(2,min(w,h)*.06) for v in points):
            points.append(point)
    return np.asarray(points).reshape(-1,2)


def spacing_options(points,axis):
    other=1-axis
    delta=points[None,:,:]-points[:,None,:]
    distances=delta[:,:,axis][(np.abs(delta[:,:,other])<4)&(delta[:,:,axis]>=24)&(delta[:,:,axis]<=150)]
    if not len(distances):return []
    values,counts=np.unique(np.round(distances/2)*2,return_counts=True)
    order=np.argsort(counts)[::-1]
    result=[]
    for i in order:
        if all(abs(values[i]-v)>4 for v in result):
            near=distances[np.abs(distances-values[i])<3]
            result.append(float(np.median(near)))
        if len(result)==4:break
    return result


def find_grids(image):
    points=diamond_centers(image)
    if len(points)<40:return []
    grids=[]
    for dx in spacing_options(points,0):
        for dy in spacing_options(points,1):
            if not .65<dx/dy<1.55:continue
            offsets=np.array([(c*dx,r*dy) for r in range(10) for c in range(5)])
            anchors=np.concatenate([points,points-[dx,0],points-[0,dy],points-[dx,dy]])
            for anchor in anchors:
                predicted=anchor+offsets
                distance=np.linalg.norm((predicted[:,None,:]-points[None,:,:])/np.array([dx,dy]),axis=2)
                nearest=distance.argmin(axis=1)
                found=distance[np.arange(50),nearest]<.085
                if found.sum()<43:continue
                # Independently fit horizontal and vertical scales; contours have
                # half-pixel inclusive bounding boxes, hence the half-pixel correction.
                matched=points[nearest[found]]-.5
                cols=offsets[found,0]/dx
                rows=offsets[found,1]/dy
                sx,x0=np.linalg.lstsq(np.column_stack([cols,np.ones(len(cols))]),matched[:,0],rcond=None)[0]
                sy,y0=np.linalg.lstsq(np.column_stack([rows,np.ones(len(rows))]),matched[:,1],rcond=None)[0]
                # Avoid subpixel jitter in JPEG contours at the native size.
                sx,sy=round(sx*2)/2,round(sy*2)/2
                x0,y0=round(x0*2)/2,round(y0*2)/2
                if x0-20*sx/50 < -1 or y0-20*sy/50 < -1 or x0+4*sx+20*sx/50>image.shape[1]+1 or y0+9*sy+20*sy/50>image.shape[0]+1:
                    continue
                origin=(x0-29*sx/50,y0-25*sy/50)
                candidate=(origin,(sx/50,sy/50),float(found.mean()))
                if not any(np.linalg.norm(np.array(origin)-v[0])<min(sx,sy)*.4 for v in grids):
                    grids.append(candidate)
    # The same lattice may also match a hypothesis shifted by one row with
    # missing endpoints. Keep the best-supported overlapping hypothesis.
    distinct=[]
    for item in sorted(grids,key=lambda g:g[2],reverse=True):
        (x,y),(sx,sy),_=item
        if not any(abs(x-v[0][0])<100*max(sx,v[1][0]) and
                   abs(y-v[0][1])<150*max(sy,v[1][1]) for v in distinct):
            distinct.append(item)
    return distinct


def normalize(image,origin,scale,margin=0):
    ox,oy=origin;sx,sy=scale
    matrix=np.array([[1/sx,0,margin-ox/sx],[0,1/sy,margin-oy/sy]],dtype=np.float64)
    return cv2.warpAffine(image,matrix,(260+2*margin,500+2*margin),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_REPLICATE)
