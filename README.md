# Placement
This python package intends to be a collection of Virtual Network Embedding (VNE)
algorithms running on top of networkx package. Each placement
algorithm is contained within the mapper module as a class inheriting from the
AbstractMapper. Every AbstractMapper has an associated AbstractChecker to
ensure that received graphs contain the required information.


## Implemented algorithms
The table below lists the algorithms that are implemented
in this package, each of them has been presented an tested
in the referenced papers.


| Algorithm name | name in package | Paper |
|--------------------------|-------|------------------------|
| **CAPEX-g** | `GreedyCostMapper`         | [1] |
| **LongRun-g** | `GreedyFogCostMapper`      | [1] |
| **OKpi** |   `FPTASMapper`             | [2] |
| **FMC**  |   `FMCMapper`               | [3] |
| **impr-Υ** | `ConstructiveMapperFromFractional` | [4] |



## Cite algorithms

In case you use any of the algorithms in your
research, consider citing the works in the table.
See the BibTeX below:


**[1]** J. Martín-Pérez, L. Cominardi, C. J. Bernardos and A. Mourad, "5GEN: A tool to generate 5G infrastructure graphs," 2019 IEEE Conference on Standards for Communications and Networking (CSCN), 2019, pp. 1-4, doi: 10.1109/CSCN.2019.8931334.
```bibtex
@INPROCEEDINGS{8931334,  author={Martín-Pérez, Jorge and Cominardi, Luca and Bernardos, Carlos J. and Mourad, Alain},  booktitle={2019 IEEE Conference on Standards for Communications and Networking (CSCN)},   title={5GEN: A tool to generate 5G infrastructure graphs},   year={2019},  volume={},  number={},  pages={1-4},  doi={10.1109/CSCN.2019.8931334}}
```

**[2]** J. Martín-Peréz, F. Malandrino, C. F. Chiasserini and C. J. Bernardos, "OKpi: All-KPI Network Slicing Through Efficient Resource Allocation," IEEE INFOCOM 2020 - IEEE Conference on Computer Communications, 2020, pp. 804-813, doi: 10.1109/INFOCOM41043.2020.9155263.
```bibtex
@INPROCEEDINGS{9155263,  author={Martín-Peréz, J. and Malandrino, F. and Chiasserini, C. F. and Bernardos, C. J.},  booktitle={IEEE INFOCOM 2020 - IEEE Conference on Computer Communications},   title={OKpi: All-KPI Network Slicing Through Efficient Resource Allocation},   year={2020},  volume={},  number={},  pages={804-813},  doi={10.1109/INFOCOM41043.2020.9155263}}
```

**[3]** Chen, Yan-Ting, and Wanjiun Liao. "Mobility-aware service function chaining in 5g wireless networks with mobile edge computing." ICC 2019-2019 IEEE International Conference on Communications (ICC). IEEE, 2019.
```bibtex
@INPROCEEDINGS{8761306,  author={Chen, Yan-Ting and Liao, Wanjiun},  booktitle={ICC 2019 - 2019 IEEE International Conference on Communications (ICC)},   title={Mobility-Aware Service Function Chaining in 5G Wireless Networks with Mobile Edge Computing},   year={2019},  volume={},  number={},  pages={1-6},  doi={10.1109/ICC.2019.8761306}}
```

**[4]** B. Nemeth, N. Molner, J. Martinperez, C. J. Bernardos, A. De la Oliva and B. Sonkoly, "Delay and reliability-constrained VNF placement on mobile and volatile 5G infrastructure," in IEEE Transactions on Mobile Computing, doi: 10.1109/TMC.2021.3055426.
```bibtex
@ARTICLE{9339982,  author={Nemeth, Balazs and Molner, Nuria and Martinperez, Jorge and Bernardos, Carlos J. and De la Oliva, Antonio and Sonkoly, Balazs},  journal={IEEE Transactions on Mobile Computing},   title={Delay and reliability-constrained VNF placement on mobile and volatile 5G infrastructure},   year={2021},  volume={},  number={},  pages={1-1},  doi={10.1109/TMC.2021.3055426}}
```
