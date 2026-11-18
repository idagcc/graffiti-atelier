"""Graffiti Atelier: native TouchDesigner interface and unified contact router."""
import time, math, io, base64, json
from pathlib import Path
from datetime import datetime
from tempfile import NamedTemporaryFile
from types import SimpleNamespace
import numpy as np
A='/atelier'; WALL='/master/version_6_styles'; CAR='/master/version_5_car'
COLORS=[(1,.10,.22),(1,.35,.07),(1,.77,.12),(.53,.91,.25),(.04,.73,.56),(.06,.68,1),(.24,.36,1),(.62,.28,1),(1,.19,.65),(.95,.94,.88),(.035,.04,.052)]
PUBLIC_COLORS=(0,2,3,5,7,9)
ACCENT=(.92,.99,.40)
CALIBRATION_TARGETS=((.13,.36),(.50,.36),(.87,.36),(.13,.135),(.50,.135),(.87,.135))
TUIO_SETTINGS=('tuio','port','flipx','flipy','swap','homography')
held={}; contacts={}; sensor_contacts={}
previous=time.perf_counter(); last_packet=0.
calibrating=False
calibration_samples=[]
calibration_tap=None

def appop():return op(A)
def state():return appop().storage.setdefault('settings',dict(mode='model',style=0,color=0,size=20,runs=True,settings=False,help=False,light=0,tuio=True,port=3333,flipx=False,flipy=True,swap=False,timeout=1.5,homography=None,image=False))
def wall():return op(WALL+'/paint_engine').module
def car():return op(CAR+'/paint_engine').module
def status(text):
    appop().op('settings_panel/status').par.text=text

def calibration_file():
    return Path(project.folder)/'LiDAR Calibration.json'

def load_calibration():
    try:
        profile=json.loads(calibration_file().read_text(encoding='utf-8'))
        if any(type(profile[key]) is not bool for key in ('tuio','flipx','flipy','swap')):
            raise ValueError
        if type(profile['port']) is not int or not 1<=profile['port']<=65535:
            raise ValueError
        if profile['homography'] is not None:
            matrix=np.asarray(profile['homography'],dtype=float)
            if matrix.shape!=(3,3) or not np.isfinite(matrix).all() or abs(np.linalg.det(matrix))<1e-8:
                raise ValueError
            profile['homography']=matrix.tolist()
        state().update({key:profile[key] for key in TUIO_SETTINGS})
    except FileNotFoundError:
        pass
    except (OSError, ValueError, TypeError, KeyError, np.linalg.LinAlgError):
        status('Saved LiDAR setup could not be loaded.')

def save_calibration():
    path=calibration_file()
    temporary=None
    try:
        with NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as stream:
            temporary=Path(stream.name)
            json.dump({key:state()[key] for key in TUIO_SETTINGS},stream,indent=2)
        temporary.replace(path)
        return True
    except OSError:
        return False
    finally:
        if temporary is not None:
            try:temporary.unlink(missing_ok=True)
            except OSError:pass

def release_all():
    wall().engine.pointers.clear();car().engine.pointers.clear();contacts.clear()

def focus_canvas():
    if not ui.performMode:appop().op('window').par.winopen.pulse()
    run("op('/atelier').setFocus()",delayFrames=3)

def fullscreen():
    w=appop().op('window')
    if not ui.performMode and w.isOpen:w.par.winclose.pulse()
    w.par.borders=False;w.par.size='fill';w.par.closeescape=False
    if not ui.performMode:w.par.performance.pulse()
    focus_canvas()

def sync():
    s=state()
    for v in [WALL,CAR]:
        c=op(v+'/STYLE_CONTROLS').par;c.Style=[0,5,1][s['style']]
    wc=op(WALL+'/STYLE_CONTROLS').par;cc=car().ctrl()
    for c in [wc,cc]:
        for channel,value in zip('rgb',COLORS[s['color']]):getattr(c,'Color'+channel).val=value
    wc.Radius=s['size'];wc.Runs=s['runs'];wc.Relief=8.;wc.Glow=2.2;wc.Lightx=[-.7,.6,1.4][s['light']]
    cc.Size=s['size']*.004;cc.Runs=1 if s['runs'] else 0;cc.Wetroughness=.12;cc.Dryroughness=.42;cc.Drytime=35
    wall().settings()
    appop().op('tuio').par.active=s['tuio'];appop().op('tuio').par.port=s['port']
    canvas=appop().op('canvas');canvas.par.top=op((CAR if s['mode']=='model' else WALL)+'/out1')
    panel=appop().op('settings_panel')
    panel.par.display=s['settings'];appop().op('help_panel').par.display=s['help']
    appop().op('calibration').par.display=calibrating
    selected=[(panel.op('wall'),s['mode']=='wall'),(panel.op('model'),s['mode']=='model')]
    selected.extend((panel.op('finish'+str(i)),s['style']==i) for i in range(3))
    selected.append((panel.op('rotate'),bool(cc.Rotate)))
    for node,value in selected:
        node.par.bgcolorr,node.par.bgcolorg,node.par.bgcolorb=ACCENT if value else (.105,.120,.145)
        node.par.fontcolorr,node.par.fontcolorg,node.par.fontcolorb=(.031,.035,.043) if value else (.94,.95,.97)
    for i in PUBLIC_COLORS:
        n=appop().op('swatch'+str(i));n.par.text='●' if i==s['color'] else ''
        n.par.fontcolorr,n.par.fontcolorg,n.par.fontcolorb=(.1,.1,.1) if i in (2,3,9) else (1,1,1)
    panel.op('size').par.text='Size '+str(s['size'])
    panel.op('runs').par.text='Drips '+('on' if s['runs'] else 'off')
    panel.op('rotate').par.text='Orbit on' if bool(cc.Rotate) else 'Orbit off'
    for name in ('rotate','left','right','zoom_in','zoom_out','home'):
        panel.op(name).par.display=s['mode']=='model'
    panel.op('sensor').par.text='TUIO '+('on' if s['tuio'] else 'off')
    panel.op('port').par.text='UDP '+str(s['port'])
    panel.op('flipx').par.text='Flip X '+('on' if s['flipx'] else 'off')
    panel.op('flipy').par.text='Flip Y '+('on' if s['flipy'] else 'off')
    panel.op('swap').par.text='Swap X/Y '+('on' if s['swap'] else 'off')
    panel.op('light').par.text=['Soft studio light','Side light','Hard rim light'][s['light']]
    panel.op('alignment').par.text='Calibration active' if s['homography'] is not None else 'Using FrameGrabber’s TUIO coordinates'

def action(name):
    global calibrating,calibration_tap,last_packet
    s=state()
    if calibrating and name!='cancel_calibration':return
    save_sensor_settings=False
    if name.startswith('swatch'):s['color']=int(name[6:])
    elif name.startswith('finish'):release_all();s['style']=int(name[6:])
    elif name in ('wall','model'):release_all();s['mode']=name
    elif name in ('settings','close_settings'):
        release_all();s['settings']=name=='settings' and not s['settings'];s['help']=False
    elif name in ('help','close_help'):
        release_all();s['help']=name=='help' and not s['help'];s['settings']=False
    elif name=='smaller':s['size']=max(4,s['size']-4)
    elif name=='larger':s['size']=min(64,s['size']+4)
    elif name=='runs':
        s['runs']=not s['runs']
        if not s['runs']:
            wall().engine.drops.clear()
            car().engine.drops.clear()
    elif name=='undo':release_all();(car() if s['mode']=='model' else wall()).engine.undo_stroke();status('Last stroke undone')
    elif name=='clear':release_all();(car() if s['mode']=='model' else wall()).engine.clear();status('Fresh surface · Undo restores your painting')
    elif name=='save':save_artwork()
    elif name=='project':project.save();status('Project saved · Image, model and editable paint preserved')
    elif name=='image':load_image()
    elif name=='remove_image':s['image']=False;appop().op('background_switch').par.index=0;status('Concrete wall restored')
    elif name=='import_model':load_model()
    elif name=='restore_model':restore_model()
    elif name=='rotate':release_all();car().ctrl().Rotate=not bool(car().ctrl().Rotate)
    elif name in ('left','right','zoom_in','zoom_out','home'):
        car().action(dict(left='turnleft',right='turnright',zoom_in='closer',zoom_out='farther',home='home')[name])
    elif name=='light':
        s['light']=(s['light']+1)%3
        # Rebalance the studio's key light; wet paint and relief respond immediately.
        n=op(CAR+'/key_light');n.par.tx=[-3,4,1][s['light']]
    elif name=='sensor':
        release_all();sensor_contacts.clear();last_packet=0.
        s['tuio']=not s['tuio'];save_sensor_settings=True
    elif name=='port':
        value=ui.messageBox('TUIO UDP port','Choose the receiving port',buttons=['3333','3334','3335','Cancel'])
        if value in (0,1,2):
            release_all();sensor_contacts.clear();last_packet=0.
            s['port']=[3333,3334,3335][value];save_sensor_settings=True
    elif name in ('flipx','flipy','swap'):
        release_all();s[name]=not s[name];s['homography']=None;save_sensor_settings=True
    elif name=='calibrate':
        if not s['tuio']:
            status('Turn on TUIO before calibrating.')
            return
        release_all()
        calibration_samples.clear()
        calibration_tap=None
        calibrating=True
        s['settings']=s['help']=False
        show_calibration_step()
    elif name=='cancel_calibration':
        finish_calibration('Calibration cancelled.')
        return
    elif name=='reset_calibration':
        release_all();s['homography']=None;save_sensor_settings=True
        status('Calibration reset.')
    elif name=='fullscreen':
        fullscreen()
    if save_sensor_settings and not save_calibration():
        status('LiDAR settings are active for this session. Saving failed.')
    sync()

def save_artwork():
    folder=Path(project.folder)/'Exports';folder.mkdir(exist_ok=True)
    stamp=datetime.now().strftime('%Y%m%d_%H%M%S_%f');m=state()['mode'];name=folder/(m+'_'+stamp)
    source=op((CAR if m=='model' else WALL)+'/out1');source.cook(force=True);source.save(str(name)+'.png')
    e=(car() if m=='model' else wall()).engine
    values={k:getattr(e,k) for k in ['ink','mass','glow']}
    if hasattr(e,'wet'):values['wet']=e.wet
    np.savez_compressed(str(name)+'_editable.npz',**values)
    if m=='model':op(CAR+'/paint_color').save(str(name)+'_texture.png')
    status('Saved PNG + editable paint · Exports / '+name.name)

def load_image(path=None):
    if path is None:path=ui.chooseFile(load=True,title='Choose a wall image · PNG or JPEG',fileTypes=['png','jpg','jpeg','tif','tiff'])
    focus_canvas()
    if not path:return
    n=appop().op('background_image');n.lock=False;n.par.file=str(path);n.par.reloadpulse.pulse();n.cook(force=True)
    if n.errors():status('Image could not be loaded');return
    # Lock the decoded TOP, embedding the image into the project.
    n.lock=True;state()['image']=True;state()['image_name']=Path(path).name
    appop().op('background_switch').par.index=1;state()['mode']='wall';status('Wall image · '+Path(path).name);sync()

def normalized(u,v):
    s=state();u,v=float(u),float(v)
    if s['swap']:u,v=v,u
    if s['flipx']:u=1-u
    if s['flipy']:v=1-v
    return u,v

def calibrated(u,v):
    u,v=normalized(u,v);h=state().get('homography')
    if h:
        q=np.asarray(h)@np.array([u,v,1.]);
        if abs(q[2])<1e-8:return -1,-1
        u,v=q[0]/q[2],q[1]/q[2]
    return float(u),float(v)

def fit_calibration(samples):
    # Fit scale, offset, rotation and shear. A perspective fit would amplify
    # small measurement errors when extrapolating from reachable targets.
    design=np.column_stack((samples,np.ones(len(samples))))
    coefficients,_,rank,spread=np.linalg.lstsq(design,CALIBRATION_TARGETS,rcond=None)
    if rank!=3 or spread[0]/spread[-1]>100:
        raise ValueError('FrameGrabber reported points too close together.')
    scales=np.linalg.svd(coefficients[:2],compute_uv=False)
    if scales[0]>8 or scales[-1]<.125:
        raise ValueError('Check the touch area in FrameGrabber and try again.')
    residual=np.linalg.norm(design@coefficients-CALIBRATION_TARGETS,axis=1)
    if residual.max()>.035:
        raise ValueError('The touches did not line up. Try tapping the center of each target.')
    return np.vstack((coefficients.T,[0,0,1])).tolist()

def show_calibration_step(detail=None):
    panel=appop().op('calibration')
    step=len(calibration_samples)
    panel.op('prompt').par.text=f'Touch target {step+1} of {len(CALIBRATION_TARGETS)}'
    if detail is None:
        if sensor_contacts:
            detail='Lift all fingers to continue.'
        elif time.perf_counter()-last_packet<2:
            detail='Touch the center of the highlighted + and lift your finger.'
        else:
            detail='Touch the highlighted +. Waiting for FrameGrabber TUIO.'
    panel.op('detail').par.text=detail
    for index in range(len(CALIBRATION_TARGETS)):
        point=panel.op(f'point{index}')
        color=ACCENT if index==step else (.105,.120,.145)
        point.par.bgcolorr,point.par.bgcolorg,point.par.bgcolorb=color
        point.par.fontcolorr,point.par.fontcolorg,point.par.fontcolorb=(
            (.031,.035,.043) if index==step else (.55,.70,.63) if index<step else (.56,.61,.69)
        )
        point.par.text='✓' if index<step else '+'

def finish_calibration(message):
    global calibrating,calibration_tap
    calibrating=False
    calibration_tap=None
    calibration_samples.clear()
    state()['settings']=True
    status(message)
    sync()

def record_calibration_tap(point):
    if not all(math.isfinite(value) for value in point):
        show_calibration_step('The sensor reported an invalid point. Try this target again.')
        return
    if any(math.dist(point,previous)<.015 for previous in calibration_samples):
        show_calibration_step('This touch is too close to an earlier one. Try the highlighted +.')
        return
    calibration_samples.append(point)
    if len(calibration_samples)<len(CALIBRATION_TARGETS):
        show_calibration_step()
        return
    try:
        state()['homography']=fit_calibration(calibration_samples)
    except (ValueError,np.linalg.LinAlgError) as error:
        finish_calibration(f'Calibration failed. {error}')
        return
    saved=save_calibration()
    finish_calibration('Calibration complete and saved.' if saved else
                       'Calibration active for this session. Saving failed.')

def tuio(events):
    global last_packet,calibration_tap
    if not state()['tuio']:return
    last_packet=time.perf_counter()
    for event in events:
        starts=event.touchesStart
        ends=event.touchesEnd
        previously_touching=bool(sensor_contacts)
        for touch in ends:
            sensor_contacts.pop(touch.id,None)
        for touches in (starts,event.touchesMove,event.touchesNoChange):
            for touch in touches:
                sensor_contacts[touch.id]=last_packet
        if calibrating:
            if len(sensor_contacts)>1:
                calibration_tap=None
                show_calibration_step('Lift all fingers, then touch one target at a time.')
            elif calibration_tap and any(touch.id==calibration_tap[0] for touch in ends):
                _,sample=calibration_tap
                calibration_tap=None
                record_calibration_tap(sample)
            elif len(starts)==1 and not previously_touching and len(sensor_contacts)==1:
                touch=starts[0]
                calibration_tap=(touch.id,normalized(touch.u,touch.v))
                show_calibration_step('Lift your finger to confirm this point.')
            elif ends and not sensor_contacts:
                show_calibration_step()
            continue
        for kind,items in [('end',ends),('start',starts),('move',event.touchesMove),('hold',event.touchesNoChange)]:
            for t in items:
                if calibrating:
                    continue
                u,v=calibrated(t.u,t.v)
                contact('tuio:'+str(t.id),u,v,kind!='end',screen=True,allow_start=kind=='start')

def contact(identifier,u,v,down,screen=False,allow_start=True):
    s=state();now=time.perf_counter()
    if not all(math.isfinite(float(x)) for x in (u,v)):down=False
    if not down:
        contacts.pop(identifier,None)
        wall().engine.pointer(identifier,0,0,False);car().engine.pointers.pop(identifier,None)
        return
    old=contacts.get(identifier)
    if old is None:
        if not allow_start or len(contacts)>=10:return
        if screen:
            # Capture a contact to its initial UI target; a color tap never turns into a stroke.
            target=hit(u,v)
            if target and target!='canvas':
                action(target);contacts[identifier]=dict(target=target,time=now);return
            if target!='canvas':return
        if s['settings'] or s['help'] or calibrating:return
        old=dict(target='canvas',mode=s['mode'],time=now,u=u,v=v);contacts[identifier]=old
    old['time']=now
    if old['target']!='canvas':return
    if screen:
        c=appop().op('canvas');u=(u*appop().width-float(c.par.x))/c.width;v=(v*appop().height-float(c.par.y))/c.height
    if not (0<=u<=1 and 0<=v<=1):
        wall().engine.pointer(identifier,0,0,False);car().engine.pointers.pop(identifier,None);return
    if old['mode']=='wall':wall().engine.pointer(identifier,u,v,True)
    else:
        e=SimpleNamespace(id=identifier,u=u,v=v,downu=u,downv=v);car().touch_event(e,True)
    old['u']=u;old['v']=v

def hit(u,v):
    x,y=u*appop().width,v*appop().height
    parent=appop().op('settings_panel') if state()['settings'] else appop().op('help_panel') if state()['help'] else appop()
    if parent!=appop():
        x-=float(parent.par.x);y-=float(parent.par.y)
    for n in parent.children:
        name=n.storage.get('action')
        if name and bool(n.par.display) and float(n.par.x)<=x<float(n.par.x)+n.width and float(n.par.y)<=y<float(n.par.y)+n.height:
            return name
    if parent==appop() and 0<=u<1 and 0<=v<1:return 'canvas'
    return None

def native(event,down,allow_start=True):
    contact('native:'+str(event.id),float(event.u),float(event.v),down,allow_start=allow_start)

def key(info):
    if not info.state:return
    k=info.key.lower()
    commands={'i':'image','m':'import_model','tab':'settings','f1':'help','1':'finish0','2':'finish1','3':'finish2','w':'wall','v':'model','r':'rotate','z':'undo','s':'save','backspace':'clear','delete':'clear','[':'smaller',']':'larger','f':'fullscreen','d':'runs','left':'left','right':'right','up':'zoom_in','down':'zoom_out'}
    if k=='escape':
        if calibrating:
            action('cancel_calibration')
        elif state()['settings']:action('close_settings')
        elif state()['help']:action('close_help')
        else:
            w=appop().op('window')
            if ui.performMode:ui.performMode=False
            else:w.par.winclose.pulse()
            w.par.borders=True;w.par.size='custom';focus_canvas()
        return
    if k=='s' and (info.cmd or info.ctrl):action('project');return
    if k in commands:
        try:action(commands[k])
        except Exception as e:status('Could not complete action · '+str(e)[:100])

def tick():
    global previous,calibration_tap
    now=time.perf_counter();dt=min(.05,now-previous);previous=now
    # Panels work natively with mouse or OS touch. LiDAR routes to the same action names.
    s=state()
    panel=appop().op('calibration') if calibrating else appop().op('settings_panel') if s['settings'] else appop().op('help_panel') if s['help'] else appop()
    for n in panel.children:
        name=n.storage.get('action')
        if name and bool(n.par.display):
            down=bool(n.panel.select);key=n.path
            pressed=down and not held.get(key,False)
            held[key]=down
            if pressed:
                try:action(name)
                except Exception as e:status('Could not complete action · '+str(e)[:100])
                break
    for identifier,c in list(contacts.items()):
        if identifier.startswith('tuio:') and now-c['time']>state()['timeout']:contact(identifier,0,0,False)
    for identifier,seen in list(sensor_contacts.items()):
        if now-seen>s['timeout']:
            sensor_contacts.pop(identifier)
            if calibration_tap and calibration_tap[0]==identifier:
                calibration_tap=None
            if calibrating and not sensor_contacts:
                show_calibration_step('Touch the highlighted + again and lift to confirm.')
    wall().engine.advance(dt)
    if wall().engine.dirty:
        op(WALL+'/paint_color').cook(force=True);op(WALL+'/paint_surface').cook(force=True);wall().engine.dirty=False
    for p in list(car().engine.pointers.values()):
        if not p['rot']:p['point']=car().paint_at(p['u'],p['v'],dt,p['point'])
    car().engine.advance(dt)
    if car().engine.dirty and s['mode']=='model':
        for n in ['paint_color','wetness_height','paint_emission']:op(CAR+'/'+n).cook(force=True)
        car().engine.dirty=False
    if s['settings']:
        if not s['tuio']:connection='TUIO is off'
        elif appop().op('tuio').errors():connection='Unable to listen on UDP '+str(s['port'])
        elif now-last_packet<2:connection=f'Receiving TUIO · {len(sensor_contacts)} active'
        else:connection='Touch the display to test TUIO'
        appop().op('settings_panel/telemetry').par.text=connection

def start():
    global held,previous,calibrating,calibration_tap
    held={};sensor_contacts.clear();release_all();calibration_samples.clear()
    calibrating=False;calibration_tap=None;previous=time.perf_counter()
    s=state()
    s['settings']=s['help']=False
    if s['color'] not in PUBLIC_COLORS:
        s['color']=min(PUBLIC_COLORS,key=lambda index:math.dist(COLORS[index],COLORS[s['color']]))
    load_calibration();sync()
    run("op('/atelier/runtime').module.fullscreen()",delayFrames=12)

def parse_obj(path):
    vertices=[];uvs=[];normals=[];triangles=[]
    for line in Path(path).read_text(errors='replace').splitlines():
        t=line.split()
        if not t:continue
        if t[0]=='v':vertices.append([float(x) for x in t[1:4]])
        elif t[0]=='vt':uvs.append([float(x) for x in t[1:3]])
        elif t[0]=='vn':normals.append([float(x) for x in t[1:4]])
        elif t[0]=='f':
            face=[]
            for token in t[1:]:
                bits=token.split('/')
                if len(bits)<2 or not bits[1]:raise ValueError('Model needs UV coordinates on every face. Export an unwrapped OBJ.')
                idx=lambda x,n:int(x)-1 if int(x)>0 else n+int(x)
                face.append((idx(bits[0],len(vertices)),idx(bits[1],len(uvs)),idx(bits[2],len(normals)) if len(bits)>2 and bits[2] else -1))
            for j in range(1,len(face)-1):triangles.append([face[0],face[j],face[j+1]])
    if not triangles or len(triangles)>150000:raise ValueError('Use an OBJ with 1 to 150,000 triangles')
    v=np.asarray(vertices,np.float32);uv=np.asarray(uvs,np.float32);ns=np.asarray(normals,np.float32)
    if not np.isfinite(v).all() or not np.isfinite(uv).all() or (ns.size and not np.isfinite(ns).all()):raise ValueError('Invalid model coordinates')
    if uv.min()<-.001 or uv.max()>1.001:raise ValueError('UVs must be packed inside the 0–1 square')
    lo,hi=v.min(0),v.max(0);scale=4.6/max(float((hi-lo).max()),.00001);offset=-(lo+hi)*.5*scale;offset[1]+=1.1
    v=v*scale+offset
    valid=np.zeros((1024,1024),bool);pos=np.zeros((1024,1024,3),np.float32);norm=np.zeros_like(pos)
    overlap=0
    for tri in triangles:
        pts=v[[q[0] for q in tri]];tex=uv[[q[1] for q in tri]]*1023
        x0,y0=np.maximum(0,np.floor(tex.min(0)).astype(int));x1,y1=np.minimum(1023,np.ceil(tex.max(0)).astype(int))
        if x1<x0 or y1<y0:continue
        a,b,c=tex;den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
        if abs(den)<1e-6:continue
        yy,xx=np.mgrid[y0:y1+1,x0:x1+1];p=((b[1]-c[1])*(xx-c[0])+(c[0]-b[0])*(yy-c[1]))/den;q=((c[1]-a[1])*(xx-c[0])+(a[0]-c[0])*(yy-c[1]))/den;r=1-p-q
        mask=(p>=-1e-5)&(q>=-1e-5)&(r>=-1e-5);weights=np.stack([p,q,r],-1)
        region=valid[y0:y1+1,x0:x1+1];overlap+=int(np.sum(region&mask));region[mask]=True
        pos[y0:y1+1,x0:x1+1][mask]=(weights@pts)[mask]
        if all(q[2]>=0 for q in tri):nn=weights@ns[[q[2] for q in tri]]
        else:nn=np.broadcast_to(np.cross(pts[1]-pts[0],pts[2]-pts[0]),(*mask.shape,3)).copy()
        nn/=np.maximum(np.linalg.norm(nn,axis=-1,keepdims=True),1e-7);norm[y0:y1+1,x0:x1+1][mask]=nn[mask]
    if valid.sum()<100:raise ValueError('UV map has no usable surface')
    if overlap>valid.sum()*.06:raise ValueError('UV islands overlap. Unwrap with unique, non-overlapping UVs.')
    buf=io.BytesIO();np.savez_compressed(buf,valid=valid,position=pos,normal=norm)
    return base64.b64encode(buf.getvalue()).decode(),scale,offset

def load_model(path=None):
    if path is None:path=ui.chooseFile(load=True,title='Choose a UV-unwrapped OBJ · Unique UV islands in 0–1',fileTypes=['obj'])
    focus_canvas()
    if not path:return
    status('Preparing model and paint atlas…')
    try:
        atlas,scale,offset=parse_obj(path)
        body=op(CAR+'/car_body')
        # Stage the imported geometry before touching the current model.
        f=body.op('import_file') or body.create(fileinSOP,'import_file');f.lock=False;f.par.file=str(path);f.cook(force=True)
        if f.errors() or f.numPoints<3:raise ValueError('TouchDesigner could not read this OBJ')
        f.lock=True
        x=body.op('import_fit') or body.create(transformSOP,'import_fit');x.inputConnectors[0].connect(f)
        for axis in 'xyz':getattr(x.par,'s'+axis).val=scale
        for axis,value in zip('xyz',offset):getattr(x.par,'t'+axis).val=float(value)
        n=body.op('import_normals') or body.create(facetSOP,'import_normals');n.inputConnectors[0].connect(x);n.cook(force=True)
        for child in body.children:
            if child.family=='SOP':child.display=False;child.render=False
        n.display=True;n.render=True
        for part in ['car_glass','car_chrome','car_interior','car_lights','car_rubber']:
            node=op(CAR+'/'+part)
            if node:node.render=False
        op(CAR).storage.pop('saved_paint',None)
        op(CAR+'/surface_lookup').text=atlas
        release_all();car().engine=car().CarPaint(restore=False)
        state()['mode']='model';state()['model_name']=Path(path).name;car().action('home');status('Model ready · '+Path(path).name);sync()
    except Exception as e:status('Model import failed · '+str(e)[:130])

def restore_model():
    body=op(CAR+'/car_body')
    for child in body.children:
        if child.family=='SOP':child.display=False;child.render=False
    body.op('surface_tangents').display=True;body.op('surface_tangents').render=True
    for part in ['car_glass','car_chrome','car_interior','car_lights','car_rubber']:
        node=op(CAR+'/'+part)
        if node:node.render=True
    op(CAR).storage.pop('saved_paint',None)
    op(CAR+'/surface_lookup').text=appop().op('original_lookup').text
    release_all();car().engine=car().CarPaint(restore=False);state()['mode']='model';state()['model_name']='Original car';status('Original car restored');sync()
