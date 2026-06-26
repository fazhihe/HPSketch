import os
import random
import shutil

input_path = 'C:/Users/45088/Desktop/9.19任务-本科班名单/9.19任务-本科班名单'
output_path = 'C:/Users/45088/Desktop/output'

file_name_list = []
glob_list = []
trunk_list = sorted(os.listdir(input_path))

for trunk in trunk_list:
    files_list = sorted(os.listdir(os.path.join(input_path, trunk)))
    for file in files_list:
        file_name_list.append(os.path.join(input_path, trunk, file))

random.shuffle(file_name_list)

stu_name_list = ['王子贤', '朱湛', '刘鼎益', '彭斯宇', '徐少栋', '张宸', '扎西顿珠', '盛宇', '吴嵘嵩', '杨昊', '陈炳逸', '李遥禹', '柴添宁', '周子乔', '楼子涵', '蒋敬', '付饶', '谢昊阳', '郝秋阳', '张鹏', '张鸿雨', '池涵', '吕湘东', '赵宇彪', '蔡昱', '白一兵', '解迎烁', '胡城玮', '刘修齐', '杨子豪', '李一航', '韩祖臣', '王映轩', '王权', '董文广', '聂智伟', '杨璐', '齐嘉欣', '张蔚', '刘承志', '王军懿', '李欣怡', '许伊昆', '赵卓勋', '项绍翀', '袁渝祥', '马文秀', '徐含蕊' ]

file_point = 0
for stu in stu_name_list:
    j = 0
    while j < 30:
        file_name = file_name_list[file_point % len(file_name_list)][len(input_path) + 1:]
        file_name = file_name[file_name.find('\\') + 1:]

        shutil.copy(file_name_list[file_point % len(file_name_list)], output_path + '/' + stu + '_' + file_name)
        file_point += 1
        j += 1

