"""
Sunlit Altbau room - procedural build for Blender 5.x (Cycles).
Usage: blender -b -P build_room.py -- out=<png> blend=<blend> res=500 samples=128
Coordinates (meters): big wall = plane x=0, window wall = plane y=0, floor z=0, ceiling z=3.4.
Room interior is x>0, y>0.
"""
import bpy, bmesh, math, random, sys
from mathutils import Vector, Matrix

# ----------------------------------------------------------------- args
ARGS = {}
if '--' in sys.argv:
    for a in sys.argv[sys.argv.index('--') + 1:]:
        if '=' in a:
            k, v = a.split('=', 1)
            ARGS[k] = v
OUT_PNG = ARGS.get('out', '')
OUT_BLEND = ARGS.get('blend', '')
RES = int(ARGS.get('res', 500))
SAMPLES = int(ARGS.get('samples', 128))
SUN_STR = float(ARGS.get('sun', 6.0))
SKY_STR = float(ARGS.get('sky', 1.0))
EXPOSURE = float(ARGS.get('exp', 0.0))
random.seed(11)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

# ----------------------------------------------------------------- constants
LX, LY, H = 6.6, 6.0, 3.3          # room size
WT = 0.55                          # window-wall thickness
WX0, WX1 = 0.45, 3.25              # window opening x range
WZ0, WZ1 = 0.80, 2.85              # window opening z range
TRZ = 2.30                         # transom height
SUN_EL = math.radians(float(ARGS.get('el', 24)))
_az = math.radians(float(ARGS.get('az', 28)))
SUN_AZ_VEC = Vector((math.sin(_az), -math.cos(_az)))            # horizontal direction TO the sun (x,y)
TO_SUN = Vector((SUN_AZ_VEC.x * math.cos(SUN_EL), SUN_AZ_VEC.y * math.cos(SUN_EL), math.sin(SUN_EL))).normalized()

# ----------------------------------------------------------------- helpers
def new_coll(name):
    c = bpy.data.collections.new(name)
    scene.collection.children.link(c)
    return c

def make_obj(name, bm, mat, coll, smooth=False):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if mat:
        me.materials.append(mat)
    if smooth:
        me.shade_smooth()
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob

def bm_box(bm, x0, x1, y0, y1, z0, z1):
    v = [bm.verts.new((x, y, z)) for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)]
    for f in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
        bm.faces.new([v[i] for i in f])

def add_bevel(ob, width, seg=2, angle=None, harden=False):
    m = ob.modifiers.new('Bevel', 'BEVEL')
    m.width = width
    m.segments = seg
    m.limit_method = 'ANGLE'
    m.angle_limit = math.radians(40)
    if harden:
        m.harden_normals = True
    return m

def mat_new(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(b.outputs['BSDF'], out.inputs['Surface'])
    return m, nt, b, out

def N(nt, t, loc=None, **props):
    n = nt.nodes.new(t)
    for k, v in props.items():
        setattr(n, k, v)
    return n

def LK(nt, a, b):
    nt.links.new(a, b)

def setin(node, name, val):
    try:
        node.inputs[name].default_value = val
    except Exception as e:
        print('WARN input', name, e)

def ramp(nt, stops):
    r = N(nt, 'ShaderNodeValToRGB')
    el = r.color_ramp.elements
    while len(el) > len(stops):
        el.remove(el[-1])
    while len(el) < len(stops):
        el.new(0.5)
    for e, (p, c) in zip(el, stops):
        e.position = p
        e.color = c
    return r

def mix_rgba(nt, blend='MIX'):
    n = N(nt, 'ShaderNodeMix', data_type='RGBA', blend_type=blend)
    return n   # inputs: 0 factor, 6 A, 7 B ; outputs: 2 result

def math_node(nt, op, a=None, b=None, clamp=False):
    n = N(nt, 'ShaderNodeMath', operation=op)
    n.use_clamp = clamp
    if a is not None: n.inputs[0].default_value = a
    if b is not None: n.inputs[1].default_value = b
    return n

# ----------------------------------------------------------------- materials
def m_plaster(name='Plaster', col=(0.78, 0.67, 0.53), rough=0.92, varscale=1.1):
    m, nt, b, out = mat_new(name)
    geo = N(nt, 'ShaderNodeNewGeometry')
    nlow = N(nt, 'ShaderNodeTexNoise', noise_dimensions='3D')
    setin(nlow, 'Scale', varscale); setin(nlow, 'Detail', 5); setin(nlow, 'Roughness', 0.55)
    LK(nt, geo.outputs['Position'], nlow.inputs['Vector'])
    mx = mix_rgba(nt, 'MULTIPLY')
    setin(mx, 'Factor', 1.0)
    mx.inputs[6].default_value = (*col, 1)
    rr = ramp(nt, [(0.30, (0.975, 0.97, 0.96, 1)), (0.70, (1.015, 1.01, 1.0, 1))])
    LK(nt, nlow.outputs['Fac'], rr.inputs['Fac'])
    LK(nt, rr.outputs['Color'], mx.inputs[7])
    LK(nt, mx.outputs[2], b.inputs['Base Color'])
    # fine grain bump
    nf = N(nt, 'ShaderNodeTexNoise', noise_dimensions='3D')
    setin(nf, 'Scale', 700); setin(nf, 'Detail', 3); setin(nf, 'Roughness', 0.6)
    LK(nt, geo.outputs['Position'], nf.inputs['Vector'])
    bp1 = N(nt, 'ShaderNodeBump'); setin(bp1, 'Strength', 0.12); setin(bp1, 'Distance', 0.002)
    LK(nt, nf.outputs['Fac'], bp1.inputs['Height'])
    ncoarse = N(nt, 'ShaderNodeTexNoise', noise_dimensions='3D')
    setin(ncoarse, 'Scale', 7); setin(ncoarse, 'Detail', 6)
    LK(nt, geo.outputs['Position'], ncoarse.inputs['Vector'])
    bp2 = N(nt, 'ShaderNodeBump'); setin(bp2, 'Strength', 0.05); setin(bp2, 'Distance', 0.01)
    LK(nt, ncoarse.outputs['Fac'], bp2.inputs['Height'])
    LK(nt, bp1.outputs['Normal'], bp2.inputs['Normal'])
    LK(nt, bp2.outputs['Normal'], b.inputs['Normal'])
    setin(b, 'Roughness', rough)
    setin(b, 'Specular IOR Level', 0.25)
    return m

def m_paint(name, col, rough=0.5):
    m, nt, b, out = mat_new(name)
    setin(b, 'Base Color', (*col, 1))
    setin(b, 'Roughness', rough)
    setin(b, 'Specular IOR Level', 0.4)
    geo = N(nt, 'ShaderNodeNewGeometry')
    nf = N(nt, 'ShaderNodeTexNoise', noise_dimensions='3D')
    setin(nf, 'Scale', 500); setin(nf, 'Detail', 2)
    LK(nt, geo.outputs['Position'], nf.inputs['Vector'])
    bp = N(nt, 'ShaderNodeBump'); setin(bp, 'Strength', 0.04); setin(bp, 'Distance', 0.001)
    LK(nt, nf.outputs['Fac'], bp.inputs['Height'])
    LK(nt, bp.outputs['Normal'], b.inputs['Normal'])
    return m

def m_wood_skirting(name='Skirting', col=(0.42, 0.23, 0.09)):
    m, nt, b, out = mat_new(name)
    geo = N(nt, 'ShaderNodeNewGeometry')
    mp = N(nt, 'ShaderNodeMapping')
    mp.inputs['Scale'].default_value = (2.0, 2.0, 140)
    LK(nt, geo.outputs['Position'], mp.inputs['Vector'])
    nz = N(nt, 'ShaderNodeTexNoise', noise_dimensions='3D')
    setin(nz, 'Scale', 1.0); setin(nz, 'Detail', 6); setin(nz, 'Distortion', 0.3)
    LK(nt, mp.outputs['Vector'], nz.inputs['Vector'])
    rr = ramp(nt, [(0.3, (col[0] * 0.55, col[1] * 0.55, col[2] * 0.55, 1)), (0.7, (col[0] * 1.15, col[1] * 1.15, col[2] * 1.2, 1))])
    LK(nt, nz.outputs['Fac'], rr.inputs['Fac'])
    LK(nt, rr.outputs['Color'], b.inputs['Base Color'])
    setin(b, 'Roughness', 0.35)
    setin(b, 'Coat Weight', 0.3); setin(b, 'Coat Roughness', 0.15)
    return m

def m_parquet():
    m, nt, b, out = mat_new('Parquet')
    tc = N(nt, 'ShaderNodeTexCoord')
    a1 = N(nt, 'ShaderNodeAttribute', attribute_name='rnd')
    a2 = N(nt, 'ShaderNodeAttribute', attribute_name='rnd2')
    sep = N(nt, 'ShaderNodeSeparateXYZ')
    LK(nt, tc.outputs['UV'], sep.inputs['Vector'])
    mx = math_node(nt, 'MULTIPLY', None, 10.0); LK(nt, a1.outputs['Fac'], mx.inputs[0])
    ax = math_node(nt, 'ADD'); LK(nt, sep.outputs['X'], ax.inputs[0]); LK(nt, mx.outputs[0], ax.inputs[1])
    my = math_node(nt, 'MULTIPLY', None, 4.0); LK(nt, a2.outputs['Fac'], my.inputs[0])
    ay = math_node(nt, 'ADD'); LK(nt, sep.outputs['Y'], ay.inputs[0]); LK(nt, my.outputs[0], ay.inputs[1])
    mz = math_node(nt, 'MULTIPLY', None, 5.0); LK(nt, a1.outputs['Fac'], mz.inputs[0])
    comb = N(nt, 'ShaderNodeCombineXYZ')
    LK(nt, ax.outputs[0], comb.inputs['X']); LK(nt, ay.outputs[0], comb.inputs['Y']); LK(nt, mz.outputs[0], comb.inputs['Z'])
    # stretched noise (grain)
    mp1 = N(nt, 'ShaderNodeMapping'); mp1.inputs['Scale'].default_value = (7, 95, 40)
    LK(nt, comb.outputs['Vector'], mp1.inputs['Vector'])
    n1 = N(nt, 'ShaderNodeTexNoise', noise_dimensions='3D')
    setin(n1, 'Scale', 1.0); setin(n1, 'Detail', 7); setin(n1, 'Roughness', 0.6); setin(n1, 'Distortion', 0.5)
    LK(nt, mp1.outputs['Vector'], n1.inputs['Vector'])
    # growth-ring bands
    mp2 = N(nt, 'ShaderNodeMapping'); mp2.inputs['Scale'].default_value = (1.5, 70, 8)
    LK(nt, comb.outputs['Vector'], mp2.inputs['Vector'])
    wv = N(nt, 'ShaderNodeTexWave', wave_type='BANDS', bands_direction='Y', wave_profile='SAW')
    setin(wv, 'Scale', 1.0); setin(wv, 'Distortion', 5.0); setin(wv, 'Detail', 2.0)
    LK(nt, mp2.outputs['Vector'], wv.inputs['Vector'])
    mixf = mix_rgba(nt, 'MIX'); setin(mixf, 'Factor', 0.35)
    LK(nt, n1.outputs['Color'], mixf.inputs[6]); LK(nt, wv.outputs['Color'], mixf.inputs[7])
    sepc = N(nt, 'ShaderNodeSeparateColor')
    LK(nt, mixf.outputs[2], sepc.inputs['Color'])
    rr = ramp(nt, [(0.30, (0.33, 0.14, 0.045, 1)), (0.55, (0.52, 0.27, 0.10, 1)), (0.80, (0.66, 0.40, 0.17, 1))])
    LK(nt, sepc.outputs['Red'], rr.inputs['Fac'])
    # per-board tint
    tint = ramp(nt, [(0.0, (0.82, 0.78, 0.74, 1)), (0.5, (1.0, 0.98, 0.95, 1)), (1.0, (1.18, 1.12, 1.02, 1))])
    LK(nt, a2.outputs['Fac'], tint.inputs['Fac'])
    mt = mix_rgba(nt, 'MULTIPLY'); setin(mt, 'Factor', 1.0)
    LK(nt, rr.outputs['Color'], mt.inputs[6]); LK(nt, tint.outputs['Color'], mt.inputs[7])
    LK(nt, mt.outputs[2], b.inputs['Base Color'])
    # roughness variation
    rg = ramp(nt, [(0.0, (0.26, 0.26, 0.26, 1)), (1.0, (0.15, 0.15, 0.15, 1))])
    LK(nt, sepc.outputs['Red'], rg.inputs['Fac'])
    LK(nt, rg.outputs['Color'], b.inputs['Roughness'])
    setin(b, 'Specular IOR Level', 0.5)
    setin(b, 'Coat Weight', 0.15); setin(b, 'Coat Roughness', 0.08)
    # grain bump
    bp = N(nt, 'ShaderNodeBump'); setin(bp, 'Strength', 0.25); setin(bp, 'Distance', 0.0006)
    LK(nt, sepc.outputs['Red'], bp.inputs['Height'])
    LK(nt, bp.outputs['Normal'], b.inputs['Normal'])
    return m

def m_glass():
    m = bpy.data.materials.new('Glass')
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    g = nt.nodes.new('ShaderNodeBsdfGlass')
    setin(g, 'IOR', 1.45); setin(g, 'Roughness', 0.0)
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    lp = nt.nodes.new('ShaderNodeLightPath')
    mx = math_node(nt, 'MAXIMUM')
    LK(nt, lp.outputs['Is Shadow Ray'], mx.inputs[0])
    LK(nt, lp.outputs['Is Diffuse Ray'], mx.inputs[1])
    ms = nt.nodes.new('ShaderNodeMixShader')
    LK(nt, mx.outputs[0], ms.inputs['Fac'])
    LK(nt, g.outputs['BSDF'], ms.inputs[1])
    LK(nt, tr.outputs['BSDF'], ms.inputs[2])
    LK(nt, ms.outputs['Shader'], out.inputs['Surface'])
    return m

def m_fabric(name='Boucle', col=(0.82, 0.74, 0.62)):
    m, nt, b, out = mat_new(name)
    geo = N(nt, 'ShaderNodeNewGeometry')
    nv = N(nt, 'ShaderNodeTexVoronoi', voronoi_dimensions='3D', feature='F1')
    setin(nv, 'Scale', 900); setin(nv, 'Randomness', 1.0)
    LK(nt, geo.outputs['Position'], nv.inputs['Vector'])
    nz = N(nt, 'ShaderNodeTexNoise', noise_dimensions='3D')
    setin(nz, 'Scale', 14); setin(nz, 'Detail', 4)
    LK(nt, geo.outputs['Position'], nz.inputs['Vector'])
    hm = math_node(nt, 'ADD'); LK(nt, nv.outputs['Distance'], hm.inputs[0]); LK(nt, nz.outputs['Fac'], hm.inputs[1])
    bp = N(nt, 'ShaderNodeBump'); setin(bp, 'Strength', 0.25); setin(bp, 'Distance', 0.0008)
    LK(nt, hm.outputs[0], bp.inputs['Height'])
    LK(nt, bp.outputs['Normal'], b.inputs['Normal'])
    rr = ramp(nt, [(0.3, (col[0] * 0.94, col[1] * 0.94, col[2] * 0.94, 1)), (0.7, (col[0] * 1.03, col[1] * 1.03, col[2] * 1.03, 1))])
    LK(nt, nz.outputs['Fac'], rr.inputs['Fac'])
    LK(nt, rr.outputs['Color'], b.inputs['Base Color'])
    setin(b, 'Roughness', 0.9)
    setin(b, 'Sheen Weight', 0.7); setin(b, 'Sheen Roughness', 0.5)
    setin(b, 'Specular IOR Level', 0.2)
    return m

def m_simple(name, col, rough=0.6, metal=0.0, spec=0.5):
    m, nt, b, out = mat_new(name)
    setin(b, 'Base Color', (*col, 1)); setin(b, 'Roughness', rough); setin(b, 'Metallic', metal)
    setin(b, 'Specular IOR Level', spec)
    return m

def m_leaf():
    m, nt, b, out = mat_new('Leaf')
    out.location = (0, 0)
    nt.nodes.remove(b)
    dif = N(nt, 'ShaderNodeBsdfDiffuse'); setin(dif, 'Color', (0.07, 0.16, 0.02, 1))
    tl = N(nt, 'ShaderNodeBsdfTranslucent'); setin(tl, 'Color', (0.25, 0.42, 0.04, 1))
    ms = N(nt, 'ShaderNodeMixShader'); setin(ms, 'Fac', 0.5)
    LK(nt, dif.outputs[0], ms.inputs[1]); LK(nt, tl.outputs[0], ms.inputs[2])
    LK(nt, ms.outputs[0], out.inputs['Surface'])
    return m

def m_leaf_far():
    m, nt, b, out = mat_new('LeafFar')
    nt.nodes.remove(b)
    geo = N(nt, 'ShaderNodeNewGeometry')
    nz = N(nt, 'ShaderNodeTexNoise', noise_dimensions='3D')
    setin(nz, 'Scale', 1.7); setin(nz, 'Detail', 3)
    LK(nt, geo.outputs['Position'], nz.inputs['Vector'])
    rr = ramp(nt, [(0.25, (0.035, 0.085, 0.015, 1)), (0.75, (0.16, 0.27, 0.05, 1))])
    LK(nt, nz.outputs['Fac'], rr.inputs['Fac'])
    dif = N(nt, 'ShaderNodeBsdfDiffuse')
    tl = N(nt, 'ShaderNodeBsdfTranslucent')
    LK(nt, rr.outputs['Color'], dif.inputs['Color'])
    LK(nt, rr.outputs['Color'], tl.inputs['Color'])
    ms = N(nt, 'ShaderNodeMixShader'); setin(ms, 'Fac', 0.30)
    LK(nt, dif.outputs[0], ms.inputs[1]); LK(nt, tl.outputs[0], ms.inputs[2])
    LK(nt, ms.outputs[0], out.inputs['Surface'])
    return m

def m_facade():
    m, nt, b, out = mat_new('Facade')
    geo = N(nt, 'ShaderNodeNewGeometry')
    sep = N(nt, 'ShaderNodeSeparateXYZ'); LK(nt, geo.outputs['Position'], sep.inputs['Vector'])
    mx = math_node(nt, 'PINGPONG', None, 2.6); LK(nt, sep.outputs['X'], mx.inputs[0])
    mz = math_node(nt, 'PINGPONG', None, 3.4); LK(nt, sep.outputs['Z'], mz.inputs[0])
    a = math_node(nt, 'GREATER_THAN', None, 0.55); LK(nt, mx.outputs[0], a.inputs[0])
    c = math_node(nt, 'GREATER_THAN', None, 1.0); LK(nt, mz.outputs[0], c.inputs[0])
    d = math_node(nt, 'LESS_THAN', None, 2.7); LK(nt, mz.outputs[0], d.inputs[0])
    wm = math_node(nt, 'MULTIPLY'); LK(nt, a.outputs[0], wm.inputs[0]); LK(nt, c.outputs[0], wm.inputs[1])
    wm2 = math_node(nt, 'MULTIPLY'); LK(nt, wm.outputs[0], wm2.inputs[0]); LK(nt, d.outputs[0], wm2.inputs[1])
    mxc = mix_rgba(nt, 'MIX')
    mxc.inputs[6].default_value = (0.45, 0.43, 0.40, 1)
    mxc.inputs[7].default_value = (0.05, 0.06, 0.07, 1)
    LK(nt, wm2.outputs[0], mxc.inputs[0])
    LK(nt, mxc.outputs[2], b.inputs['Base Color'])
    setin(b, 'Roughness', 0.85)
    return m

def m_foliage():
    m, nt, b, out = mat_new('FoliageFar')
    geo = N(nt, 'ShaderNodeNewGeometry')
    nz = N(nt, 'ShaderNodeTexNoise', noise_dimensions='3D')
    setin(nz, 'Scale', 3.0); setin(nz, 'Detail', 6)
    LK(nt, geo.outputs['Position'], nz.inputs['Vector'])
    rr = ramp(nt, [(0.3, (0.05, 0.12, 0.02, 1)), (0.7, (0.20, 0.34, 0.06, 1))])
    LK(nt, nz.outputs['Fac'], rr.inputs['Fac'])
    LK(nt, rr.outputs['Color'], b.inputs['Base Color'])
    setin(b, 'Roughness', 0.7)
    setin(b, 'Emission Strength', 0.0)
    return m

# ----------------------------------------------------------------- build
C_ROOM = new_coll('Room')
C_WIN = new_coll('Window')
C_FLOOR = new_coll('Floor')
C_SOFA = new_coll('Sofa')
C_OUT = new_coll('Outside')
C_LIGHT = new_coll('Lights')

MAT_WALL = m_plaster('Plaster')
MAT_CEIL = m_plaster('Ceiling', col=(0.82, 0.77, 0.68), rough=0.95)
MAT_TRIM = m_paint('PaintTrim', (0.86, 0.83, 0.75), 0.45)
MAT_FRAME = m_paint('PaintFrame', (0.88, 0.86, 0.80), 0.38)
MAT_CORN = m_paint('Stucco', (0.84, 0.78, 0.68), 0.9)
MAT_SKIRT = m_wood_skirting()
MAT_PARQ = m_parquet()
MAT_GLASS = m_glass()
MAT_FAB = m_fabric()
MAT_RAD = m_paint('RadiatorPaint', (0.84, 0.82, 0.76), 0.4)
MAT_CHROME = m_simple('Chrome', (0.85, 0.85, 0.85), 0.15, 1.0)
MAT_DARK = m_simple('Underfloor', (0.01, 0.007, 0.004), 1.0)

# ---- shell: walls, floor slab, ceiling
bm = bm_new = bmesh.new()
bm_box(bm, -0.3, 0.0, -WT, LY + 0.3, -0.3, H + 0.3)           # big wall x=0
bm_box(bm, LX, LX + 0.3, -WT, LY + 0.3, -0.3, H + 0.3)        # far-x wall
bm_box(bm, 0.0, LX, LY, LY + 0.3, -0.3, H + 0.3)              # far-y wall
make_obj('Wall_Big', bm, MAT_WALL, C_ROOM)

bm = bmesh.new()   # window wall pieces
bm_box(bm, 0.0, WX0, -WT, 0.0, -0.3, H + 0.3)
bm_box(bm, WX1, LX, -WT, 0.0, -0.3, H + 0.3)
bm_box(bm, WX0, WX1, -WT, 0.0, -0.3, WZ0)
bm_box(bm, WX0, WX1, -WT, 0.0, WZ1, H + 0.3)
make_obj('Wall_Window', bm, MAT_WALL, C_ROOM)

bm = bmesh.new()
bm_box(bm, -0.3, LX + 0.3, -WT, LY + 0.3, H, H + 0.3)
make_obj('Ceiling', bm, MAT_CEIL, C_ROOM)

bm = bmesh.new()
bm_box(bm, -0.3, LX + 0.3, -WT, LY + 0.3, -0.3, -0.02)
make_obj('Subfloor', bm, MAT_DARK, C_ROOM)

# ---- profile strips (cornice, skirting) following the room rectangle
def profile_ring(name, prof, z_ref, mat, coll, smooth=False):
    """prof: list of (offset_from_wall, dz) forming a closed polygon; mitered at all four corners."""
    bm = bmesh.new()
    n = len(prof)
    def P(wall, o, dz, t):
        z = z_ref + dz
        if wall == 0:   return (o, t, z)                 # x=0 wall, t = y
        if wall == 1:   return (t, o, z)                 # y=0 wall, t = x
        if wall == 2:   return (LX - o, t, z)            # x=LX wall
        if wall == 3:   return (t, LY - o, z)            # y=LY wall
    for wall in range(4):
        for i in range(n):
            o0, d0 = prof[i]
            o1, d1 = prof[(i + 1) % n]
            along = LY if wall in (0, 2) else LX
            vs = [bm.verts.new(P(wall, o0, d0, o0)), bm.verts.new(P(wall, o0, d0, along - o0)),
                  bm.verts.new(P(wall, o1, d1, along - o1)), bm.verts.new(P(wall, o1, d1, o1))]
            try:
                bm.faces.new(vs)
            except ValueError:
                pass
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
    ob = make_obj(name, bm, mat, coll, smooth)
    return ob

# cornice (hangs down from the ceiling)
cove = [(0.15 + 0.11 * math.cos(math.radians(a)), -0.17 + 0.11 * math.sin(math.radians(a))) for a in range(90, 181, 15)]
corn_prof = [(0.0, 0.0), (0.20, 0.0), (0.20, -0.028), (0.178, -0.04), (0.178, -0.085), (0.16, -0.095), (0.16, -0.105)]
corn_prof += [(0.15 + 0.10 * math.cos(math.radians(a)), -0.20 + 0.10 * math.sin(math.radians(a))) for a in range(90, 181, 18)]
corn_prof += [(0.05, -0.215), (0.05, -0.23), (0.0, -0.245)]
profile_ring('Cornice', corn_prof, H, MAT_CORN, C_ROOM)

# egg-and-dart band on the cornice face (offset 0.178, z H-0.04..H-0.085)
bm = bmesh.new()
def band_items(wall):
    along = LY if wall in (0, 2) else LX
    t = 0.30
    items = []
    while t < along - 0.30:
        items.append(t)
        t += 0.048
    return items
for wall in range(4):
    for t in band_items(wall):
        zc = H - 0.0625
        for kind, tt, sx, sz in (('egg', t, 0.013, 0.021), ('dart', t + 0.024, 0.006, 0.019)):
            if wall == 0:   cx, cy = 0.178, tt
            elif wall == 1: cx, cy = tt, 0.178
            elif wall == 2: cx, cy = LX - 0.178, tt
            else:           cx, cy = tt, LY - 0.178
            sph = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0)['verts']
            for v in sph:
                if wall in (0, 2):
                    v.co = Vector((cx + v.co.x * 0.010 * (1 if wall == 0 else -1), cy + v.co.y * sx, zc + v.co.z * sz))
                else:
                    v.co = Vector((cx + v.co.y * sx, cy + v.co.x * 0.010 * (1 if wall == 1 else -1), zc + v.co.z * sz))
make_obj('Cornice_Ornament', bm, MAT_CORN, C_ROOM, smooth=True)

# skirting board
sk_prof = [(0.0, 0.0), (0.016, 0.0), (0.016, 0.075), (0.020, 0.085), (0.020, 0.092), (0.012, 0.098), (0.0, 0.098)]
profile_ring('Skirting', sk_prof, 0.0, MAT_SKIRT, C_ROOM)

# ---- window ---------------------------------------------------------------
# outer frame + posts + transom
FY0, FY1 = -0.50, -0.40
POSTS = [1.15, 1.85, 2.55]
bm = bmesh.new()
bm_box(bm, WX0, WX0 + 0.07, FY0, FY1, WZ0, WZ1)
bm_box(bm, WX1 - 0.07, WX1, FY0, FY1, WZ0, WZ1)
bm_box(bm, WX0, WX1, FY0, FY1, WZ0, WZ0 + 0.07)
bm_box(bm, WX0, WX1, FY0, FY1, WZ1 - 0.07, WZ1)
for cx in POSTS:
    bm_box(bm, cx - 0.05, cx + 0.05, FY0, FY1, WZ0, WZ1)
bm_box(bm, WX0, WX1, FY0, FY1, TRZ - 0.035, TRZ + 0.035)
fr = make_obj('Window_Frame', bm, MAT_FRAME, C_WIN)
add_bevel(fr, 0.004, 2)

_edges = [WX0 + 0.07] + sum([[p - 0.05, p + 0.05] for p in POSTS], []) + [WX1 - 0.07]
cells_x = [(_edges[i], _edges[i + 1]) for i in range(0, len(_edges), 2)]
cells_z = [(WZ0 + 0.07, TRZ - 0.035), (TRZ + 0.035, WZ1 - 0.07)]
bm = bmesh.new(); bg = bmesh.new()
SW = 0.05
SY0, SY1 = -0.45, -0.38
for (xa, xb) in cells_x:
    for (za, zb) in cells_z:
        bm_box(bm, xa, xa + SW, SY0, SY1, za, zb)
        bm_box(bm, xb - SW, xb, SY0, SY1, za, zb)
        bm_box(bm, xa, xb, SY0, SY1, za, za + SW)
        bm_box(bm, xa, xb, SY0, SY1, zb - SW, zb)
        bm_box(bg, xa + SW - 0.005, xb - SW + 0.005, -0.428, -0.422, za + SW - 0.005, zb - SW + 0.005)
sa = make_obj('Window_Sashes', bm, MAT_FRAME, C_WIN)
add_bevel(sa, 0.003, 2)
make_obj('Window_Glass', bg, MAT_GLASS, C_WIN)

# interior trim, sill, apron
bm = bmesh.new()
TW, TT = 0.12, 0.028
bm_box(bm, WX0 - TW, WX0, 0.0, TT, WZ0 - 0.02, WZ1 + 0.055)
bm_box(bm, WX1, WX1 + TW, 0.0, TT, WZ0 - 0.02, WZ1 + 0.055)
bm_box(bm, WX0 - TW, WX1 + TW, 0.0, TT, WZ1, WZ1 + 0.055)
bm_box(bm, WX0 - 0.10, WX1 + 0.10, 0.0, 0.085, WZ0 - 0.04, WZ0)                       # sill board
bm_box(bm, WX0, WX1, -0.40, 0.0, WZ0 - 0.04, WZ0)                                     # sill inside reveal
bm_box(bm, WX0 - TW, WX1 + TW, 0.0, TT, WZ0 - 0.14, WZ0 - 0.04)                       # apron
tr = make_obj('Window_Trim', bm, MAT_TRIM, C_WIN)
add_bevel(tr, 0.004, 2)
# inner reveal bead
bm = bmesh.new()
bm_box(bm, WX0 - 0.0, WX0 + 0.02, 0.0, 0.020, WZ0, WZ1)
bm_box(bm, WX1 - 0.02, WX1, 0.0, 0.020, WZ0, WZ1)
bm_box(bm, WX0, WX1, 0.0, 0.020, WZ1 - 0.02, WZ1)
make_obj('Window_Bead', bm, MAT_TRIM, C_WIN)

# window handle (olive) on first casement
bm = bmesh.new()
bm_box(bm, 1.060, 1.074, -0.38, -0.376, 1.45, 1.62)
bm_box(bm, 1.064, 1.070, -0.376, -0.34, 1.53, 1.54)
bm_box(bm, 1.064, 1.070, -0.355, -0.345, 1.45, 1.54)
make_obj('Window_Handle', bm, MAT_CHROME, C_WIN)

# radiator (cast iron sections)
bm = bmesh.new()
RX0, RN, RPITCH = 0.70, 20, 0.062
for i in range(RN):
    x = RX0 + i * RPITCH
    for j, (ya, yb) in enumerate(((0.045, 0.080), (0.090, 0.125))):
        r = bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=10, radius1=0.016, radius2=0.016, depth=0.60,
                                  matrix=Matrix.Translation(((x + 0.012), (ya + yb) / 2, 0.42)))
        for v in r['verts']:
            pass
    bm_box(bm, x + 0.004, x + 0.036, 0.075, 0.095, 0.15, 0.70)
bm_box(bm, RX0 - 0.01, RX0 + RN * RPITCH, 0.045, 0.125, 0.70, 0.735)
bm_box(bm, RX0 - 0.01, RX0 + RN * RPITCH, 0.045, 0.125, 0.115, 0.15)
rad = make_obj('Radiator', bm, MAT_RAD, C_ROOM, smooth=True)
for i in range(4):
    bm = bmesh.new()
    bm_box(bm, RX0 + (0 if i < 2 else RN * RPITCH - 0.06) + (0.0 if i % 2 == 0 else 0.0), RX0 + (0.05 if i < 2 else RN * RPITCH - 0.01),
           0.05, 0.12, 0.0, 0.115)
    make_obj('RadFoot%d' % i, bm, MAT_RAD, C_ROOM)
    break

# ---- herringbone parquet --------------------------------------------------
def build_parquet():
    L, W, GAP = 0.42, 0.07, 0.0016
    T = 0.016
    me = bpy.data.meshes.new('Parquet')
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new('UVMap')
    rnd1 = bm.verts.layers.float.new('rnd')
    rnd2 = bm.verts.layers.float.new('rnd2')
    s2 = math.sqrt(0.5)
    def rot(p, q):
        return (p * s2 + q * s2, -p * s2 + q * s2)
    count = 0
    M = 0.3
    for k in range(-200, 200):
        for mm in range(-60, 60):
            ox, oy = k * W - mm * L, k * W + mm * L
            for kind in (0, 1):
                if kind == 0:   # horizontal in pattern frame
                    p0, q0, pw, qh = ox, oy, L, W
                else:           # vertical
                    p0, q0, pw, qh = ox + L, oy + W - L, W, L
                cp, cq = p0 + pw / 2, q0 + qh / 2
                cx, cy = rot(cp, cq)
                if not (-M <= cx <= LX + M and -M <= cy <= LY + M):
                    continue
                r1, r2 = random.random(), random.random()
                # corners in pattern frame (shrunk by gap)
                hw, hh = pw / 2 - GAP, qh / 2 - GAP
                corners = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
                top, bot = [], []
                for (a, b) in corners:
                    x, y = rot(cp + a, cq + b)
                    top.append(bm.verts.new((x, y, 0.0)))
                    bot.append(bm.verts.new((x, y, -T)))
                for v in top + bot:
                    v[rnd1] = r1
                    v[rnd2] = r2
                f = bm.faces.new(top)
                # UV: u along the long axis
                long_is_p = pw > qh
                for lp, (a, b) in zip(f.loops, corners):
                    if long_is_p:
                        lp[uv].uv = ((a + hw) , (b + hh))
                    else:
                        lp[uv].uv = ((b + hh), (a + hw))
                for i in range(4):
                    j = (i + 1) % 4
                    bm.faces.new([top[i], bot[i], bot[j], top[j]])
                count += 1
    print('parquet boards', count)
    bm.normal_update()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(me)
    bm.free()
    me.materials.append(MAT_PARQ)
    ob = bpy.data.objects.new('Parquet', me)
    C_FLOOR.objects.link(ob)
    add_bevel(ob, 0.0005, 1)
    return ob
build_parquet()

# ---- sofa -----------------------------------------------------------------
def soft_block(name, x0, x1, y0, y1, z0, z1, rad, mat, coll, seg=6):
    bm = bmesh.new()
    bm_box(bm, x0, x1, y0, y1, z0, z1)
    ob = make_obj(name, bm, mat, coll, smooth=True)
    m = add_bevel(ob, rad, seg, harden=True)
    m.limit_method = 'NONE'
    m.profile = 0.6
    return ob

SX0 = float(ARGS.get('sofax', 1.4)); SY0_ = float(ARGS.get('sofay', 0.62)); SLEN = 2.5; SDEP = 0.92
# low modular sofa along the window wall: arm block at the -x end, back along the wall side, loose pillow
soft_block('Sofa_Base', SX0 + 0.01, SX0 + SLEN - 0.01, SY0_ + 0.01, SY0_ + SDEP - 0.025, 0.06, 0.30, 0.06, MAT_FAB, C_SOFA)
_mid = SX0 + 0.28 + (SLEN - 0.30) / 2
soft_block('Sofa_Seat1', SX0 + 0.28, _mid - 0.004, SY0_ + 0.30, SY0_ + SDEP - 0.0, 0.30, 0.47, 0.08, MAT_FAB, C_SOFA)
soft_block('Sofa_Seat2', _mid + 0.004, SX0 + SLEN - 0.02, SY0_ + 0.30, SY0_ + SDEP - 0.0, 0.30, 0.47, 0.08, MAT_FAB, C_SOFA)
soft_block('Sofa_Arm', SX0, SX0 + 0.30, SY0_, SY0_ + SDEP + 0.012, 0.06, 0.66, 0.11, MAT_FAB, C_SOFA)
soft_block('Sofa_Back', SX0 + 0.20, SX0 + SLEN, SY0_, SY0_ + 0.32, 0.30, 0.74, 0.11, MAT_FAB, C_SOFA)
soft_block('Sofa_Pillow', SX0 + 0.55, SX0 + 1.05, SY0_ + 0.30, SY0_ + 0.50, 0.46, 0.86, 0.08, MAT_FAB, C_SOFA)

# ---- freestanding clothing rail (matte black, T-feet) ---------------------
if ARGS.get('rail', '0') == '1':
    RAIL_Y0, RAIL_Y1 = float(ARGS.get('rail_y0', 1.95)), float(ARGS.get('rail_y1', 3.2))
    RAIL_X = float(ARGS.get('rail_x', 0.62))
    RH, R_T = 1.62, 0.0125
    MAT_RAILBLK = m_simple('RailBlack', (0.018, 0.018, 0.019), 0.42, 0.0, 0.5)
    def cyl(bm, p0, p1, r, seg=24):
        p0, p1 = Vector(p0), Vector(p1)
        d = p1 - p0
        q = d.normalized().to_track_quat('Z', 'Y')
        m = Matrix.Translation((p0 + p1) / 2) @ q.to_matrix().to_4x4()
        bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg, radius1=r, radius2=r, depth=d.length, matrix=m)
    bm = bmesh.new()
    for y in (RAIL_Y0, RAIL_Y1):
        cyl(bm, (RAIL_X, y, 0.03), (RAIL_X, y, RH), R_T)                 # post
        cyl(bm, (RAIL_X - 0.27, y, 0.03), (RAIL_X + 0.27, y, 0.03), 0.02)  # foot bar
        for fx in (-0.27, 0.27):                                            # rubber-look caps
            cyl(bm, (RAIL_X + fx, y, 0.0), (RAIL_X + fx, y, 0.03), 0.018)
    cyl(bm, (RAIL_X, RAIL_Y0, RH), (RAIL_X, RAIL_Y1, RH), R_T)             # top hanging rail
    cyl(bm, (RAIL_X, RAIL_Y0, 0.33), (RAIL_X, RAIL_Y1, 0.33), 0.010)        # lower shelf rail
    for y in (RAIL_Y0, RAIL_Y1):                                            # end caps / joints
        ico = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=0.018, matrix=Matrix.Translation((RAIL_X, y, RH)))
    make_obj('ClothingRail', bm, MAT_RAILBLK, C_SOFA, smooth=True)

# ---- Lasse II (real product rack, appended read-only from the working file) --
LASSE_BLEND = ARGS.get('lasse_file', r"C:\Users\HI\Desktop\Measurement Product Final\Lasse II\Lasse II.blend")
if ARGS.get('lasse', '1') == '1':
    with bpy.data.libraries.load(LASSE_BLEND, link=False) as (_src, _dst):
        _dst.collections = ['Product']
    prod = _dst.collections[0]
    scene.collection.children.link(prod)
    bpy.context.view_layer.update()
    root = bpy.data.objects['Lasse_II_0013_group']
    # rack frame: wall plates at y=-7.69 (wall side), width along x, floor at z=-1.522
    PIV = Vector((0.136, -7.69, -1.522))
    LY_C = float(ARGS.get('lasse_y', 2.35))      # centre of the rack along the big wall
    M = Matrix.Translation((0.002, LY_C, 0.0)) @ Matrix.Rotation(math.radians(-90), 4, 'Z') @ Matrix.Translation(-PIV)
    root.matrix_world = M @ root.matrix_world
    bpy.context.view_layer.update()
    # ---- clothes on black hangers (from Altbau Room v25: same garments as the reference look)
    if ARGS.get('clothes', '1') == '1':
        CL_BLEND = ARGS.get('clothes_file', r"C:\Users\HI\Desktop\Altbau Room\Altbau Room v25.blend")
        _want = ['Hangers027', 'Hangers_coat', 'Hangers_shirt', 'Hangers_sweater', 'jacket_004',
                 'buttons_jacket_004', 'chemise', "t'shirt 2.002", 'substance_file_018']
        with bpy.data.libraries.load(CL_BLEND, link=False) as (_s2, _d2):
            _d2.objects = [n for n in _want if n in _s2.objects]
        C_CLOTH = new_coll('Clothes')
        _cl = {o.name: o for o in _d2.objects}
        for o in _d2.objects:
            C_CLOTH.objects.link(o)
        bpy.context.view_layer.update()
        # Fit the hangers to the thin garments: make the arms thin like a flat plastic hanger (x = rail axis in the
        # v25 frame), keep their full length and the full-size hook, and give the hook its chrome material back.
        MAT_HBLACK = m_simple('HangerBlack', (0.012, 0.012, 0.013), 0.38, 0.0, 0.5)
        HXS = float(ARGS.get('hanger_xs', 0.18))        # arm thickness factor
        HYS = float(ARGS.get('hanger_ys', 0.78))        # arm length factor
        HOOK_Z = 1.955                                  # v25 frame: everything above this z is neck + hook
        _fit_done = set()
        for hn in ('Hangers027', 'Hangers_coat', 'Hangers_shirt', 'Hangers_sweater'):
            if hn not in _cl:
                continue
            ho = _cl[hn]
            me = ho.data
            if me.name in _fit_done:
                continue
            _fit_done.add(me.name)
            Wm = ho.matrix_world
            body = [v for v in me.vertices if (Wm @ v.co).z < HOOK_Z]
            if body:
                _xs = [(Wm @ v.co).x for v in body]
                _ys = [(Wm @ v.co).y for v in body]
                xcen = (min(_xs) + max(_xs)) / 2
                ycen = (min(_ys) + max(_ys)) / 2
                for v in body:
                    w = Wm @ v.co
                    w.x = xcen + (w.x - xcen) * HXS
                    w.y = ycen + (w.y - ycen) * HYS
                    v.co = Wm.inverted() @ w
            for p in me.polygons:
                if all((Wm @ me.vertices[i].co).z >= HOOK_Z for i in p.vertices):
                    p.material_index = 1                  # hook -> Hanger_Chrome
            me.update()
        for hn in ('Hangers027', 'Hangers_coat', 'Hangers_shirt', 'Hangers_sweater'):
            if hn in _cl:
                for i, sl in enumerate(_cl[hn].material_slots):
                    if sl.material and 'Wood' in sl.material.name:
                        _cl[hn].material_slots[i].material = MAT_HBLACK
        # paste the group exactly as arranged in Altbau Room v25 (one rigid move, same order and spacing):
        # cream shirt, dark knit, blue blazer, brown coat
        _order = ['Hangers_shirt', 'Hangers_sweater', 'Hangers027', 'Hangers_coat']
        CL_Y = float(ARGS.get('clothes_y', 1.9))      # group centre along the wall (left bay)
        CL_DZ = float(ARGS.get('clothes_dz', -0.05))
        CL_ROT = float(ARGS.get('clothes_rot', 90))     # +90: cream on the left, -90: mirrored
        RAIL_X = 0.002 + (-7.38 + 7.69)                  # rail distance from the wall
        _cx, _cy = [], []
        for hn in _order:
            h = _cl[hn]
            bb = [h.matrix_world @ Vector(c) for c in h.bound_box]
            _cx.append((min(v.x for v in bb) + max(v.x for v in bb)) / 2)
            _cy.append((min(v.y for v in bb) + max(v.y for v in bb)) / 2)
        xc, yc = sum(_cx) / len(_cx), sum(_cy) / len(_cy)
        Mc = Matrix.Translation((RAIL_X, CL_Y, CL_DZ)) @ Matrix.Rotation(math.radians(CL_ROT), 4, 'Z') @ Matrix.Translation((-xc, -yc, 0))
        SPF = float(ARGS.get('clothes_spf', 0.75))      # squeeze the v25 spacing so the group fits one rack section
        for hn, _x in zip(_order, _cx):
            _sh = Matrix.Translation((0, (_x - xc) * (SPF - 1.0) * math.sin(math.radians(CL_ROT)), 0))
            _cl[hn].matrix_world = _sh @ Mc @ _cl[hn].matrix_world
        # lift the garments on their hangers so the hanger arms sit inside the shoulders
        GDZ = float(ARGS.get('garment_dz', 0.0))
        for _n in ('jacket_004', 'buttons_jacket_004', 'chemise', "t'shirt 2.002", 'substance_file_018'):
            if _n in _cl and GDZ:
                _g = _cl[_n]
                _P = _g.parent.matrix_world @ _g.matrix_parent_inverse
                _g.location = _g.location + (_P.inverted().to_3x3() @ Vector((0, 0, GDZ)))
        bpy.context.view_layer.update()
        if ARGS.get('hide_garments', '0') == '1':
            for _n in ('jacket_004', 'buttons_jacket_004', 'chemise', "t'shirt 2.002", 'substance_file_018'):
                if _n in _cl:
                    _cl[_n].hide_render = True
        bpy.context.view_layer.update()
        # soft warm fill light that only lights the clothes and hangers (light linking)
        FILL_W = float(ARGS.get('fill', 90))
        if FILL_W > 0:
            _recv = bpy.data.collections.new('ClothesReceivers')
            for o in _d2.objects:
                _recv.objects.link(o)
            fl = bpy.data.lights.new('ClothesFill', 'AREA')
            fl.shape = 'RECTANGLE'; fl.size = 2.0; fl.size_y = 1.6
            fl.energy = FILL_W
            fl.color = (1.0, 0.90, 0.78)
            flo = bpy.data.objects.new('ClothesFill', fl)
            C_LIGHT.objects.link(flo)
            flo.location = (2.3, CL_Y + 0.4, 2.5)
            _d = Vector((RAIL_X, CL_Y, 1.5)) - flo.location
            flo.rotation_euler = _d.to_track_quat('-Z', 'Y').to_euler()
            flo.light_linking.receiver_collection = _recv

# ---- outside: facade, trees, shadow-casting twigs -------------------------
bm = bmesh.new()
bm_box(bm, -40, 12, -20, -18, -8, 16)
make_obj('Facade', bm, m_facade(), C_OUT).visible_shadow = False
bm = bmesh.new()
bm_box(bm, -60, 60, -60, 20, -8.0, -4.0)
make_obj('Street', bm, m_simple('Street', (0.15, 0.15, 0.15), 0.9), C_OUT).visible_shadow = False

# (far foliage is generated after the camera exists)

# twigs + leaves between sun and window (cast the dappled shadows)
def leaf_bm(bm, pos, axis, normal, length, width):
    ax = axis.normalized()
    nz = normal.normalized()
    side = ax.cross(nz).normalized()
    pts = []
    prof = [(0.0, 0.0), (0.2, 0.30), (0.5, 0.50), (0.8, 0.30), (1.0, 0.0)]
    left = [bm.verts.new(pos + ax * (t * length) + side * (w * width) + nz * (math.sin(t * math.pi) * 0.01)) for (t, w) in prof]
    right = [bm.verts.new(pos + ax * (t * length) - side * (w * width) + nz * (math.sin(t * math.pi) * 0.01)) for (t, w) in prof]
    bm.faces.new([left[0], left[1], left[2], left[3], left[4], right[3], right[2], right[1]])

bm_leaf = bmesh.new()
bm_twig = bmesh.new()
n_tw = int(ARGS.get('twigs', 120))
for i in range(n_tw):
    xw = random.uniform(0.3, 3.4)
    zw = random.choice([random.uniform(0.7, 2.0), random.uniform(0.7, 3.0), random.uniform(1.8, 3.2)])
    s = random.uniform(2.5, 7.5)
    base = Vector((xw, -0.3, zw)) + TO_SUN * s
    ang = random.uniform(0, math.tau)
    direction = Vector((math.cos(ang), math.sin(ang), random.uniform(-0.35, 0.25))).normalized()
    ln = random.uniform(0.9, 1.8)
    # twig
    mid = base + direction * ln / 2
    q = direction.to_track_quat('Z', 'Y')
    mt = Matrix.Translation(mid) @ q.to_matrix().to_4x4()
    bmesh.ops.create_cone(bm_twig, cap_ends=False, segments=5, radius1=0.006, radius2=0.002, depth=ln, matrix=mt)
    t = 0.08
    flip = 1
    while t < ln:
        p = base + direction * t
        up = Vector((random.uniform(-.3, .3), random.uniform(-.3, .3), 1.0)).normalized()
        side = direction.cross(up).normalized()
        axis = (side * flip * random.uniform(0.7, 1.0) + direction * random.uniform(0.2, 0.7) + Vector((0, 0, random.uniform(-0.3, 0.3)))).normalized()
        nrm = up.cross(axis).cross(axis).normalized() if abs(up.dot(axis)) < 0.95 else up
        L_ = random.uniform(0.08, 0.13)
        leaf_bm(bm_leaf, p, axis, up, L_, L_ * 0.55)
        flip = -flip
        t += random.uniform(0.05, 0.09)
make_obj('Leaves', bm_leaf, m_leaf(), C_OUT)
make_obj('Twigs', bm_twig, m_simple('Bark', (0.07, 0.05, 0.03), 0.9), C_OUT)

# ---- lights, world, camera --------------------------------------------------
sun = bpy.data.lights.new('Sun', 'SUN')
sun.energy = SUN_STR
sun.angle = math.radians(float(ARGS.get('sunang', 0.7)))
sun.color = (1.0, 0.90, 0.76)
sob = bpy.data.objects.new('Sun', sun)
C_LIGHT.objects.link(sob)
sob.rotation_euler = (-TO_SUN).to_track_quat('-Z', 'Y').to_euler()

port = bpy.data.lights.new('WindowPortal', 'AREA')
port.shape = 'RECTANGLE'
port.size = WX1 - WX0
port.size_y = WZ1 - WZ0
try:
    port.cycles.is_portal = True
except Exception:
    try:
        port.is_portal = True
    except Exception as e:
        print('portal unavailable', e)
pob = bpy.data.objects.new('WindowPortal', port)
C_LIGHT.objects.link(pob)
pob.location = ((WX0 + WX1) / 2, -0.04, (WZ0 + WZ1) / 2)
pob.rotation_euler = (math.radians(90), 0, 0)

world = bpy.data.worlds.new('World')
scene.world = world
world.use_nodes = True
wn = world.node_tree
wn.nodes.clear()
wout = wn.nodes.new('ShaderNodeOutputWorld')
bg = wn.nodes.new('ShaderNodeBackground')
sky = wn.nodes.new('ShaderNodeTexSky')
try:
    models = [i.identifier for i in sky.bl_rna.properties['sky_type'].enum_items]
    print('sky models', models)
    for cand in models:
        if 'MULTIPLE' in cand or 'NISHITA' in cand:
            sky.sky_type = cand
            break
    sky.sun_disc = False
    sky.sun_elevation = SUN_EL
    sky.sun_rotation = math.atan2(TO_SUN.x, TO_SUN.y) * -1 + math.pi
    sky.air_density = 1.0
except Exception as e:
    print('sky err', e)
bg.inputs['Strength'].default_value = SKY_STR
tint = wn.nodes.new('ShaderNodeMix'); tint.data_type = 'RGBA'; tint.blend_type = 'MULTIPLY'
tint.inputs[0].default_value = 1.0
tint.inputs[7].default_value = (1.0, 0.88, 0.72, 1.0)
wn.links.new(sky.outputs['Color'], tint.inputs[6])
wn.links.new(tint.outputs[2], bg.inputs['Color'])
wn.links.new(bg.outputs['Background'], wout.inputs['Surface'])

cam_d = bpy.data.cameras.new('Camera')
cam_d.lens = float(ARGS.get('lens', 30))
cam_d.sensor_width = 36
cam_d.clip_start = 0.05
cam_d.clip_end = 200
cam = bpy.data.objects.new('Camera', cam_d)
scene.collection.objects.link(cam)
cam.location = Vector((float(ARGS.get('cx', 3.44)), float(ARGS.get('cy', 3.14)), float(ARGS.get('cz', 1.2))))
fwd = Vector((-0.918, -0.397, float(ARGS.get('pitch', 0.0)))).normalized()
cam.rotation_euler = fwd.to_track_quat('-Z', 'Y').to_euler()
scene.camera = cam
if 'look' in ARGS:
    _lk = Vector([float(v) for v in ARGS['look'].split(',')])
    cam.rotation_euler = (_lk - cam.location).to_track_quat('-Z', 'Y').to_euler()
    fwd = (_lk - cam.location).normalized()

# ---- far foliage seen through the window: leaf clumps along camera rays
def cam_ray(u, v):
    f = fwd.normalized()
    rt = f.cross(Vector((0, 0, 1))).normalized()
    up = rt.cross(f).normalized()
    k = 36.0 / cam_d.lens
    return (f + rt * ((u - 0.5) * k) + up * ((0.5 - v) * k)).normalized()
bm_far = bmesh.new()
bm_trunk = bmesh.new()
nclump = int(ARGS.get('clumps', 120))
for i in range(nclump):
    u = random.uniform(-0.02, 0.12)
    v = 0.30 + 0.34 * random.random() ** 0.7
    t = random.uniform(8.0, 18.0)
    ctr = cam.location + cam_ray(u, v) * t
    for j in range(random.randint(25, 60)):
        p = ctr + Vector((random.gauss(0, 0.55), random.gauss(0, 0.45), random.gauss(0, 0.45)))
        ax = Vector((random.gauss(0, 1), random.gauss(0, 1), random.gauss(0, 1))).normalized()
        nm = Vector((random.gauss(0, 1), random.gauss(0, 1), random.gauss(0, 1))).normalized()
        if abs(ax.dot(nm)) > 0.9 or p.y > -2.0:
            continue
        nm = (nm - ax * ax.dot(nm)).normalized()
        L_ = random.uniform(0.22, 0.42)
        leaf_bm(bm_far, p, ax, nm, L_, L_ * 0.5)
ob = make_obj('Foliage_Far', bm_far, m_leaf_far(), C_OUT)
ob.visible_shadow = False

# ---- render settings
r = scene.render
r.engine = 'CYCLES'
r.resolution_x = r.resolution_y = RES
r.resolution_percentage = 100
r.image_settings.file_format = 'PNG'
r.image_settings.color_mode = 'RGB'
cy = scene.cycles
cy.samples = SAMPLES
cy.use_adaptive_sampling = True
cy.adaptive_threshold = 0.02
cy.use_denoising = True
try:
    cy.denoiser = 'OPENIMAGEDENOISE'
except Exception:
    pass
cy.max_bounces = 10
cy.diffuse_bounces = 6
cy.glossy_bounces = 4
cy.transmission_bounces = 6
cy.sample_clamp_indirect = 4.0
cy.caustics_reflective = False
cy.caustics_refractive = False
try:
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'OPTIX'
    prefs.get_devices()
    for d in prefs.devices:
        d.use = (d.type == 'OPTIX')
    cy.device = 'GPU'
except Exception as e:
    print('gpu setup err', e)
vs = scene.view_settings
try:
    vs.view_transform = ARGS.get('view', 'AgX')
except Exception as e:
    print('view transform', e)
try:
    vs.look = ARGS.get('look', 'None')
except Exception as e:
    print('look', e, [i.identifier for i in vs.bl_rna.properties['look'].enum_items])
vs.exposure = EXPOSURE

if OUT_BLEND:
    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND, compress=True)
if OUT_PNG:
    scene.render.filepath = OUT_PNG
    bpy.ops.render.render(write_still=True)
    print('RENDER DONE', OUT_PNG)
