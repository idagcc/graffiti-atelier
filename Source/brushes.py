import numpy as np

NAMES=['Spray','Neon','Marker','Rainbow','Splatter','Sculpt']

def preset(style):
    row=op('/master/STYLE_PRESETS').row(NAMES[int(style)])
    return [float(c.val) for c in row[1:]]

def brush(style,u,v,color,rng,phase):
    """Shared brush footprints for the wall and the car's local surface plane."""
    d=np.sqrt(u*u+v*v)
    color=np.asarray(color,np.float32)
    if style==0:
        profile=np.exp(-3.4*d*d)*(.72+rng.random(d.shape)*.56)
    elif style==1:
        profile=np.clip((.58-d)*18,0,1)
    elif style==2:
        chisel=np.sqrt((u*.8+v*.6)**2*.65+(-u*.6+v*.8)**2*3.)
        profile=np.clip((1-chisel)*18,0,1)
    elif style==3:
        profile=np.clip((1-d)*14,0,1)
        hue=np.mod(phase+v*.24,1)
        color=np.clip(np.abs(np.mod(hue[...,None]*6+np.array([0,4,2]),6)-3)-1,0,1)
        color=.06+.94*color
    elif style==4:
        profile=np.clip((.52-d)*12,0,1)*(.55+.45*rng.random(d.shape))
        for _ in range(9):
            theta=rng.uniform(0,6.283);dist=rng.uniform(.45,1.65);radius=rng.uniform(.035,.19)
            spot=np.sqrt((u-np.cos(theta)*dist)**2+(v-np.sin(theta)*dist)**2)
            profile=np.maximum(profile,np.clip((radius-spot)*55,0,1))
    else:
        profile=np.sqrt(np.clip(1-d*d,0,1))
    return profile.astype(np.float32),color

def choose(version,index):
    version.op('paint_engine').module.engine.pointers.clear()
    version.op('STYLE_CONTROLS').par.Style=int(index)
    labels(version)

def labels(version):
    selected=int(version.op('STYLE_CONTROLS').par.Style)
    for i in range(6):
        t=version.op('paint_studio/style'+str(i))
        t.par.bgcolorr,t.par.bgcolorg,t.par.bgcolorb=(.26,.23,.38) if i==selected else (.10,.12,.15)
        t.par.text=NAMES[i].upper()

def poll(version,held):
    glow=float(version.op('STYLE_CONTROLS').par.Glow)
    if glow!=held.get('_glow'):
        version.op('paint_engine').module.engine.dirty=True
        held['_glow']=glow
    for i in range(6):
        name='style'+str(i);down=bool(version.op('paint_studio/'+name).panel.select)
        if down and not held.get(name,False):choose(version,i)
        held[name]=down
    labels(version)
