# HPSketch

This repository provides source data for our paper:

[A History-based parametric CAD sketch dataset with advanced engineering commands](https://www.sciencedirect.com/science/article/abs/pii/S0010448525000107)

HPSketch is the first history-based parametric CAD sketch dataset to support advanced engineering commands.

A gallery of HPSketch dataset is shown above.

![image](https://github.com/fazhihe/HPSketch/blob/main/A%20gallery%20of%20HPSketch.png)

The vector format of HPSketch is in the folder of ./data.

The citation of this article is as follows:

```
@article{FAN2025103848,
title = {A history-based parametric CAD sketch dataset with advanced engineering commands},
journal = {Computer-Aided Design},
volume = {182},
pages = {103848},
year = {2025},
doi = {https://doi.org/10.1016/j.cad.2025.103848},
url = {https://www.sciencedirect.com/science/article/pii/S0010448525000107},
author = {Rubin Fan and Fazhi He and Yuxin Liu and Jing Lin},
}
```

## Visualization and Export

We provide an online website to visualize CAD models.

[http://whucad.l2.bb1a.cn/](http://whucad.l2.bb1a.cn/)

Through the above web interface (without the need to install industrial CAD software), WHUCAD vector files in `.h5` format can be processed. These may include vectors from the WHUCAD dataset itself, or vectors predicted/generated/reconstructed by AI systems based on WHUCAD vectors through relevant vector computation—for example, new vectors generated via GAN or Diffusion networks.

Three representative types of geometric models are supported (CAD / CAE / Visualization):

* **stp (Brep)** – CAD geometric models in boundary representation (B-rep) format.
* **stl (Mesh)** – Visualization geometric models in mesh representation.
* **icem (ICEM)** – Pre-processing geometric models compatible with CAE software such as Ansys.

This service is intended for academic research purposes only and is not for commercial use.
