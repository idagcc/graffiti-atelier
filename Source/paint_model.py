import numpy as np
import math,time,base64,io
from pathlib import Path
from datetime import datetime

V='/master/version_5_car'
PALETTE=[(.93,.035,.045),(.99,.39,.025),(.98,.8,.09),(.06,.65,.42),(.025,.28,.85),(.52,.1,.77),(.93,.92,.86),(.02,.024,.03)]
def ctrl():return op(V+'/CAR_CONTROLS').par

class CarPaint:
    def __init__(self,restore=True):
        data=np.load(io.BytesIO(base64.b64decode(op(V+'/surface_lookup').text)))
        self.valid=data['valid'];self.flat=np.flatnonzero(self.valid)
        padded=np.full((1024,1024),-1,np.int32);padded.reshape(-1)[self.flat]=self.flat
        for _ in range(2):
            prev=padded.copy()
            for axis,shift in [(0,1),(0,-1),(1,1),(1,-1)]:
                rolled=np.roll(prev,shift,axis);mask=(padded<0)&(rolled>=0);padded[mask]=rolled[mask]
        self.padding_dest=np.flatnonzero((padded>=0)&~self.valid)
        self.padding_src=padded.reshape(-1)[self.padding_dest]
        self.pos=data['position'].reshape(-1,3)[self.flat];self.norm=data['normal'].reshape(-1,3)[self.flat]
        self.origin=self.pos.min(0)-.5;self.cell=.16
        cells=np.floor((self.pos-self.origin)/self.cell).astype(np.int32)
        assert cells.max()<128
        keys=cells[:,0]+cells[:,1]*128+cells[:,2]*16384
        order=np.argsort(keys);unique,starts,counts=np.unique(keys[order],return_index=True,return_counts=True)
        self.buckets={int(k):order[start:start+count] for k,start,count in zip(unique,starts,counts)}
        self.rng=np.random.default_rng(319)
        self.ink=np.zeros((len(self.flat),4),np.float32)
        self.mass=np.zeros(len(self.flat),np.float32);self.wet=np.zeros_like(self.mass);self.glow=np.zeros_like(self.mass);self.phase=0.
        self.pointers={};self.drops=[];self.undo=[];self.dirty=True
        self.base=np.array([.80,.81,.78],np.float32)
        saved=op(V).storage.get('saved_paint') if restore else None
        if saved is not None:
            saved=np.load(io.BytesIO(base64.b64decode(saved)),allow_pickle=False)
            for name in ('ink','mass','wet'):
                array=np.asarray(saved[name],dtype=np.float32)
                if array.shape!=getattr(self,name).shape or not np.isfinite(array).all():
                    raise ValueError('Saved car paint does not match this surface')
                setattr(self,name,array.copy())
            if 'glow' in saved:self.glow=saved['glow'].copy()
    def candidates(self,p,r):
        lo=np.floor((p-r-self.origin)/self.cell).astype(int);hi=np.floor((p+r-self.origin)/self.cell).astype(int)
        chunks=[self.buckets.get(x+y*128+z*16384) for z in range(lo[2],hi[2]+1) for y in range(lo[1],hi[1]+1) for x in range(lo[0],hi[0]+1)]
        chunks=[x for x in chunks if x is not None]
        return np.concatenate(chunks) if chunks else np.empty(0,int)
    def stamp(self,p,n,r,col,dose,drip=False,style=None):
        ids=self.candidates(p,r*1.8)
        if not len(ids):return
        delta=self.pos[ids]-p;d2=np.sum(delta*delta,axis=1)/(r*r)
        keep=(d2<3.1)&((self.norm[ids]@n)>.2)&(np.abs(delta@n)<r*.7)
        ids=ids[keep];d2=d2[keep];delta=delta[keep]
        if not len(ids):return
        style=int(op(V+'/STYLE_CONTROLS').par.Style) if style is None else style
        shared=op('/master/style_tools').module
        gain,emission,relief,runs=shared.preset(style)
        if drip:profile=np.exp(-d2*2.6)
        else:
            axis=np.cross(n,[0.,1.,0.])
            if np.linalg.norm(axis)<.01:axis=np.cross(n,[1.,0.,0.])
            axis/=np.linalg.norm(axis);up=np.cross(n,axis)
            profile,col=shared.brush(style,delta@axis/r,delta@up/r,col,self.rng,self.phase)
            self.phase=(self.phase+.008)%1
        dose*=gain
        a=(1-np.exp(-dose*profile)).astype(np.float32)
        self.ink[ids,:3]=np.asarray(col)*a[:,None]+self.ink[ids,:3]*(1-a[:,None])
        self.ink[ids,3]=a+self.ink[ids,3]*(1-a)
        self.glow[ids]=emission*a+self.glow[ids]*(1-a)
        self.mass[ids]=np.minimum(6,self.mass[ids]+dose*profile*.16*relief)
        self.wet[ids]=np.minimum(8,self.wet[ids]+dose*profile)
        self.dirty=True
        runs*=float(ctrl().Runs)
        eligible=ids[(self.wet[ids]>1.3)&(np.abs(self.norm[ids,1])<.92)]
        # ponytail: up to 96 surface-following rivulets; this is a wet-paint approximation, not a Navier-Stokes solver.
        if not drip and runs>0 and len(eligible) and len(self.drops)<96:
            for idx in self.rng.choice(eligible,min(3,len(eligible)),replace=False):
                if self.rng.random()>min(.85,dose*runs*1.6):continue
                point=self.pos[idx].copy()
                if any(np.linalg.norm(d['p']-point)<.035 for d in self.drops):continue
                self.drops.append(dict(style=style,p=point,n=self.norm[idx].copy(),r=self.rng.uniform(.012,.026),speed=self.rng.uniform(.026,.065),life=self.rng.uniform(4,14),age=0.,col=np.asarray(col).copy(),phase=self.rng.uniform(0,6.28)))
                self.wet[idx]=max(0,self.wet[idx]-.55)
    def begin(self):
        self.undo.append((self.ink.copy(),self.mass.copy(),self.wet.copy(),self.glow.copy()))
        self.undo=self.undo[-6:]
    def clear(self):
        self.begin();self.ink.fill(0);self.mass.fill(0);self.wet.fill(0);self.glow.fill(0);self.drops=[];self.pointers={};self.dirty=True
    def undo_stroke(self):
        if self.undo:self.ink,self.mass,self.wet,self.glow=self.undo.pop();self.drops=[];self.pointers={};self.dirty=True
    def advance(self,dt):
        if self.wet.max()>.0001:
            self.wet*=math.exp(-dt*3/max(1,float(ctrl().Drytime)));self.dirty=True
        alive=[]
        for d in self.drops:
            d['age']+=dt
            if d['age']>d['life']:continue
            n=d['n'];gravity=np.array([0.,-1.,0.]);tangent=gravity-n*np.dot(gravity,n)
            speed=d['speed']*float(ctrl().Runs)*max(.12,1-d['age']/d['life'])
            sideways=np.cross(n,gravity)*math.sin(d['phase']+d['age']*2.)*.10
            target=d['p']+(tangent+sideways)*speed*dt
            ids=self.candidates(target,.08)
            if not len(ids):continue
            dist=np.sum((self.pos[ids]-target)**2,axis=1)+np.maximum(0,.4-self.norm[ids]@n)*.1
            j=ids[np.argmin(dist)]
            if np.linalg.norm(self.pos[j]-target)>.075:continue
            normal=self.norm[j];target+=normal*np.dot(self.pos[j]-target,normal)
            d['p']=target;d['n']=normal
            self.stamp(target,normal,d['r'],d['col'],min(.3,dt*3.5),True,style=d.get('style',0))
            alive.append(d)
        self.drops=alive
    def emission_image(self):
        image=np.zeros((1024,1024,4),np.float32);image[:,:,3]=1
        image.reshape(-1,4)[self.flat,:3]=self.ink[:,:3]/np.maximum(self.ink[:,3:4],.0001)*self.glow[:,None]*float(op(V+'/STYLE_CONTROLS').par.Glow)
        return self.pad(image)
    def color_image(self):
        image=np.ones((1024,1024,4),np.float32);image[:,:,:3]=self.base
        image.reshape(-1,4)[self.flat,:3]=self.ink[:,:3]+self.base*(1-self.ink[:,3:4])
        return self.pad(image)
    def surface_image(self):
        image=np.ones((1024,1024,4),np.float32);image[:,:,0]=.22;image[:,:,1:3]=0
        wetness=np.clip(self.wet,0,1)
        rough=float(ctrl().Dryroughness)*(1-wetness)+float(ctrl().Wetroughness)*wetness
        rows=image.reshape(-1,4);rows[self.flat,0]=.22*(1-self.ink[:,3])+rough*self.ink[:,3]
        rows[self.flat,1]=self.mass*float(ctrl().Relief);rows[self.flat,2]=wetness
        return self.pad(image)
    def pad(self,image):
        # Two texels of island-edge padding prevent visible dark lines at UV seams.
        rows=image.reshape(-1,4);rows[self.padding_dest]=rows[self.padding_src]
        return image

engine=CarPaint();previous_time=time.perf_counter();button_states={};last_upload=0.;last_right=None
def labels():
    p=op(V+'/paint_studio');rot=bool(ctrl().Rotate)
    p.op('paint').par.bgcolorr,p.op('paint').par.bgcolorg,p.op('paint').par.bgcolorb=(.13,.32,.25) if not rot else (.12,.14,.16)
    p.op('rotate').par.bgcolorr,p.op('rotate').par.bgcolorg,p.op('rotate').par.bgcolorb=(.13,.32,.25) if rot else (.12,.14,.16)
def action(name):
    c=ctrl()
    if name.startswith('color'):
        for s,value in zip('rgb',PALETTE[int(name[5:])]):getattr(c,'Color'+s).val=value
    elif name=='clear':engine.clear()
    elif name=='undo':engine.undo_stroke()
    elif name=='paint':c.Rotate=False
    elif name=='rotate':c.Rotate=True
    elif name=='turnleft':c.Yaw=float(c.Yaw)-30
    elif name=='turnright':c.Yaw=float(c.Yaw)+30
    elif name=='closer':c.Distance=float(c.Distance)-.5
    elif name=='farther':c.Distance=float(c.Distance)+.5
    elif name=='home':c.Yaw=38;c.Pitch=16;c.Distance=8.3
    elif name=='save':save_project_paint()
    labels();engine.dirty=True
def save_project_paint():
    folder=Path(project.folder)/'Car paintings';folder.mkdir(exist_ok=True)
    name=datetime.now().strftime('Car_%Y%m%d_%H%M%S_%f')
    op(V+'/out1').save(str(folder/(name+'.png')))
    op(V+'/paint_color').save(str(folder/(name+'_texture.png')))
    np.savez_compressed(folder/(name+'_paint.npz'),ink=engine.ink,mass=engine.mass,wet=engine.wet,glow=engine.glow)
    op(V+'/paint_studio/status').par.text='Saved view, paint texture and editable paint data in Car paintings.'
def pick(u,v):
    if not (0<=u<=1 and 0<=v<=1):return None
    event=op(V+'/surface_pick').pick(u,v)
    if not event.pickOp or event.pickOp.parent().name!='car_body':return None
    return np.array([event.pos.x,event.pos.y,event.pos.z],dtype=np.float32),np.array([event.normal.x,event.normal.y,event.normal.z],dtype=np.float32)
def paint_at(u,v,dt,previous=None):
    hit=pick(u,v)
    if hit is None:return None
    p,n=hit;c=ctrl();r=float(c.Size);color=[float(getattr(c,'Color'+s)) for s in 'rgb'];dose=min(.7,max(.07,dt*11))*float(c.Flow)
    if previous is not None and np.linalg.norm(previous-p)<1.2:
        count=min(32,max(1,int(np.linalg.norm(previous-p)/(r*.3))))
        for t in np.linspace(0,1,count+1)[1:]:engine.stamp(previous*(1-t)+p*t,n,r,color,dose)
    else:engine.stamp(p,n,r,color,dose)
    return p
def touch_event(event,down):
    key=str(event.id);u,v=float(event.u),float(event.v)
    if not down:engine.pointers.pop(key,None);return
    old=engine.pointers.get(key)
    if old is None:
        if not bool(ctrl().Rotate):engine.begin()
        old=dict(u=float(event.downu),v=float(event.downv),point=None,rot=bool(ctrl().Rotate))
        if not old['rot']:old['point']=paint_at(old['u'],old['v'],.018)
    if old['rot']:
        ctrl().Yaw=float(ctrl().Yaw)-(u-old['u'])*220;ctrl().Pitch=float(ctrl().Pitch)-(v-old['v'])*100
    else:old['point']=paint_at(u,v,.018,old['point'])
    old['u']=u;old['v']=v;engine.pointers[key]=old
def tick():
    global previous_time,last_upload,last_right
    now=time.perf_counter();dt=min(.06,max(0,now-previous_time));previous_time=now
    c=ctrl();p=op(V+'/paint_studio');canvas=p.op('canvas')
    op('/master/style_tools').module.poll(op(V),button_states)
    for name in ['color'+str(i) for i in range(8)]+['paint','rotate','undo','clear','save','turnleft','turnright','closer','farther','home']:
        down=bool(p.op(name).panel.select)
        if down and not button_states.get(name,False):action(name)
        button_states[name]=down
    if not op('/master/master_window').isOpen:engine.pointers.clear()
    right=bool(canvas.panel.rselect)
    if right:
        uv=(float(canvas.panel.u),float(canvas.panel.v))
        if last_right:
            c.Yaw=float(c.Yaw)-(uv[0]-last_right[0])*220;c.Pitch=float(c.Pitch)-(uv[1]-last_right[1])*100
        last_right=uv;engine.pointers.clear()
    else:last_right=None
    for contact in list(engine.pointers.values()):
        if not contact['rot'] and not right:contact['point']=paint_at(contact['u'],contact['v'],dt,contact['point'])
    engine.advance(dt)
    if engine.dirty and now-last_upload>1/30:
        op(V+'/paint_color').cook(force=True);op(V+'/wetness_height').cook(force=True);op(V+'/paint_emission').cook(force=True)
        last_upload=now;engine.dirty=False
    labels()
