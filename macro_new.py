import numpy as np

ALL_COMMANDS = ['Line', 'Arc', 'Circle', 'Spline', 'SCP', 'EOS', 'SOL', 'Ellipse', 'Parabola', 'Hyperbola', 'Select', 'Mirror', 'Rotate', 'Chamfer', 'Fillet', 'Constraint']
LINE_IDX = ALL_COMMANDS.index('Line')                                           # 0
ARC_IDX = ALL_COMMANDS.index('Arc')                                             # 1
CIRCLE_IDX = ALL_COMMANDS.index('Circle')                                       # 2
SPLINE_IDX = ALL_COMMANDS.index('Spline')                                       # 3
SCP_IDX = ALL_COMMANDS.index('SCP')                                             # 4     Spline Control Point
EOS_IDX = ALL_COMMANDS.index('EOS')                                             # 5
SOL_IDX = ALL_COMMANDS.index('SOL')                                             # 6
ELLIPSE_IDX = ALL_COMMANDS.index('Ellipse')                                     # 7
PARA_IDX = ALL_COMMANDS.index('Parabola')                                       # 8
HYPER_IDX = ALL_COMMANDS.index('Hyperbola')                                     # 9
SELECT_IDX = ALL_COMMANDS.index('Select')                                       # 10
MIRROR_IDX = ALL_COMMANDS.index('Mirror')                                       # 11
ROTATE_IDX = ALL_COMMANDS.index('Rotate')                                       # 12
CHAMFER_IDX = ALL_COMMANDS.index('Chamfer')                                     # 13
FILLET_IDX = ALL_COMMANDS.index('Fillet')                                       # 14

CONSTRAINT_IDX = ALL_COMMANDS.index('Constraint')                               # 15

SELECT_TYPE = ['Loop', 'Wire', 'Point', 'OriginElements', 'ControlPoint']

# 底层标号
CONSTRAINT_TYPE = ['catCstTypeReference', 'catCstTypeDistance', 'catCstTypeOn', 'catCstTypeConcentricity', 'catCstTypeTangency', 'catCstTypeLength', 'catCstTypeAngle', 
                  'catCstTypePlanarAngle', 'catCstTypeParallelism', 'catCstTypeAxisParallelism', 'catCstTypeHorizontality', 'catCstTypePerpendicularity', 'catCstTypeAxisPerpendicularity', 
                  'catCstTypeVerticality', 'catCstTypeRadius', 'catCstTypeSymmetry', 'catCstTypeMidPoint', 'catCstTypeEquidistance', 'catCstTypeMajorRadius', 'catCstTypeMinorRadius']
# 表层标号
CONSTRAINT_VEC_TYPE = ['catCstTypeReference', 'catCstTypeDistance', 'catCstTypeOn', 'catCstTypeConcentricity', 'catCstTypeTangency', 'catCstTypeLength', 'catCstTypeAngle', 
                      'catCstTypeParallelism', 'catCstTypeHorizontality', 'catCstTypePerpendicularity', 'catCstTypeVerticality', 'catCstTypeRadius', 'catCstTypeSymmetry', 
                      'catCstTypeMidPoint', 'catCstTypeEquidistance', 'catCstTypeMajorRadius', 'catCstTypeMinorRadius']
# 元素为1
CONSTRAINT_MONO_TYPE = ['catCstTypeReference', 'catCstTypeLength', 'catCstTypeRadius', 'catCstTypeMajorRadius', 'catCstTypeMinorRadius']
# 元素为2
CONSTRAINT_BI_TYPE = ['catCstTypeDistance', 'catCstTypeOn', 'catCstTypeConcentricity', 'catCstTypeTangency', 'catCstTypeAngle', 'catCstTypeParallelism', 
                      'catCstTypeHorizontality', 'catCstTypePerpendicularity', 'catCstTypeVerticality', 'catCstTypeMidPoint']
# 元素为3
CONSTRAINT_TRI_TYPE = ['catCstTypeSymmetry', 'catCstTypeEquidistance']


PAD_VAL = -1
N_ARGS_SKETCH = 5  # sketch parameters: x, y, alpha, f, r
N_ARGS_APPEND = 8  # r2, axis_angle, rotate_angle, c1, c2, fr, x2, y2
N_ARGS_SELECT = 3  # select type, sketch_no, wire_no
N_ARGS_CONSTRAINTS = 4 # constraint type, dimension 1, 2, 3
N_ARGS = N_ARGS_SKETCH + N_ARGS_APPEND + N_ARGS_SELECT + N_ARGS_CONSTRAINTS
SOL_VEC = np.array([SOL_IDX, *([PAD_VAL] * N_ARGS)])
EOS_VEC = np.array([EOS_IDX, *([PAD_VAL] * N_ARGS)])
SPLINE_VEC = np.array([SPLINE_IDX, *([PAD_VAL] * N_ARGS)])

# 便于观察的放大倍率
SKETCH_SCALE = 100

# 指令对应参数的掩码，需要扩展到22位
CMD_ARGS_MASK = np.array([[1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],                     # line
                          [1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],                     # arc
                          [1, 1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],                     # circle
                          [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],                     # spline
                          [1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],                     # scp
                          [*[0]*N_ARGS],                # EOS
                          [*[0]*N_ARGS],                # SOL
                          [1, 1, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # Ellipse
                          [1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0],  # Parabola
                          [1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0],  # Hyperbola
                          [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0],  # Select
                          [1, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # Mirror
                          [1, 1, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # Rotate
                          [0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # Chamfer
                          [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # Fillet
                          
                          [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],  # Constraint(other)
                          [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 1],  # Constraint(dimension11: Radius、MajorRadius、MinorRadius）
                          [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1],  # Constraint(dimension12: Length、Distance)
                          [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 1]   # Constraint(dimension21: Angle)
])

NORM_FACTOR = 0.75 # scale factor for normalization to prevent overflow during augmentation

MAX_N_EXT = 10 # maximum number of extrusion
MAX_N_LOOPS = 6 # maximum number of loops per sketch
MAX_N_CURVES = 15 # maximum number of curves per loop
MAX_TOTAL_LEN = 100 # maximum cad sequence length
ARGS_DIM = 256

ARGS_N = 256

def Get_integer_and_fraction(num, n=256):
    # fraction = num
    # num = np.trunc(num).clip(min=0, max=n-1).astype(np.int)
    # fraction = ((fraction - num) * n).round().clip(min=0, max=n-1).astype(np.int)
    # return num, fraction
    return np.round(num), 0
