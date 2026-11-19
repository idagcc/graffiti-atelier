import math
import time
from pathlib import Path
from datetime import datetime
import numpy as np

W,H=1024,640
PALETTE=[(.98,.19,.40),(.98,.42,.075),(.98,.85,.12),(.24,.86,.62),(.16,.59,.98),(.64,.31,.96),(.96,.95,.88)]
SIZES={'small':12,'medium':25,'large':46}


class Spray:
    def __init__(self):
        self.rng=np.random.default_rng(17)
        self.ink=np.zeros((H,W,4),np.float32)
        self.color=0
        self.radius=25
        self.dripping=True
        self.density=1.0
        self.softness=.49
        self.grain=1.0
        self.flow=6.0
        self.paint_color=None
        self.drip_speed=1.0
        self.drip_width=1.0
        self.drip_life=1.0
        self.drip_threshold=.78
        self.drip_delay=.48
        self.max_drips=80
        self.clear()

    def clear(self):
        self.ink.fill(0)
        self.pointers={}
        self.drops=[]
        self.dirty=True

    def stamp(self,x,y,r,color,dose,drip=False):
        extent=r*(1.18 if drip else 2.0)
        x0,x1=max(0,int(x-extent-1)),min(W,int(x+extent+2))
        y0,y1=max(0,int(y-extent-1)),min(H,int(y+extent+2))
        if x0>=x1 or y0>=y1:
            return
        yy,xx=np.mgrid[y0:y1,x0:x1].astype(np.float32)
        d2=((xx-x)**2+(yy-y)**2)/(r*r)
        if drip:
            alpha=np.clip((1-np.sqrt(d2))*r*1.3,0,1)*min(.9,dose)
        else:
            dose*=self.density
            profile=np.exp(-(6-self.softness*5.5)*d2)*np.clip(2-np.sqrt(d2),0,1)
            grain=self.rng.random(d2.shape,dtype=np.float32)
            droplets=(grain>1-profile*.27*self.grain).astype(np.float32)
            alpha=1-np.exp(-dose*(profile*.83+droplets*1.5))
        a=alpha[...,None]
        region=self.ink[y0:y1,x0:x1]
        region[...,:3]=np.asarray(color,np.float32)*a+region[...,:3]*(1-a)
        region[...,3]=alpha+region[...,3]*(1-alpha)
        self.dirty=True

    def pointer(self,identifier,u,v,down,pressure=1.0,color=None):
        """Common input: normalized UV, bottom-left origin, contact ID and spray gate."""
        key=str(identifier)
        if not down:
            self.pointers.pop(key,None)
            return
        try:
            u,v,pressure=float(u),float(v),float(pressure)
        except (ValueError,TypeError):
            self.pointers.pop(key,None)
            return
        if not all(math.isfinite(n) for n in (u,v,pressure)) or not (0<=u<=1 and 0<=v<=1):
            self.pointers.pop(key,None)
            return
        pressure=min(1,max(0,pressure))
        if pressure==0:
            self.pointers.pop(key,None)
            return
        now=time.perf_counter()
        x,y=u*(W-1),v*(H-1)
        old=self.pointers.get(key)
        if old is None:
            # ponytail: cap live contacts at ten, matching the installation's current touch scope.
            if len(self.pointers)>=10:
                return
            color = color if color is not None else self.paint_color or PALETTE[self.color]
            old=dict(x=x,y=y,hold=0.,travel=0.,last=now,r=self.radius,color=color,pressure=pressure)
            self.pointers[key]=old
            self.stamp(x,y,old['r'],old['color'],.85*pressure)
        else:
            dist=math.hypot(x-old['x'],y-old['y'])
            if dist>.1:
                count=max(1,math.ceil(dist/max(2,old['r']*.30)))
                dose=min(.75,.075+max(.002,min(.05,now-old['last']))*16/count)*pressure
                for i in range(1,count+1):
                    t=i/count
                    self.stamp(old['x']+(x-old['x'])*t,old['y']+(y-old['y'])*t,old['r'],old['color'],dose)
                old['travel']+=dist
                old['hold']=0
            old.update(x=x,y=y,last=now,pressure=pressure)

    def add_drop(self,p):
        if not self.dripping:
            return
        self.drops.append(dict(x=p['x']+self.rng.uniform(-.24,.24)*p['r'],
            y=p['y']-p['r']*.30,r=float(self.rng.uniform(1.2,max(1.5,p['r']*.095)))*self.drip_width,
            age=0.,life=float(self.rng.uniform(2.4,5.5))*self.drip_life,speed=float(self.rng.uniform(22,48)),color=p['color']))
        # ponytail: The Maxdrips control bounds CPU work; dense liquid simulations should move to the GPU.
        self.drops=self.drops[-self.max_drips:]

    def advance(self,dt):
        dt=min(.05,max(0,dt))
        for p in self.pointers.values():
            self.stamp(p['x'],p['y'],p['r'],p['color'],dt*self.flow*p['pressure'])
            p['hold']+=dt
            coverage=self.ink[int(p['y']),int(p['x']),3]
            if coverage>self.drip_threshold and (p['hold']>self.drip_delay or p['travel']>p['r']*5):
                self.add_drop(p)
                p['hold']=p['travel']=0
        if not self.dripping:
            return
        alive=[]
        for d in self.drops:
            d['age']+=dt
            if d['age']>=d['life'] or d['y']<-d['r']:
                continue
            dry=1-d['age']/d['life']
            dy=d['speed']*self.drip_speed*dt*(.22+dry)
            n=max(1,math.ceil(dy/max(.5,d['r']*.35)))
            for _ in range(n):
                d['y']-=dy/n
                self.stamp(d['x'],d['y'],d['r']*(.62+.38*dry),d['color'],.7,True)
            alive.append(d)
        self.drops=alive


