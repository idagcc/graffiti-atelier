"""Rebuild the presentation panels in the open TouchDesigner project."""

from pathlib import Path

app = op('/atelier')
app.op('runtime').text = Path(source_dir, 'runtime.py').read_text(encoding='utf-8')
runtime = app.op('runtime').module

BACKGROUND = (.031, .035, .043)
SHEET = (.052, .060, .074)
BUTTON = (.105, .120, .145)
LINE = (.15, .17, .21)
WHITE = (.94, .95, .97)
MUTED = (.63, .68, .75)
ACCENT = runtime.ACCENT
WALL_COLOR_SOURCE = 'brick_wall.frag'
CLEAR_HELP = ('Clear All / Z', 'Clear the canvas. Press Z to undo.')
EXIT_HELP = ('Tab / Ctrl+Q', 'Open Settings or exit the app (Cmd+Q on Mac)')

def rect(node, x, y, w, h):
    for name, value, extent, units in (
        ('x', x, 'width', 1280), ('y', y, 'height', 800),
        ('w', w, 'width', 1280), ('h', h, 'height', 800),
    ):
        getattr(node.par, name).expr = f'parent().{extent}*{value/units}'
    return node

def fill(node, color, alpha=1):
    node.par.bgcolorr, node.par.bgcolorg, node.par.bgcolorb = color
    node.par.bgalpha = alpha

def block(parent, name, bounds, color, layer=0, alpha=1):
    node = rect(parent.create(containerCOMP, name), *bounds)
    fill(node, color, alpha)
    node.par.layer = layer
    return node

def text(parent, name, value, bounds, size=16, color=WHITE, align='left',
         background=None, action=None, layer=2):
    node = rect(parent.create(textCOMP, name), *bounds)
    node.par.text = value
    node.par.font = 'DM Sans'
    node.par.fontsize.expr = f'{size}*min(op("/atelier").width/1280,op("/atelier").height/800)'
    node.par.alignx = align
    node.par.scaletofit = 'onlyshrink'
    node.par.fontcolorr, node.par.fontcolorg, node.par.fontcolorb = color
    node.par.layer = layer
    if background is not None:
        fill(node, background)
    if action:
        node.storage['action'] = action
    return node

def button(parent, name, value, bounds, action=None, background=BUTTON, color=WHITE, layer=2):
    return text(parent, name, value, bounds, 15, color, 'center', background,
                action or name, layer)

def modal(name, color, alpha=1):
    node = block(app, name, (0, 0, 1280, 800), color, layer=100, alpha=alpha)
    node.par.display = False
    return node

def install_wall_features(parent, source_dir):
    brick = parent.op('brick_wall')
    if brick is None:
        brick = parent.create(glslTOP, 'brick_wall')
        brick.nodeX = -360
        brick.nodeY = 170
    brick.viewer = True
    brick.par.outputresolution = 'custom'
    brick.par.resolutionw, brick.par.resolutionh = 1024, 640
    brick.inputConnectors[0].connect(parent.op('concrete'))
    brick.par.pixeldat.eval().text = Path(source_dir, WALL_COLOR_SOURCE).read_text(encoding='utf-8')
    parent.op('background_switch').inputConnectors[0].connect(brick)

    settings = parent.op('settings_panel')
    controls = (
        (parent, 'clear_all', 'Clear All', (1090, 15, 158, 52), 'clear', (.24, .105, .13)),
        (settings, 'exit_app', 'Exit App', (382, 89, 143, 43), 'exit_app', BUTTON),
    )
    for panel, name, label, bounds, action, color in controls:
        if panel.op(name) is None:
            node = button(panel, name, label, bounds, action, background=color, layer=3)
            node.viewer = True
            node.nodeX, node.nodeY = 390, 170
            node.par.resizecomp = node
            node.par.repocomp = node
            node.resetNodeSize()

    settings.op('remove_image').par.text = 'Use brick wall'
    help_panel = parent.op('help_panel')
    for index, (key, description) in ((5, CLEAR_HELP), (7, EXIT_HELP)):
        help_panel.op(f'key{index}').par.text = key
        help_panel.op(f'instruction{index}').par.text = description

# Keep the canvas operator so the native-touch receiver remains attached to it.
panels = [child for child in app.children
          if child.family == 'COMP' and child.name not in ('canvas', 'window')]
for child in panels:
    child.destroy()
for child in app.children:
    if child.family == 'DAT' and child.name.endswith('_callbacks') and child.name not in (
        'native_touch_callbacks', 'keyboard_callbacks', 'tuio_callbacks',
    ):
        child.destroy()

fill(app, BACKGROUND)
canvas = rect(app.op('canvas'), 0, 0, 1280, 800)
canvas.par.topfill = 'off'
canvas.par.layer = 0
app.op('native_touch_callbacks').text = """def onDown(dat,event):op('/atelier/runtime').module.native(event,True)
def onMove(dat,event):op('/atelier/runtime').module.native(event,True,allow_start=False)
def onUp(dat,event):op('/atelier/runtime').module.native(event,False)
def onHover(dat,event):pass
"""
for position, index in enumerate(runtime.PUBLIC_COLORS):
    color = runtime.COLORS[index]
    name = f'swatch{index}'
    swatch = text(app, name, '', (422+74*position, 15, 66, 52), 23, WHITE, 'center',
                  color, name, layer=3)

settings = modal('settings_panel', BACKGROUND, alpha=.72)
block(settings, 'sheet', (0, 0, 1280, 596), SHEET)
block(settings, 'sheet_edge', (0, 595, 1280, 1), LINE, layer=1)
text(settings, 'title', 'Settings', (32, 526, 380, 48), 34)
button(settings, 'help', 'Help', (1002, 531, 108, 42))
button(settings, 'close', 'Done', (1120, 531, 128, 42), 'close_settings', ACCENT, BACKGROUND)
block(settings, 'rule', (32, 509, 1216, 1), LINE, layer=1)
block(settings, 'divide', (640, 74, 1, 417), LINE, layer=1)
text(settings, 'surface', 'Canvas', (32, 459, 550, 38), 22)
button(settings, 'finish0', 'Spray', (32, 405, 130, 43))
button(settings, 'finish1', 'Wet paint', (170, 405, 147, 43))
button(settings, 'finish2', 'Neon', (325, 405, 172, 43))
button(settings, 'rotate', 'Orbit', (505, 405, 105, 43))
button(settings, 'wall', 'Wall', (32, 354, 130, 43))
button(settings, 'model', '3D object', (170, 354, 147, 43))
button(settings, 'smaller', '−', (329, 354, 43, 43))
text(settings, 'size', 'Size 20', (372, 354, 82, 43), 14, WHITE, 'center', BACKGROUND, layer=2)
button(settings, 'larger', '+', (454, 354, 43, 43))
button(settings, 'runs', 'Drips on', (505, 354, 105, 43))
button(settings, 'image', 'Load wall image', (32, 303, 280, 43))
button(settings, 'remove_image', 'Use brick wall', (320, 303, 290, 43))
button(settings, 'import_model', 'Load 3D model', (32, 252, 280, 43))
button(settings, 'restore_model', 'Restore original car', (320, 252, 290, 43))
button(settings, 'light', 'Soft studio light', (32, 201, 191, 43))
button(settings, 'left', 'Turn left', (231, 201, 90, 43))
button(settings, 'right', 'Turn right', (329, 201, 90, 43))
button(settings, 'zoom_in', 'Zoom +', (427, 201, 88, 43))
button(settings, 'zoom_out', 'Zoom −', (523, 201, 87, 43))
button(settings, 'home', 'Reset view', (32, 150, 191, 43))
button(settings, 'clear', 'Clear surface', (231, 150, 143, 43))
button(settings, 'undo', 'Undo stroke', (382, 150, 143, 43))
button(settings, 'save', 'Export artwork', (32, 89, 191, 43))
button(settings, 'project', 'Save project', (231, 89, 143, 43))

text(settings, 'sensor_title', 'LiDAR calibration', (674, 459, 573, 38), 22)
text(settings, 'sensor_hint', 'SLAMTEC RPLIDAR S3  ·  FrameGrabber.NET', (674, 427, 573, 28), 14, MUTED)
button(settings, 'sensor', 'TUIO on', (674, 371, 274, 43))
button(settings, 'port', 'UDP 3333', (956, 371, 292, 43))
button(settings, 'flipx', 'Flip X off', (674, 320, 182, 43))
button(settings, 'flipy', 'Flip Y on', (864, 320, 182, 43))
button(settings, 'swap', 'Swap X/Y off', (1054, 320, 194, 43))
button(settings, 'calibrate', 'Calibrate · 6 points', (674, 259, 308, 48), background=ACCENT, color=BACKGROUND)
button(settings, 'reset_calibration', 'Reset calibration', (990, 259, 258, 48))
text(settings, 'telemetry', '', (674, 215, 574, 32), 15, MUTED)
text(settings, 'alignment', '', (674, 175, 574, 32), 15)
text(settings, 'setup_hint', 'Set the touch area and enable TUIO in FrameGrabber.NET.', (674, 137, 574, 29), 14, MUTED)
text(settings, 'status', '', (32, 25, 1216, 38), 15, ACCENT)

help_panel = modal('help_panel', BACKGROUND, alpha=.78)
block(help_panel, 'sheet', (0, 0, 1280, 530), SHEET)
text(help_panel, 'title', 'How to paint', (32, 452, 600, 54), 34)
button(help_panel, 'close', 'Done', (1120, 459, 128, 42), 'close_help', ACCENT, BACKGROUND)
instructions = (
    ('Paint', 'Choose a color. Drag to paint or hold to build up color.'),
    ('1 / 2 / 3', 'Spray, wet paint or neon'),
    ('W / V', 'Wall or 3D object'),
    ('[ / ]', 'Decrease or increase brush size'),
    ('R / Arrows', 'Toggle orbit or turn and zoom the 3D object'),
    CLEAR_HELP,
    ('S / Ctrl+S', 'Export your artwork or save an editable project'),
    EXIT_HELP,
)
for index, (key, description) in enumerate(instructions):
    y = 402-48*index
    text(help_panel, f'key{index}', key, (32, y, 216, 35), 15, ACCENT)
    text(help_panel, f'instruction{index}', description, (256, y, 992, 35), 17)

calibration = modal('calibration', BACKGROUND)
text(calibration, 'title', 'LiDAR calibration', (100, 469, 1080, 60), 39, WHITE, 'center')
text(calibration, 'prompt', '', (100, 415, 1080, 50), 24, WHITE, 'center')
text(calibration, 'detail', '', (100, 372, 1080, 36), 16, MUTED, 'center')
button(calibration, 'cancel', 'Cancel', (1120, 13, 128, 42), 'cancel_calibration')
for index, (u, v) in enumerate(runtime.CALIBRATION_TARGETS):
    target = text(calibration, f'point{index}', '+', (0, 0, 62, 62), 39, WHITE, 'center', BUTTON)
    target.par.w.expr = 'min(parent().width/1280,parent().height/800)*62'
    target.par.h.expr = 'me.width'
    target.par.x.expr = f'parent().width*{u}-me.width/2'
    target.par.y.expr = f'parent().height*{v}-me.height/2'
    number = text(calibration, f'number{index}', str(index+1), (0, 0, 104, 30), 16, MUTED, 'center')
    number.par.x.expr = f'parent().width*{u}-me.width/2'
    number.par.y.expr = f'op("point{index}").par.y+op("point{index}").height'

# Match the 3D render's aspect to the canvas while preserving render picking.
render = op(runtime.CAR+'/CAR_RENDER')
render.par.resolutionw.expr = 'max(1,min(1600,round(640*op("/atelier/canvas").width/max(1,op("/atelier/canvas").height))))'
install_wall_features(app, source_dir)
runtime.sync()
