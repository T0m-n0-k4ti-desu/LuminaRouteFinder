"""Image viewport: zoom, scrolling, panning and ROI gestures.

Only callbacks cross into the application controller; this component knows
nothing about solving, output files, settings or worker threads.
"""
import base64
import tkinter as tk
import cv2
from ..errors import ErrorCode
from ..error_messages import error_message


class ImagePreview:
    def __init__(self, canvas, selecting, scale_text, *, can_interact, is_closed,
                 on_region_selected, on_notice):
        self.canvas = canvas
        self.scheduler = canvas.winfo_toplevel()
        self.selecting = selecting
        self.scale_text = scale_text
        self.can_interact = can_interact
        self.is_closed = is_closed
        self.on_region_selected = on_region_selected
        self.on_notice = on_notice
        self.input_image = self.image = self.photo = None
        self.region = self.drag_start = self.resize_id = None
        self.showing_input = self.panning = False
        self.zoom = None
        self.display_scale = 1.
        self.image_offset = (0, 0)
        canvas.bind('<Configure>', self.schedule_render)
        canvas.bind('<ButtonPress-1>', self.pointer_start)
        canvas.bind('<B1-Motion>', self.pointer_drag)
        canvas.bind('<ButtonRelease-1>', self.pointer_end)

    def input_point(self,event):
        x=(self.canvas.canvasx(event.x)-self.image_offset[0])/self.display_scale
        y=(self.canvas.canvasy(event.y)-self.image_offset[1])/self.display_scale
        h,w=self.input_image.shape[:2]
        return max(0,min(w,x)),max(0,min(h,y))

    def update_canvas_cursor(self):
        if not self.can_interact() or self.image is None:
            cursor = ''
        elif self.selecting.get() and self.showing_input:
            cursor = 'crosshair'
        elif self.panning:
            cursor = 'fleur'
        elif (self.image.shape[1]*self.display_scale > self.canvas.winfo_width() or
              self.image.shape[0]*self.display_scale > self.canvas.winfo_height()):
            cursor = 'hand2'
        else:
            cursor = ''
        self.canvas.configure(cursor=cursor)

    def pointer_start(self,event):
        self.panning = False
        self.drag_start = None
        if not self.can_interact() or self.image is None:
            return
        if self.selecting.get() and self.showing_input:
            self.selection_start(event)
        elif (self.image.shape[1]*self.display_scale > self.canvas.winfo_width() or
              self.image.shape[0]*self.display_scale > self.canvas.winfo_height()):
            self.canvas.scan_mark(event.x,event.y)
            self.panning = True
        self.update_canvas_cursor()

    def pointer_drag(self,event):
        if not self.can_interact():
            return
        if self.panning:
            self.canvas.scan_dragto(event.x,event.y,gain=1)
        elif self.selecting.get() and self.showing_input:
            self.selection_drag(event)

    def pointer_end(self,event):
        if self.panning:
            self.pointer_drag(event)
            self.panning = False
            self.update_canvas_cursor()
        elif self.selecting.get() and self.showing_input:
            self.selection_end(event)

    def selection_start(self,event):
        if not self.can_interact() or not self.selecting.get() or not self.showing_input or self.input_image is None:
            return
        self.drag_start=self.input_point(event)

    def selection_drag(self,event):
        if self.drag_start is not None and self.can_interact():
            self.draw_region((*self.drag_start,*self.input_point(event)))

    def selection_end(self,event):
        if self.drag_start is None or not self.can_interact():
            return
        import math
        a,b=self.drag_start,self.input_point(event)
        self.drag_start=None
        box=(math.floor(min(a[0],b[0])),math.floor(min(a[1],b[1])),
             math.ceil(max(a[0],b[0])),math.ceil(max(a[1],b[1])))
        if box[2]-box[0]<20 or box[3]-box[1]<20:
            self.on_notice(error_message(ErrorCode.REGION_TOO_SMALL))
            self.render()
            return
        self.region=box
        self.on_region_selected(box)

    def draw_region(self,box):
        self.canvas.delete('region')
        if box is None or not self.showing_input:
            return
        x1,y1,x2,y2=box
        sx,sy=self.image_offset
        scale=self.display_scale
        self.canvas.create_rectangle(sx+x1*scale,sy+y1*scale,sx+x2*scale,sy+y2*scale,
                                     outline='#e07800',width=3,tags='region')

    def schedule_render(self,event=None):
        if self.resize_id is not None:
            self.scheduler.after_cancel(self.resize_id)
        self.resize_id = self.scheduler.after(80,self.render)

    def render(self):
        self.panning = False
        if self.resize_id is not None:
            self.scheduler.after_cancel(self.resize_id)
        self.resize_id = None
        if self.is_closed():
            return
        self.canvas.delete('all')
        width,height=max(1,self.canvas.winfo_width()),max(1,self.canvas.winfo_height())
        if self.image is None:
            self.scale_text.set('')
            self.update_canvas_cursor()
            self.canvas.configure(scrollregion=(0,0,width,height))
            self.canvas.create_text(width/2,height/2,text='入力画像と解析結果をここに表示します',fill='#65768b',width=max(100,width-40))
            return
        ih,iw=self.image.shape[:2]
        fit=min(max(1,width-20)/iw,max(1,height-20)/ih)
        scale=fit if self.zoom is None else self.zoom
        self.display_scale=scale
        resized=cv2.resize(self.image,(max(1,round(iw*scale)),max(1,round(ih*scale))),
                           interpolation=cv2.INTER_AREA if scale<1 else cv2.INTER_NEAREST)
        ok,png=cv2.imencode('.png',resized)
        if not ok:
            return
        self.photo=tk.PhotoImage(master=self.canvas,data=base64.b64encode(png).decode('ascii'))
        dw,dh=resized.shape[1],resized.shape[0]
        self.image_offset=((max(width,dw)-dw)/2,(max(height,dh)-dh)/2)
        self.canvas.create_image(max(width,dw)/2,max(height,dh)/2,image=self.photo)
        self.draw_region(self.region)
        self.canvas.configure(scrollregion=(0,0,max(width,dw),max(height,dh)))
        self.scale_text.set(f'{scale:.0%}')
        self.update_canvas_cursor()

    def fit(self):
        self.zoom=None
        self.canvas.xview_moveto(0)
        self.canvas.yview_moveto(0)
        self.render()

    def change_zoom(self,factor):
        if self.image is not None:
            self.zoom=max(.1,min(4,getattr(self,'display_scale',1)*factor))
            self.render()
