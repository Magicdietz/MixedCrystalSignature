#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jun 14 08:51:08 2017

@author: dietz
"""

# Alles automatisch Datengesteuert

#1. Daten erstellen und Signatur davon berechnen
#2. Classifier anlernen
#3. Auswertung und plots

import numpy as np
import time

import datageneration.generatecrystaldata as gcn
import datageneration.disordercrystaldata as dcs
from mixedcrystalsignature import MixedCrystalSignature

from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score
import pickle

class CrystalAnalyzer:
    """Analyze Crystal Strucures"""
    train_seed=0
    test_seed=1
    train_noiselist=list(range(4,12,1))
    noiselist=list(range(0,21))
    structure_arr=['fcc','hcp','bcc']
    labels2struct={'fcc':1,'hcp':2,'bcc':3}
    volume = [[0,0,0],[34,34,34]]
    #volume = [[0,0,0],[15,15,15]]
    inner_distance = 2
    
    loglevel=3
    
    def __init__(self, classifier, scaler, sign_calculator):
        self.classifier=classifier
        self.scaler=scaler
        self.sign_calculator=sign_calculator
        
    def create_artificial_datasets(self,noise_arr, structure_arr, volume, rnd_seed):
        datasets=dict()
        for structure in structure_arr:
            datasets[structure]={'noise':[],'datalist':[]}
            basedata=[]
            if 'fcc' == structure:
                basedata=gcn.fill_volume_fcc(volume[0], volume[1], volume[2])
            if 'hcp' == structure:
                basedata=gcn.fill_volume_hcp(volume[0], volume[1], volume[2])
            if 'bcc' == structure:
                basedata=gcn.fill_volume_bcc(volume[0], volume[1], volume[2])
            
            for noise in noise_arr:
                datasets[structure]['datalist'].append(dcs.add_gaussian_noise(basedata, noise/100, rnd_seed))
                datasets[structure]['noise'].append(noise)
        return datasets
    
    
    def calculate_artificial_signatures(self, datasets):
        signatures=dict()
        for structure in datasets:
            signatures[structure]={'sign_arr':[],'voro_vols':[], 'softness':[], 'data_idx':[]}
            initial_datapoints=datasets[structure]['datalist'][0]
            inner_bool_vec=self.get_inner_volume_bool_vec(initial_datapoints)
            for i,datapoints in enumerate(datasets[structure]['datalist']):
                self.sign_calculator.set_datapoints(datapoints)
                self.sign_calculator.set_inner_bool_vec(inner_bool_vec)
                self.sign_calculator.calc_signature()
                signatures[structure]['sign_arr'].append(self.sign_calculator.signature.values)
                signatures[structure]['voro_vols'].append(self.sign_calculator.voro_vols)
                signatures[structure]['softness'].append(self.sign_calculator.struct_order)
                signatures[structure]['data_idx'].append(self.sign_calculator.solid_indices)
                if self.loglevel >= 3:
                    print('struc:',structure,
                          'noise:',datasets[structure]['noise'][i],
                          'num:', len(self.sign_calculator.signature))
        return signatures
    
    def calculate_signatures(self, datasets, inner_distance):

        signatures={'sign_arr':[],'voro_vols':[], 'softness':[], 'data_idx':[]}
        for i,datapoints in enumerate(datasets['datalist']):
            
            volume=self.get_volume_from_datapoints(datapoints)
            
            self.sign_calculator.set_datapoints(datapoints)
            self.sign_calculator.set_inner_bool_vec(self.get_inner_volume_bool_vec(datapoints,volume,inner_distance))
            self.sign_calculator.calc_qlm_array()
            self.sign_calculator.calc_si_bool()
            self.sign_calculator.calc_sign_array()
            signatures['sign_arr'].append(self.sign_calculator.sign_array)
            signatures['voro_vols'].append(self.sign_calculator.voro_vols)
            signatures['softness'].append(self.sign_calculator.softness)
            signatures['data_idx'].append(self.sign_calculator.solid_indices)
            if self.loglevel >= 3:
                
                if 'templist' in datasets:
                    print('idx',i,
                          'temp',datasets['templist'][i],
                          'num:', len(self.sign_calculator.sign_array))
                else:
                    print('idx',i,'num:', len(self.sign_calculator.sign_array))
                
        return signatures
        
    
    def convert_artificial_signatures_to_matrix(self,signatures):
        index_dict=dict()
        startindex=0
        signlist=[]
        labels=[]
        
        for structure in signatures:
            index_dict[structure]=[]
            for i,sign_arr in enumerate(signatures[structure]['sign_arr']):
                if i in self.train_noiselist:
                    length=sign_arr.shape[0]
                    if length>0:
                        signlist.append(sign_arr)
                        data_idx=signatures[structure]['data_idx'][0]
                        index_dict[structure].append([i,range(startindex,startindex+length),data_idx])
                        labels.append(np.zeros(length,dtype=np.int32)+self.labels2struct[structure])
                        startindex+=length

        return np.concatenate(signlist,axis=0), np.concatenate(labels), index_dict
    
    
    def convert_signatures_to_matrix(self, signatures):
        index_list=[]
        startindex=0
        signlist=[]

        for i,sign_arr in enumerate(signatures['sign_arr']):
            length=sign_arr.shape[0]
            if length>0:
                signlist.append(sign_arr)
                data_idx=signatures['data_idx'][0]
                index_list.append([i,range(startindex,startindex+length),data_idx])
                startindex+=length

        return np.concatenate(signlist,axis=0), index_list
    
    def generate_train_signatures(self):
        if self.loglevel >= 3:
            print('generating training signatures')
        self.train_datasets=self.create_artificial_datasets(self.noiselist,
                                                            self.structure_arr,
                                                            self.volume[1],
                                                            self.train_seed)
        self.train_signatures=self.calculate_artificial_signatures(self.train_datasets)
        
    def generate_test_signatures(self):
        if self.loglevel >= 3:
            print('generating test signatures')
        self.test_datasets=self.create_artificial_datasets(self.noiselist,
                                                            self.structure_arr,
                                                            self.volume[1],
                                                            self.test_seed)
        self.test_signatures=self.calculate_artificial_signatures(self.test_datasets)
        
    def load_object(self, filepath):
        objects=[]
        with open(filepath,'rb') as file:
            objects=pickle.load(file)
        return objects
        
    def save_object(self,objects, filepath):
        with open(filepath,'wb') as file:
            pickle.dump(objects,file)
            
    def save_training_signatures(self,path):
        self.save_object(self.train_signatures,path)
        
    def load_training_signatures(self,path):
        self.train_signatures=self.load_object(path)
        
    def save_test_signatures(self,path):
        self.save_object(self.test_signatures,path)
        
    def load_test_signatures(self,path):
        self.test_signatures=self.load_object(path)
    
    def save_classifier(self,path):
        self.save_object(self.classifier,path)
    
    def load_classifier(self,path):
        self.classifier=self.load_object(path)
        
    def save_scaler(self,path):
        self.save_object(self.scaler,path)
    
    def load_scaler(self,path):
        self.scaler=self.load_object(path)
    
    def train_classifier(self):
        if self.loglevel >=1:
            print('started training')
            t = time.time()
        
        self.trainmatrix, self.trainlabels, self.trainindex_dict=self.convert_artificial_signatures_to_matrix(self.train_signatures)
        
        self.classifier.fit(self.scaler.fit_transform(self.trainmatrix),self.trainlabels)
        
        if self.loglevel >=1:
            print('finished training, time:',time.time()-t)
        
        if self.loglevel >=3:
            trainprediction=self.classifier.predict(self.scaler.transform(self.trainmatrix))
            print('Accuracy on Train set:',
                  accuracy_score(trainprediction,self.trainlabels))
        
    def predict_test(self):
        for structure in self.test_signatures:
            self.test_signatures[structure]['prediction']=[]
            for i,sign_arr in enumerate(self.test_signatures[structure]['sign_arr']):
                if len(sign_arr)>0:
                    pred=self.classifier.predict(self.scaler.transform(sign_arr))
                else:
                    pred=np.array([],dtype=np.int32)
                self.test_signatures[structure]['prediction'].append(pred)
                if self.loglevel >=1:
                    orig_labels=np.zeros(len(pred),dtype=np.int32)+self.labels2struct[structure]
                    print('predicted','struc',structure,'idx', i,
                          accuracy_score(pred,orig_labels))
    
    def predict(self,signatures):
        signatures['prediction']=[]
        for i,sign_arr in enumerate(signatures['sign_arr']):
            if len(sign_arr)>0:
                pred=self.classifier.predict(self.scaler.transform(sign_arr))
            else:
                pred=[]
            signatures['prediction'].append(pred)
            if self.loglevel >=3:
                print('predicted','idx', i)
        
        return signatures
    
    def predict_proba(self,signatures):
        signatures['probabilities']=[]
        for i,sign_arr in enumerate(signatures['sign_arr']):
            if len(sign_arr)>0:
                pred=self.classifier.predict_proba(self.scaler.transform(sign_arr))
            else:
                pred=[]
            signatures['probabilities'].append(pred)
            if self.loglevel >=3:
                print('predicted probabilites','idx', i)
        
        return signatures
    
    def get_volume_from_datapoints(self,datapoints):
        volume=[[0,0,0],[0,0,0]]
        volume[0][0]=datapoints[:,0].min()
        volume[0][1]=datapoints[:,1].min()
        volume[0][2]=datapoints[:,2].min()
        
        volume[1][0]=datapoints[:,0].max()
        volume[1][1]=datapoints[:,1].max()
        volume[1][2]=datapoints[:,2].max()
        return volume
    
    def get_inner_volume_bool_vec(self,datapoints, volume=[], inner_distance=-1):
        if inner_distance<0:
            inner_distance=self.inner_distance
        if volume==[]:
            volume=self.volume
            
        x_min = volume[0][0]+inner_distance
        y_min = volume[0][1]+inner_distance
        z_min = volume[0][2]+inner_distance
        
        x_max = volume[1][0]-inner_distance
        y_max = volume[1][1]-inner_distance
        z_max = volume[1][2]-inner_distance
        
        bool_matrix_min = datapoints >= [x_min,y_min,z_min]
        bool_matrix_max = datapoints <= [x_max,y_max,z_max]
        
        bool_matrix=np.logical_and(bool_matrix_min,bool_matrix_max)
        
        return np.all(bool_matrix,axis=1)

def get_counts(signatures,labels2struct):
    countdict=dict()
    for structure,key in labels2struct.items():
        countdict[structure]=[]
        for i,prediction in enumerate(signatures['prediction']):
            countdict[structure].append(np.sum(np.equal(prediction,key)))
    return countdict

import matplotlib.pyplot as plt
def plot_test_data(signatures,noiselist,labels2struct):
    style={'fcc':['v','-'],
           'hcp':['o','--'],
           'bcc':['d',':'],
           'false':['s','-.']}
    
    fig,ax= plt.subplots(1, 1)
    length=len(signatures[list(signatures.keys())[0]]['sign_arr'])
    falsecounts=np.zeros(length,dtype=np.int32)
    summedcounts=np.zeros(length,dtype=np.int32)
    
    struct_list=sorted(signatures.keys())
    for structure in struct_list:
        countdict=get_counts(signatures[structure],labels2struct)
        struc_lengths=[len(signatures[structure]['data_idx'][i]) for i in range(length)]
        first_count_value=struc_lengths[0]
        tmpfalse=np.zeros(length,dtype=np.int32)
        for countstruct in countdict:
            if countstruct!=structure:
                tmpfalse=np.add(tmpfalse,countdict[countstruct])
        falsecounts=np.add(falsecounts,tmpfalse)
        
        summedcounts=np.add(summedcounts,struc_lengths)
        percentages=np.divide(countdict[structure],first_count_value)*100
        plt.plot(noiselist,percentages,label=structure,marker=style[structure][0],linestyle=style[structure][1])
    
    falsecounts[summedcounts==0]=0
    summedcounts[summedcounts==0]=1
    falsepercentages=np.divide(falsecounts,summedcounts)*100
    plt.plot(noiselist,falsepercentages,label='false',marker=style['false'][0],linestyle=style['false'][1])
    
    print('falsepos:',falsepercentages[10])
    
    plt.xlabel('noise [%]')
    plt.ylabel('structural fraction [%]')
    plt.xticks(noiselist[::2])
    plt.legend()
    return fig,ax

if __name__ == '__main__':
    import matplotlib
    matplotlib.rcParams.update({'figure.autolayout': True})
    from sklearn.ensemble import GradientBoostingClassifier
    
#    filepath='pc_17112016_9h31m_10Pa.dump'
#    logfilepath='pc_17112016_9h31m_10Pa.log'
#    timesteps=list(range(200000,10000000,250000))
#    inner_distance=53.7071
#    mddata=get_md_data_dict(filepath, logfilepath, timesteps)

    
    import multiprocessing as mp
    
    sign_calculator=MixedCrystalSignature(solid_thresh=0.55,pool=mp.Pool(6))
    
    classifier = MLPClassifier(max_iter=300,tol=1e-5,
                               hidden_layer_sizes=(250,),
                               solver='adam',random_state=0, shuffle=True,
                               activation='relu',alpha=1e-4)
    
    #classifier=GradientBoostingClassifier()
    
    scaler=StandardScaler()
    
    ca=CrystalAnalyzer(classifier,scaler,sign_calculator)
#    ca.generate_train_signatures()
#    ca.save_training_signatures("tmp_train.pkl")
#    ca.generate_test_signatures()
#    ca.save_test_signatures("tmp_test.pkl")
    
    sign_calculator.p.close()
    sign_calculator.p.join()
#    
    ca.load_training_signatures("tmp_train.pkl")
#    ca.train_classifier()
#    ca.save_classifier("tmp_classifier.pkl")
#    ca.save_scaler("tmp_scaler.pkl")
    
    ca.load_scaler("tmp_scaler.pkl")
    ca.load_classifier("tmp_classifier.pkl")
    ca.load_test_signatures("tmp_test.pkl")
    ca.predict_test()
    
    fig2,ax2=plot_test_data(ca.test_signatures,ca.noiselist,ca.labels2struct)
#    
    
#    ca.save_training_signatures()
    
#    ca.save_test_signatures()
#
#    ca.load_training_signatures()
    
#    ca.save_classifier()
#    ca.save_scaler()
#
#    ca.load_scaler()
#    ca.load_classifier()
#    ca.load_test_signatures()
#    ca.predict_test()
#    ca.save_test_signatures()
    
    
#    mdsigns=ca.calculate_signatures(mddata,inner_distance)
#    ca.save_object(mdsigns,'tmp_md.pkl')
    
#    mdsigns=ca.load_object('tmp_md.pkl')
#    ca.predict(mdsigns)
#    ca.save_object(mdsigns,'tmp_md.pkl')

#    volume=ca.get_volume_from_datapoints(mddata['datalist'][-1])
#    inner=ca.get_inner_volume_bool_vec(mddata['datalist'][-1],volume,inner_distance)
# 
#    fig, ax = MCSPL.plot_md_data(mdsigns,mddata['templist'],ca.labels2struct,np.sum(inner))
#    MCSPL.set_font_sizes(ax,18)
#    ca.save_object(fig,'figures/md_fig_si055_4.pkl')
#    
#    fig2,ax2=MCSPL.plot_test_data(ca.test_signatures,ca.noiselist,ca.labels2struct)
#    MCSPL.set_font_sizes(ax2,18)
#    ca.save_object(fig2,'figures/test_fig_si055_4.pkl')
#    
#    fig3,ax3=MCSPL.plot_train_data(ca.train_signatures,ca.noiselist)
#    MCSPL.set_font_sizes(ax3,18)
#    ca.save_object(fig3,'figures/train_fig_si055_4.pkl')
#    
#    fig4,ax4=MCSPL.plot_false_data(ca.test_signatures,ca.noiselist,ca.labels2struct)
#    MCSPL.set_font_sizes(ax4,18)
#    
#    fig5,ax5=MCSPL.plot_md_sim_class_from_matlab('/media/dietz/Matlab/MDSimAnalysis/mdsim_matlab_to_python.mat')
#    MCSPL.set_font_sizes(ax5,18)
#    
#    plt.show()
#    sign_calculator.close_proc()