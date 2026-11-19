import numpy as np
import time,io,base64
from pathlib import Path
from datetime import datetime

V='/master/version_6_styles'
Base=op('/atelier/spray_base').module.Spray
styles=op('/master/style_tools').module
PALETTE=op('/master/version_5_car/paint_engine').module.PALETTE

class WallPaint(Base):
    def __init__(self,saved=None,mask=None):
        self.glow=np.zeros((640,1024),np.float32);self.mass=np.zeros_like(self.glow);self.wet=np.zeros_like(self.glow)
        self.undo=[];self.phase=0.;self.style=0
        self.mask=mask
        super().__init__()
        if saved:
            data=np.load(io.BytesIO(base64.b64decode(saved)),allow_pickle=False)
            for name in ('ink','glow','mass','wet'):
                if name not in data:continue
                a=data[name]
                if a.shape!=getattr(self,name).shape or not np.isfinite(a).all():raise ValueError('Invalid saved wall paint')
                setattr(self,name,a.copy())
    def begin(self):
        self.undo.append((self.ink.copy(),self.glow.copy(),self.mass.copy(),self.wet.copy()));self.undo=self.undo[-6:]
    def clear(self):
        if hasattr(self,'ink') and self.ink.any():self.begin()
        super().clear();self.glow.fill(0);self.mass.fill(0);self.wet.fill(0)
    def undo_stroke(self):
        if self.undo:self.ink,self.glow,self.mass,self.wet=self.undo.pop();self.pointers={};self.drops=[];self.dirty=True
    def pointer(self,identifier,u,v,down,pressure=1,color=None):
        if down and str(identifier) not in self.pointers:
            if self.mask is not None:
                if not (0<=u<=1 and 0<=v<=1):return
                if not self.mask[round(v*639),round(u*1023)]:return
            self.begin()
        super().pointer(identifier,u,v,down,pressure,color)
    def add_drop(self,p):
        runs=styles.preset(self.style)[3]
        if not self.dripping or runs<=0:return
        # Separate wet patches along the lower edge can each release a rivulet.
        for _ in range(min(5,max(1,int(round(runs*3))))):
            q=p.copy();q['x']=float(np.clip(p['x']+self.rng.uniform(-.65,.65)*p['r'],0,1023))
            q['y']=max(0,p['y']-self.rng.uniform(.1,.35)*p['r'])
            if self.ink[int(q['y']),int(q['x']),3]>.65:super().add_drop(q)
    def stamp(self,x,y,r,color,dose,drip=False):
        r=max(1,r);extent=r*1.8
        x0,x1=max(0,int(x-extent-1)),min(1024,int(x+extent+2));y0,y1=max(0,int(y-extent-1)),min(640,int(y+extent+2))
        if x0>=x1 or y0>=y1:return
        yy,xx=np.mgrid[y0:y1,x0:x1].astype(np.float32)
        style=0 if drip else self.style
        profile,col=styles.brush(style,(xx-x)/r,(yy-y)/r,color,self.rng,self.phase)
        gain,emission,relief,runs=styles.preset(style)
        if not drip:self.phase=(self.phase+.008)%1
        if self.mask is not None:
            profile=profile*self.mask[y0:y1,x0:x1]
        alpha=(1-np.exp(-dose*profile*gain)).astype(np.float32)
        region=self.ink[y0:y1,x0:x1];a=alpha[...,None]
        region[:,:,:3]=col*a+region[:,:,:3]*(1-a);region[:,:,3]=alpha+region[:,:,3]*(1-alpha)
        g=self.glow[y0:y1,x0:x1];g[:]=emission*alpha+g*(1-alpha)
        h=self.mass[y0:y1,x0:x1];h[:]=np.minimum(2,h+dose*profile*relief*.05)
        self.wet[y0:y1,x0:x1]=np.minimum(1,self.wet[y0:y1,x0:x1]+alpha*.65)
        self.dirty=True
    def advance(self,dt):
        super().advance(dt)
        if self.wet.max()>.0001:self.wet*=np.exp(-dt/12);self.dirty=True
    def surface_image(self):
        a=np.zeros((640,1024,4),np.float32);a[:,:,0]=self.glow;a[:,:,1]=self.mass;a[:,:,2]=self.wet;a[:,:,3]=1;return a

saved_surfaces=op(V).storage.get('saved_surfaces',{})
engine=WallPaint(saved_surfaces.get('image',op(V).storage.get('saved_paint')))
surfaces={'image':engine}
previous_time=time.perf_counter();button_states={}

def select_surface(key,mask_top=None):
    global engine
    if key not in surfaces:
        mask=None
        if mask_top is not None:
            pixels=mask_top.numpyArray(delayed=False)[:,:,0]
            rows=np.rint(np.linspace(0,pixels.shape[0]-1,640)).astype(int)
            columns=np.rint(np.linspace(0,pixels.shape[1]-1,1024)).astype(int)
            mask=pixels[np.ix_(rows,columns)]>.5
        surfaces[key]=WallPaint(saved_surfaces.get(key),mask)
    if engine is not surfaces[key]:
        engine.drops.clear()
        engine=surfaces[key]
        engine.dirty=True

def save_surfaces():
    saved=saved_surfaces.copy()
    for key,surface in surfaces.items():
        if not surface.ink.any():
            saved.pop(key,None)
            continue
        buf=io.BytesIO()
        np.savez_compressed(buf,ink=surface.ink,mass=surface.mass,glow=surface.glow,wet=surface.wet)
        saved[key]=base64.b64encode(buf.getvalue()).decode()
    op(V).storage['saved_surfaces']=saved
    op(V).storage.pop('saved_paint',None)

def settings():
    c=op(V+'/STYLE_CONTROLS').par
    engine.style=int(c.Style);engine.radius=float(c.Radius);engine.flow=float(c.Flow)
    engine.paint_color=tuple(float(getattr(c,'Color'+s)) for s in 'rgb')
    engine.dripping=bool(c.Runs)

def action(name):
    c=op(V+'/STYLE_CONTROLS').par
    if name.startswith('color'):
        for s,value in zip('rgb',PALETTE[int(name[5:])]):setattr(c,'Color'+s,value)
    elif name in ('small','medium','large'):c.Radius={'small':9,'medium':20,'large':38}[name]
    elif name=='clear':engine.clear()
    elif name=='undo':engine.undo_stroke()
    elif name=='drips':c.Runs=not bool(c.Runs)
    elif name=='save':
        folder=Path(project.folder)/'Style paintings';folder.mkdir(exist_ok=True)
        op(V+'/out1').save(str(folder/('Graffiti_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.png')))
        op(V+'/paint_studio/status').par.text='Saved in Style paintings. File > Save preserves editable paint in the project.'
    settings()

def touch_event(event,down):
    settings();key='touch:'+str(event.id)
    if down:
        if key not in engine.pointers:engine.pointer(key,event.downu,event.downv,True)
        engine.pointer(key,event.u,event.v,True)
    else:
        if key in engine.pointers:engine.pointer(key,event.u,event.v,True)
        engine.pointer(key,0,0,False)

def tick():
    global previous_time
    now=time.perf_counter();dt=min(.05,now-previous_time);previous_time=now
    p=op(V+'/paint_studio');styles.poll(op(V),button_states)
    for name in ['color'+str(i) for i in range(8)]+['small','medium','large','drips','undo','clear','save']:
        down=bool(p.op(name).panel.select)
        if down and not button_states.get(name,False):action(name)
        button_states[name]=down
    settings()
    if not op('/master/master_window').isOpen:engine.pointers.clear()
    engine.advance(dt)
    if engine.dirty:
        op(V+'/paint_color').cook(force=True);op(V+'/paint_surface').cook(force=True);engine.dirty=False
    p.op('drips').par.text='DRIPS ON' if engine.dripping else 'DRIPS OFF'
