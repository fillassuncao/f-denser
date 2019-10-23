import random
import keras
from keras import backend
from multiprocessing import Pool
from time import time
import tensorflow
import numpy as np
from keras.callbacks import Callback, ModelCheckpoint
import os
from data import load_dataset

DEBUG = False

class TimedStopping(keras.callbacks.Callback):
    """
        Stop training when maximum time has passed.
        Code from:
            https://github.com/keras-team/keras-contrib/issues/87

        Attributes
        ----------
        start_time : float
            time when the training started
        
        seconds : float 
            maximum time before stopping.
        
        verbose : bool 
            verbosity mode.


        Methods
        -------
        on_train_begin(logs)
            method called upon training beginning

        on_epoch_end(epoch, logs={})
            method called after the end of each training epoch
    """

    def __init__(self, seconds=None, verbose=0):
        """
        Parameters
        ----------
        seconds : float
            maximum time before stopping.

        vebose : bool
            verbosity mode
        """

        super(keras.callbacks.Callback, self).__init__()

        self.start_time = 0
        self.seconds = seconds
        self.verbose = verbose


    def on_train_begin(self, logs={}):
        """
            Method called upon training beginning

            Parameters
            ----------
            logs : dict
                training logs
        """

        self.start_time = time()

    def on_epoch_end(self, epoch, logs={}):
        """
            Method called after the end of each training epoch.
            Checks if the maximum time has passed

            Parameters
            ----------
            epoch : int
                current epoch

            logs : dict
                training logs
        """

        if time() - self.start_time > self.seconds:
            self.model.stop_training = True
            if self.verbose:
                print('Stopping after %s seconds.' % self.seconds)


class Evaluator:
    """
        Stores the dataset, maps the phenotype into a trainable model, and
        evaluates it


        Attributes
        ----------
        dataset : dict
            dataset instances and partitions

        fitness_metric : function
            fitness_metric (y_true, y_pred)
            y_pred are the confidences


        Methods
        -------
        get_layers(phenotype)
            parses the phenotype corresponding to the layers
            auxiliary function of the assemble_network function

        get_learning(learning)
            parses the phenotype corresponding to the learning
            auxiliary function of the assemble_optimiser function

        assemble_network(keras_layers, input_size)
            maps the layers phenotype into a keras model

        assemble_optimiser(learning)
            maps the learning into a keras optimiser

        evaluate(phenotype, load_prev_weights, weights_save_path, parent_weights_path,
                 train_time, num_epochs, datagen=None, input_size=(32, 32, 3))
            evaluates the keras model using the keras optimiser

        testing_performance(self, model_path)
            compute testing performance of the model
    """

    def __init__(self, dataset, fitness_metric):
        """
            Creates the Evaluator instance and loads the dataset.

            Parameters
            ----------
            dataset : str
                dataset to be loaded
        """

        self.dataset = load_dataset(dataset)
        self.fitness_metric = fitness_metric


    def get_layers(self, phenotype):
        """
            Parses the phenotype corresponding to the layers.
            Auxiliary function of the assemble_network function.

            Parameters
            ----------
            phenotye : str
                individual layers phenotype

            Returns
            -------
            layers : list
                list of tuples (layer_type : str, node properties : dict)
        """

        raw_phenotype = phenotype.split(' ')

        idx = 0
        first = True
        node_type, node_val = raw_phenotype[idx].split(':')
        layers = []

        while idx < len(raw_phenotype):
            if node_type == 'layer':
                if not first:
                    layers.append((layer_type, node_properties))
                else:
                    first = False
                layer_type = node_val
                node_properties = {}
            else:
                node_properties[node_type] = node_val.split(',')

            idx += 1
            if idx < len(raw_phenotype):
                node_type, node_val = raw_phenotype[idx].split(':')

        layers.append((layer_type, node_properties))

        return layers


    def get_learning(self, learning):
        """
            Parses the phenotype corresponding to the learning
            Auxiliary function of the assemble_optimiser function

            Parameters
            ----------
            learning : str
                learning phenotype of the individual

            Returns
            -------
            learning_params : dict
                learning parameters
        """

        raw_learning = learning.split(' ')

        idx = 0
        learning_params = {}
        while idx < len(raw_learning):
            param_name, param_value = raw_learning[idx].split(':')
            learning_params[param_name] = param_value.split(',')
            idx += 1

        for _key_ in sorted(list(learning_params.keys())):
            if len(learning_params[_key_]) == 1:
                try:
                    learning_params[_key_] = eval(learning_params[_key_][0])
                except NameError:
                    learning_params[_key_] = learning_params[_key_][0]

        return learning_params


    def assemble_network(self, keras_layers, input_size):
        """
            Maps the layers phenotype into a keras model

            Parameters
            ----------
            keras_layers : list
                output from get_layers

            input_size : tuple
                network input shape

            Returns
            -------
            model : keras.models.Model
                keras trainable model
        """

        #input layer
        inputs = keras.layers.Input(shape=input_size)

        #Create layers -- ADD NEW LAYERS HERE
        layers = []
        for layer_type, layer_params in keras_layers:
            #convolutional layer
            if layer_type == 'conv':
                conv_layer = keras.layers.Conv2D(filters=int(layer_params['num-filters'][0]),
                                                 kernel_size=(int(layer_params['filter-shape'][0]), int(layer_params['filter-shape'][0])),
                                                 strides=(int(layer_params['stride'][0]), int(layer_params['stride'][0])),
                                                 padding=layer_params['padding'][0],
                                                 activation=layer_params['act'][0],
                                                 use_bias=eval(layer_params['bias'][0]),
                                                 kernel_initializer='he_normal',
                                                 kernel_regularizer=keras.regularizers.l2(0.0005))
                layers.append(conv_layer)

            #batch-normalisation
            elif layer_type == 'batch-norm':
                batch_norm = keras.layers.BatchNormalization()
                layers.append(batch_norm)

            #average pooling layer
            elif layer_type == 'pool-avg':
                pool_avg = keras.layers.AveragePooling2D(pool_size=(int(layer_params['kernel-size'][0]), int(layer_params['kernel-size'][0])),
                                                         strides=int(layer_params['stride'][0]),
                                                         padding=layer_params['padding'][0])
                layers.append(pool_avg)

            #max pooling layer
            elif layer_type == 'pool-max':
                pool_max = keras.layers.MaxPooling2D(pool_size=(int(layer_params['kernel-size'][0]), int(layer_params['kernel-size'][0])),
                                                             strides=int(layer_params['stride'][0]),
                                                             padding=layer_params['padding'][0])
                layers.append(pool_max)

            #fully-connected layer
            elif layer_type == 'fc':
                fc = keras.layers.Dense(int(layer_params['num-units'][0]),
                                             activation=layer_params['act'][0],
                                             use_bias=eval(layer_params['bias'][0]),
                                             kernel_initializer='he_normal',
                                             kernel_regularizer=keras.regularizers.l2(0.0005))
                layers.append(fc)

            #dropout layer
            elif layer_type == 'dropout':
                dropout = keras.layers.Dropout(rate=float(layer_params['rate'][0]))
                layers.append(dropout)


            #END ADD NEW LAYERS


        #Connection between layers
        for layer in keras_layers:
            layer[1]['input'] = map(int, layer[1]['input'])


        first_fc = True
        data_layers = []
        invalid_layers = []

        for layer_idx, layer in enumerate(layers):
            
            try:
                if len(keras_layers[layer_idx][1]['input']) == 1:
                    if keras_layers[layer_idx][1]['input'][0] == -1:
                        data_layers.append(layer(inputs))
                    else:
                        if keras_layers[layer_idx][0] == 'fc' and first_fc:
                            first_fc = False
                            flatten = keras.layers.Flatten()(data_layers[keras_layers[layer_idx][1]['input'][0]])
                            data_layers.append(layer(flatten))
                            continue

                        data_layers.append(layer(data_layers[keras_layers[layer_idx][1]['input'][0]]))

                else:
                    #Get minimum shape: when merging layers all the signals are converted to the minimum shape
                    minimum_shape = input_size[0]
                    for input_idx in keras_layers[layer_idx][1]['input']:
                        if input_idx != -1 and input_idx not in invalid_layers:
                            if data_layers[input_idx].shape[-3:][0] < minimum_shape:
                                minimum_shape = int(data_layers[input_idx].shape[-3:][0])

                    #Reshape signals to the same shape
                    merge_signals = []
                    for input_idx in keras_layers[layer_idx][1]['input']:
                        if input_idx == -1:
                            if inputs.shape[-3:][0] > minimum_shape:
                                actual_shape = int(inputs.shape[-3:][0])
                                merge_signals.append(keras.layers.MaxPooling2D(pool_size=(actual_shape-(minimum_shape-1), actual_shape-(minimum_shape-1)), strides=1)(inputs))
                            else:
                                merge_signals.append(inputs)

                        elif input_idx not in invalid_layers:
                            if data_layers[input_idx].shape[-3:][0] > minimum_shape:
                                actual_shape = int(data_layers[input_idx].shape[-3:][0])
                                merge_signals.append(keras.layers.MaxPooling2D(pool_size=(actual_shape-(minimum_shape-1), actual_shape-(minimum_shape-1)), strides=1)(data_layers[input_idx]))
                            else:
                                merge_signals.append(data_layers[input_idx])

                    if len(merge_signals) == 1:
                        merged_signal = merge_signals[0]
                    elif len(merge_signals) > 1:
                        merged_signal = keras.layers.concatenate(merge_signals)
                    else:
                        merged_signal = data_layers[-1]

                    data_layers.append(layer(merged_signal))
            except ValueError as e:
                data_layers.append(data_layers[-1])
                invalid_layers.append(layer_idx)
                if DEBUG:
                    print keras_layers[layer_idx][0]
                    print e

        
        model = keras.models.Model(inputs=inputs, outputs=data_layers[-1])
        
        if DEBUG:
            model.summary()

        return model


    def assemble_optimiser(self, learning):
        """
            Maps the learning into a keras optimiser

            Parameters
            ----------
            learning : dict
                output of get_learning

            Returns
            -------
            optimiser : keras.optimizers.Optimizer
                keras optimiser that will be later used to train the model
        """

        if learning['learning'] == 'rmsprop':
            return keras.optimizers.RMSprop(lr = float(learning['lr']),
                                            rho = float(learning['rho']),
                                            decay = float(learning['decay']))
        
        elif learning['learning'] == 'gradient-descent':
            return keras.optimizers.SGD(lr = float(learning['lr']),
                                        momentum = float(learning['momentum']),
                                        decay = float(learning['decay']),
                                        nesterov = bool(learning['nesterov']))

        elif learning['learning'] == 'adam':
            return keras.optimizers.Adam(lr = float(learning['lr']),
                                         beta_1 = float(learning['beta1']),
                                         beta_2 = float(learning['beta2']),
                                         decay = float(learning['decay']))


    def evaluate(self, phenotype, load_prev_weights, weights_save_path, parent_weights_path,\
                 train_time, num_epochs, datagen=None, datagen_test = None, input_size=(32, 32, 3)):
        """
            Evaluates the keras model using the keras optimiser

            Parameters
            ----------
            phenotype : str
                individual phenotype

            load_prev_weights : bool
                resume training from a previous train or not

            weights_save_path : str
                path where to save the model weights after training

            parent_weights_path : str
                path to the weights of the previous training

            train_time : float
                maximum training time

            num_epochs : int
                maximum number of epochs

            datagen : keras.preprocessing.image.ImageDataGenerator
                Data augmentation method image data generator

            input_size : tuple
                dataset input shape
                

            Returns
            -------
            score_history : dict
                training data: loss and accuracy
        """

        model_phenotype, learning_phenotype = phenotype.split('learning:')
        learning_phenotype = 'learning:'+learning_phenotype.rstrip().lstrip()
        model_phenotype = model_phenotype.rstrip().lstrip().replace('  ', ' ')

        keras_layers = self.get_layers(model_phenotype)
        keras_learning = self.get_learning(learning_phenotype)
        batch_size = int(keras_learning['batch_size'])
        
        if load_prev_weights:
            model = keras.models.load_model(parent_weights_path.replace('.hdf5', '.h5'))

        else:
            model = self.assemble_network(keras_layers, input_size)

            opt = self.assemble_optimiser(keras_learning)
            model.compile(loss='categorical_crossentropy',
                          optimizer=opt,
                          metrics=['accuracy'])

        #early stopping
        early_stop = keras.callbacks.EarlyStopping(monitor='val_loss', patience=int(keras_learning['early_stop']))

        #time based stopping
        time_stop = TimedStopping(seconds=train_time, verbose=DEBUG)

        #save individual with the lowest validation loss
        monitor = ModelCheckpoint(weights_save_path, monitor='val_loss', verbose=0, save_best_only=True)

        trainable_count = int(np.sum([backend.count_params(p) for p in set(model.trainable_weights)]))

        if datagen is not None:
            score = model.fit_generator(datagen.flow(self.dataset['evo_x_train'],
                                                 self.dataset['evo_y_train'],
                                                 batch_size=batch_size),
                                        steps_per_epoch=(self.dataset['evo_x_train'].shape[0]//batch_size),
                                        epochs=int(keras_learning['epochs']),
                                        validation_data=(datagen_test.flow(self.dataset['evo_x_val'], self.dataset['evo_y_val'], batch_size=batch_size)),
                                        validation_steps = (self.dataset['evo_x_val'].shape[0]//batch_size),
                                        callbacks = [early_stop, time_stop, monitor],
                                        initial_epoch = num_epochs,
                                        verbose= DEBUG)
        else:
            score = model.fit(x = self.dataset['evo_x_train'], y = self.dataset['evo_y_train'],
                              batch_size = batch_size,
                              epochs = int(keras_learning['epochs']),
                              steps_per_epoch=(self.dataset['evo_x_train'].shape[0]//batch_size),
                              validation_data=(self.dataset['evo_x_val'], self.dataset['evo_y_val']),
                              callbacks = [early_stop, time_stop, monitor],
                              initial_epoch = num_epochs,
                              verbose = DEBUG)


        #load weights with the lowest val loss
        if os.path.isfile(weights_save_path):
            model.load_weights(weights_save_path)
        #save final moodel to file
        model.save(weights_save_path.replace('.hdf5', '.h5'))

        #measure test performance
        if datagen_test is None:
            y_pred_test = model.predict(self.dataset['evo_x_test'], batch_size=batch_size, verbose=0)
        else:
            y_pred_test = model.predict_generator(datagen_test.flow(self.dataset['evo_x_test'], batch_size=100, shuffle=False), steps =self.dataset['evo_x_test'].shape[0]//100, verbose=DEBUG)

        accuracy_test = self.fitness_metric(self.dataset['evo_y_test'], y_pred_test)

        if DEBUG:
            print phenotype, accuracy_test

        score.history['trainable_parameters'] = trainable_count
        score.history['accuracy_test'] = accuracy_test

        return score.history


    def testing_performance(self, model_path):
        """
            Compute testing performance of the model

            Parameters
            ----------
            model_path : str
                Path to the model .h5 file


            Returns
            -------
            accuracy : float
                Model accuracy
        """

        model = keras.models.load_model(model_path)
        y_pred = model.predict(self.dataset['x_test'])
        accuracy = self.fitness_metric(self.dataset['y_test'], y_pred)
        return accuracy



def evaluate(args):
    """
        Function used to deploy a new process to train a candidate solution.
        Each candidate solution is trained in a separe process to avoid memory problems.

        Parameters
        ----------
        args : tuple
            cnn_eval : Evaluator
                network evaluator

            phenotype : str
                individual phenotype

            load_prev_weights : bool
                resume training from a previous train or not

            weights_save_path : str
                path where to save the model weights after training

            parent_weights_path : str
                path to the weights of the previous training

            train_time : float
                maximum training time

            num_epochs : int
                maximum number of epochs

        Returns
        -------
        score_history : dict
            training data: loss and accuracy
    """

    cnn_eval, phenotype, load_prev_weights, weights_save_path, parent_weights_path, train_time, num_epochs, datagen, datagen_test = args

    try:
        return cnn_eval.evaluate(phenotype, load_prev_weights, weights_save_path, parent_weights_path, train_time, num_epochs, datagen, datagen_test)
    except tensorflow.errors.ResourceExhaustedError as e:
        return None


class Module:
    """
        Each of the units of the outer-level genotype


        Attributes
        ----------
        module : str
            non-terminal symbol

        min_expansions : int
            minimum expansions of the block

        max_expansions : int
            maximum expansions of the block

        levels_back : dict
            number of previous layers a given layer can receive as input

        layers : list
            list of layers of the module

        connections : dict
            list of connetions of each layer


        Methods
        -------
            initialise(grammar, reuse)
                Randomly creates a module
    """

    def __init__(self, module, min_expansions, max_expansions, levels_back, min_expansins):
        """
            Parameters
            ----------
            module : str
                non-terminal symbol

            min_expansions : int
                minimum expansions of the block
        
            max_expansions : int
                maximum expansions of the block

            levels_back : dict
                number of previous layers a given layer can receive as input
        """

        self.module = module
        self.min_expansions = min_expansins
        self.max_expansions = max_expansions
        self.levels_back = levels_back
        self.layers = []
        self.connections = {}

    def initialise(self, grammar, reuse, init_max):
        """
            Randomly creates a module

            Parameters
            ----------
            grammar : Grammar
                grammar instace that stores the expansion rules

            reuse : float
                likelihood of reusing an existing layer

            Returns
            -------
            score_history : dict
                training data: loss and accuracy
        """

        num_expansions = random.choice(init_max[self.module])

        #Initialise layers
        for idx in range(num_expansions):
            if idx>0 and random.random() <= reuse:
                r_idx = random.randint(0, idx-1)
                self.layers.append(self.layers[r_idx])
            else:
                self.layers.append(grammar.initialise(self.module))

        #Initialise connections: feed-forward and allowing skip-connections
        self.connections = {}
        for layer_idx in range(num_expansions):
            if layer_idx == 0:
                #the -1 layer is the input
                self.connections[layer_idx] = [-1,]
            else:
                connection_possibilities = list(range(max(0, layer_idx-self.levels_back), layer_idx-1))
                if len(connection_possibilities) < self.levels_back-1:
                    connection_possibilities.append(-1)

                sample_size = random.randint(0, len(connection_possibilities))
                
                self.connections[layer_idx] = [layer_idx-1] 
                if sample_size > 0:
                    self.connections[layer_idx] += random.sample(connection_possibilities, sample_size)



class Individual:
    """
        Candidate solution.


        Attributes
        ----------
        network_structure : list
            ordered list of tuples formated as follows 
            [(non-terminal, min_expansions, max_expansions), ...]

        output_rule : str
            output non-terminal symbol

        macro_rules : list
            list of non-terminals (str) with the marco rules (e.g., learning)

        modules : list
            list of Modules (genotype) of the layers

        output : dict
            output rule genotype

        macro : list
            list of Modules (genotype) for the macro rules

        phenotype : str
            phenotype of the candidate solution

        fitness : float
            fitness value of the candidate solution

        metrics : dict
            training metrics

        num_epochs : int
            number of performed epochs during training

        trainable_parameters : int
            number of trainable parameters of the network

        time : float
            network training time

        current_time : float
            performed network training time

        train_time : float
            maximum training time

        id : int
            individual unique identifier


        Methods
        -------
            initialise(grammar, levels_back, reuse)
                Randomly creates a candidate solution

            decode(grammar)
                Maps the genotype to the phenotype

            evaluate(grammar, cnn_eval, weights_save_path, parent_weights_path='')
                Performs the evaluation of a candidate solution
    """


    def __init__(self, network_structure, macro_rules, output_rule, ind_id):
        """
            Parameters
            ----------
            network_structure : list
                ordered list of tuples formated as follows 
                [(non-terminal, min_expansions, max_expansions), ...]

            macro_rules : list
                list of non-terminals (str) with the marco rules (e.g., learning)

            output_rule : str
                output non-terminal symbol

            ind_id : int
                individual unique identifier
        """


        self.network_structure = network_structure
        self.output_rule = output_rule
        self.macro_rules = macro_rules
        self.modules = []
        self.output = None
        self.macro = []
        self.phenotype = None
        self.fitness = None
        self.metrics = None
        self.num_epochs = None
        self.trainable_parameters = None
        self.time = None
        self.current_time = 0
        self.train_time = 0
        self.id = ind_id

    def initialise(self, grammar, levels_back, reuse, init_max):
        """
            Randomly creates a candidate solution

            Parameters
            ----------
            grammar : Grammar
                grammar instaces that stores the expansion rules

            levels_back : dict
                number of previous layers a given layer can receive as input

            reuse : float
                likelihood of reusing an existing layer

            Returns
            -------
            candidate_solution : Individual
                randomly created candidate solution
        """

        for non_terminal, min_expansions, max_expansions in self.network_structure:
            new_module = Module(non_terminal, min_expansions, max_expansions, levels_back[non_terminal], min_expansions)
            new_module.initialise(grammar, reuse, init_max)

            self.modules.append(new_module)

        #Initialise output
        self.output = grammar.initialise(self.output_rule)

        # Initialise the macro structure: learning, data augmentation, etc.
        for rule in self.macro_rules:
            self.macro.append(grammar.initialise(rule))

        return self


    def decode(self, grammar):
        """
            Maps the genotype to the phenotype

            Parameters
            ----------
            grammar : Grammar
                grammar instaces that stores the expansion rules

            Returns
            -------
            phenotype : str
                phenotype of the individual to be used in the mapping to the keras model.
        """

        phenotype = ''
        offset = 0
        layer_counter = 0
        for module in self.modules:
            offset = layer_counter
            for layer_idx, layer_genotype in enumerate(module.layers):
                layer_counter += 1
                phenotype += ' ' + grammar.decode(module.module, layer_genotype)+ ' input:'+",".join(map(str, np.array(module.connections[layer_idx])+offset))

        phenotype += ' '+grammar.decode(self.output_rule, self.output)+' input:'+str(layer_counter-1)

        for rule_idx, macro_rule in enumerate(self.macro_rules):
            phenotype += ' '+grammar.decode(macro_rule, self.macro[rule_idx])

        self.phenotype = phenotype.rstrip().lstrip()
        return self.phenotype


    def evaluate(self, grammar, cnn_eval, datagen, datagen_test, weights_save_path, parent_weights_path=''):
        """
            Performs the evaluation of a candidate solution

            Parameters
            ----------
            grammar : Grammar
                grammar instaces that stores the expansion rules

            cnn_eval : Evaluator
                Evaluator instance used to train the networks

            datagen : keras.preprocessing.image.ImageDataGenerator
                Data augmentation method image data generator
        
            weights_save_path : str
                path where to save the model weights after training

            parent_weights_path : str
                path to the weights of the previous training


            Returns
            -------
            fitness : float
                quality of the candidate solutions
        """

        phenotype = self.decode(grammar)
        start = time()
        pool = Pool(processes=1)

        load_prev_weights = True
        if self.current_time == 0:
            load_prev_weights = False

        train_time = self.train_time - self.current_time

        result = pool.apply_async(evaluate, [(cnn_eval, phenotype, load_prev_weights,\
                                              weights_save_path, parent_weights_path,\
                                              train_time, self.num_epochs, datagen, datagen_test)])
        pool.close()
        pool.join()
        metrics = result.get()

        if metrics is not None:
            self.metrics = metrics
            self.fitness = self.metrics['accuracy_test']
            self.num_epochs += len(self.metrics['val_acc'])
            self.trainable_parameters = self.metrics['trainable_parameters']
            self.current_time += (self.train_time-self.current_time)
        else:
            self.metrics = None
            self.fitness = -1
            self.num_epochs = 0
            self.trainable_parameters = -1
            self.current_time = 0

        self.time = time() - start

        return self.fitness

