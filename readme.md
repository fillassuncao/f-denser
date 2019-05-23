# Fast-DENSER++: Fast Deep Evolutionary Network Structured Representation

F-DENSER++ is a new extension to Deep Evolutionary Network Structured Evolution (DENSER). The vast majority of NeuroEvolution methods that optimise Deep Artificial Neural Networks (DANNs) only evaluate the candidate solutions for a fixed amount of epochs; this makes it difficult to effectively assess the learning strategy, and requires the best generated network to be further trained after evolution. F-DENSER++ enables the training time of the candidate solutions to grow continuously as necessary, i.e., in the initial generations the candidate solutions are trained for shorter times, and as generations proceed it is expected that longer training cycles enable better performances. Consequently, the models discovered by F-DENSER++ are fully-trained DANNs, and are ready for deployment after evolution, without the need for further training. 

```
@article{assunccao2019fast,
  title={Fast-DENSER++: Evolving Fully-Trained Deep Artificial Neural Networks},
  author={Assun{\c{c}}{\~a}o, Filipe and Louren{\c{c}}o, Nuno and Machado, Penousal and Ribeiro, Bernardete},
  journal={arXiv preprint arXiv:1905.02969},
  year={2019}
}

@article{assunccao2018denser,
  title={DENSER: deep evolutionary network structured representation},
  author={Assun{\c{c}}ao, Filipe and Louren{\c{c}}o, Nuno and Machado, Penousal and Ribeiro, Bernardete},
  journal={Genetic Programming and Evolvable Machines},
  pages={1--31},
  year={2018},
  publisher={Springer}
}
```

### Requirements
Currently this codebase only works with python 2. The following libraries are needed: tensorflow, keras, numpy, and sklearn, scipy, and jsmin. 

### Usage

`python f_denser.py -d <dataset> -c <config> -r <run> -g <grammar>`

-d [mandatory] can assume one of the following values: mnist, fashion-mnist, svhn, cifar10, cifar100-fine, cifar100-coarse, tiny-imagenet

-c [mandatory] is the path to a json configuration file. Check example/config.json for an example

-r [optional] the the run to be performed [0-14]

-g [mandatory] path to the grammar file to be used. Check example/modules.grammar for an example 

### Support

Any questions, comments or suggestion should be directed to Filipe Assunção ([fga@dei.uc.pt](mailto:fga@dei.uc.pt))