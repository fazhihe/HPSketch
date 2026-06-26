import os
import h5py
import numpy as np

from macro_new import *
input_path = 'D:/Dataset/Random_Argument_Process/only_sketch_argu'
output_path = 'D:/Dataset/Random_Argument_Process/DeepSketch'

trunk_list = os.listdir(input_path)

for trunk in trunk_list:
    file_list = os.listdir(os.path.join(input_path, trunk))
    if not os.path.exists(os.path.join(output_path, trunk)):
        os.makedirs(os.path.join(output_path, trunk))
    for file in file_list:
        file_path = os.path.join(input_path, trunk, file)
        output_file_path = os.path.join(output_path, trunk, file)
        macro_vec = h5py.File(file_path, 'r')['vec'][:, :6]
        i = 0
        while i < len(macro_vec):
            if macro_vec[i][0] == 7:
                macro_vec = np.concatenate([macro_vec[:i], macro_vec[i+1:]])
                i -= 1
            i += 1

        with h5py.File(output_file_path) as f:
            f['vec'] = macro_vec
        print(file_path, 'OK')

