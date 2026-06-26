import copy
import glob
import json
import os

import numpy as np

from Catia_utils import *
from CAD_Class import *
from Geometry_utils import *
import win32com.client

vec = np.array([SOL_VEC,
       [LINE_IDX, 176, 80, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
       [LINE_IDX, 223, 128, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
       [LINE_IDX, 176, 176, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
       [LINE_IDX, 128, 128, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
       [SELECT_IDX, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 1, 1, 1, -1, -1, -1, -1],
       [SELECT_IDX, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 1, 1, 2, -1, -1, -1, -1],
       [FILLET_IDX, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 32, -1, -1, -1, -1, -1, -1, -1, -1],
       EOS_VEC])

cad = Macro_Seq.from_vector(vec, is_numerical=True, n=256)
# cad.numericalize(n=ARGS_N)
# vec = cad.to_vector(MAX_N_EXT, MAX_N_LOOPS, MAX_N_CURVES, MAX_TOTAL_LEN, pad=False)

catia = win32com.client.Dispatch('catia.application')
catia.visible = 1
doc = catia.documents.add('Part')
part = doc.part
create_CAD_CATIA(cad, catia, doc, part, only_sketch=True)