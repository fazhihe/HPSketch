import os
import random
import shutil

output_path = 'C:/Users/45088/Desktop/output'

file_name_list = []
glob_list = []
trunk_list = sorted(os.listdir(output_path))

name_map = {}

for i in trunk_list:
    if i[:2] not in name_map.keys():
        name_map[i[:2]] = 1
    else:
        name_map[i[:2]] += 1
print(name_map)