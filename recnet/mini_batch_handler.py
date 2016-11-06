from __future__ import print_function
__author__ = 'Joerg Franke'
"""
This file contains the organization of the mini-batches. It loads existing mini-batch-data and creates mini-batches from a
list of sequences/file. This includes bucketing, padding and mask creation.
"""

######                           Imports
########################################
import os
import klepto
import numpy as np
import theano


######          Mini Batch Handler Class
########################################
class MiniBatchHandler:

    def __init__(self,rng, prm):

        self.rng = rng
        self.prm_data = prm.data
        self.prm_struct = prm.struct
        self.ctc = prm.optimize['loss_function'] == "CTC"


    ###### Check out if data exists and is consistent
    ########################################
    def check_out_data_set(self):

        for set in ['train', 'valid', 'test']:
            if self.prm_data[set + "_data_name"] != None:
                file_name = self.prm_data["data_location"] + self.prm_data[set + "_data_name"]
                try:
                    d = klepto.archives.file_archive(file_name, cached=True,serialized=True)
                    d.load()
                    data_set_x = d['x']
                    data_set_y = d['y']
                    d.clear()
                    self.prm_data[set + "_set_len"] = data_set_x.__len__()
                    if data_set_x.__len__() != data_set_y.__len__():
                        raise Warning("x and y " + set + "_data_name have not the same length")
                    self.prm_data["x_size"] = data_set_x[0].shape[1]
                    if self.prm_data["x_size"] != int(self.prm_struct["net_size"][0]):
                        raise Warning(set + " data x size and net input size are unequal")
                    if self.ctc == False:
                        self.prm_data["y_size"] = data_set_y[0].shape[1]
                        if self.prm_data["y_size"] != int(self.prm_struct["net_size"][-1]):
                            raise Warning(set + " data y size and net input size are unequal")
                    else:
                        self.prm_data["y_size"] = self.prm_struct["net_size"][-1]
                    del data_set_x
                    del data_set_y
                    self.prm_data[set + "_batch_quantity"] = int(np.trunc(self.prm_data[set + "_set_len" ]/self.prm_data["batch_size"]))
                    self.prm_data["checked_data"][set] = True
                except KeyError:
                    raise Warning("data_location or " + set + "_data_name wrong")





    ###### Create mini batches and storage them in klepto files
    ########################################
    def create_mini_batches(self, set):

        if self.prm_data["checked_data"][set] == False:
            self.check_out_data_set()

        if set != "train" and set != "valid" and set != "test":
            raise Warning("set must be 'train' or 'valid' or 'test'")

        if os.path.isfile(self.prm_data["mini_batch_location"] + "mb_of_" + self.prm_data[set + "_data_name"]):
            self.delete_mini_batches(set)

        file_name = self.prm_data["data_location"] + self.prm_data[set + "_data_name"]
        d = klepto.archives.file_archive(file_name, cached=True,serialized=True)
        d.load()
        data_set_x = d['x']
        data_set_y = d['y']
        d.clear()

        self.prm_data[set + "_data_x_len"] = [i.__len__() for i in data_set_x]
        self.prm_data[set + "_data_y_len"]= [i.__len__() for i in data_set_y]
        if self.ctc == False:
            if not np.array_equal(self.prm_data[set + "_data_x_len"], self.prm_data[set + "_data_y_len"]):
                raise Warning(set + " x and y sequences have not the same length")

        sample_order = np.arange(0,self.prm_data[set + "_set_len" ])
        if set == "train":
            sample_order = self.rng.permutation(sample_order)

        data_mb_x = []
        data_mb_y = []
        data_mask = []

        for j in range(self.prm_data[set + "_batch_quantity"]):

            sample_selection = sample_order[ j*self.prm_data["batch_size"]:j*self.prm_data["batch_size"]+self.prm_data["batch_size"] ]
            max_seq_len = np.max(  [data_set_x[i].__len__() for i in sample_selection])
            if self.ctc == True:
                max_y_len = np.max(  [data_set_y[i].__len__() for i in sample_selection])

            mb_train_x = np.zeros([max_seq_len, self.prm_data["batch_size"], self.prm_data["x_size"]])
            if self.ctc == False:
                mb_train_y = np.zeros([max_seq_len, self.prm_data["batch_size"], self.prm_data["y_size"]])
            else:
                #mb_train_y = np.zeros([2*max_y_len+1]) #todo rebuild 2, batch size 1, no batch dimension
                mb_train_y = np.zeros([self.prm_data["batch_size"], 2*max_y_len+1]) #todo rebuild # in case of ctc y is [batchsize, 2*max seq length + 2] shape[1] y_seq+blanks+number_y_sqe_length
            mb_mask = np.zeros([max_seq_len, self.prm_data["batch_size"], 1])

            for k in range(self.prm_data["batch_size"]):
                s = sample_selection[k]
                sample_length =  self.prm_data[set + "_data_x_len"][s]
                mb_train_x[:sample_length,k,:] = data_set_x[s][:sample_length]
                if self.ctc == False:
                    mb_train_y[:sample_length,k,:] = data_set_y[s][:sample_length]
                else:
                    y1 = [self.prm_struct["net_size"][-1]-1]
                    for char in data_set_y[s]:
                        y1 += [char, self.prm_struct["net_size"][-1]-1  ]

                    #mb_train_y[:] = y1
                    mb_train_y[k,:y1.__len__()] = y1 #todo rebuild 2, batch size 1, no batch dimension


                    #mb_train_y[k,-1] = y1.__len__() #todo waste
                    #mb_train_y[k,:] = np.array(mb_train_y[k,:], dtype=theano.config.floatx)
                mb_mask[:sample_length,k,:y1.__len__()] = np.ones([sample_length,1])

            data_mb_x.append(mb_train_x.astype(theano.config.floatX))
            data_mb_y.append(mb_train_y.astype(theano.config.floatX))
            data_mask.append(mb_mask.astype(theano.config.floatX))

        file_name = self.prm_data["mini_batch_location"] + "mb_of_" + self.prm_data[set + "_data_name"]
        d = klepto.archives.file_archive(file_name, cached=True,serialized=True)
        d['x'] = data_mb_x
        d['y'] = data_mb_y
        d['m'] = data_mask
        d.dump()
        d.clear()


    ###### Delete stored mini batch klepto files
    ########################################
    def delete_mini_batches(self, set):
        file_name = self.prm_data["mini_batch_location"] + "mb_of_" + self.prm_data[set + "_data_name"]
        os.remove(file_name)


    ######  Load from mini batch klepto file
    ########################################
    def load_mini_batches(self, set):
        file_name = self.prm_data["mini_batch_location"] + "mb_of_" + self.prm_data[set + "_data_name"]
        d = klepto.archives.file_archive(file_name, cached=True,serialized=True)
        d.load()
        data_mb_set_x = d['x']
        data_mb_set_y = d['y']
        data_mb_set_m = d['m']
        d.clear()
        return data_mb_set_x, data_mb_set_y, data_mb_set_m