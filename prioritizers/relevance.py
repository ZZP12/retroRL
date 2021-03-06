from retroRL.prioritizers.prioritizer import Prioritizer
import rdkit.Chem as Chem
from rdkit.Chem import AllChem
import numpy as np

import math
import sys
import random
import time
import os
import cPickle as pickle

class RelevanceTemplatePrioritizer(Prioritizer):
    '''
    Prioritize the templates based on their relevance
    '''

    def __init__(self, retro=True):
        self.retro = retro
        self.FP_len = 2048
        self.FP_rad = 2
        self.vars = []
        self.template_count = 100
        self.max_cum_prob = 1

    def mol_to_fp(self, mol):
        if mol is None:
            return np.zeros((self.FP_len,), dtype=np.float32)
        return np.array(AllChem.GetMorganFingerprintAsBitVect(mol, self.FP_rad, nBits=self.FP_len,
                                                              useChirality=True), dtype=np.bool)

    def smi_to_fp(self, smi):
        if not smi:
            return np.zeros((self.FP_len,), dtype=np.float32)
        return self.mol_to_fp(Chem.MolFromSmiles(smi))

    def get_priority(self, input_tuple, **kwargs):
        (templates, target) = input_tuple
        # Templates should be sorted by popularity for indices to be correct!
        probs, top_ids = self.get_topk_from_smi(smi=target, k = min(self.template_count, len(templates)))
        top_templates = []
        cum_score = 0
        for i, id in enumerate(top_ids):
            templates[id]['score'] = probs[i]
            top_templates.append(templates[id])
            cum_score += probs[i]
            #End loop if max cumulative score is exceeded
            if cum_score >= self.max_cum_prob:
                break
        return top_templates

    def load_model(self):
        modelpath = '../prioritizers/template/template_relevance_network_weights.pickle'

        if not os.path.isfile(modelpath):
            modelpath = 'prioritizers/template/template_relevance_network_weights.pickle'

        with open(modelpath, 'rb') as fid:
            self.vars = pickle.load(fid)
        return self

    def apply(self, x):
        # Each pair of vars is a weight and bias term
        for i in range(0, len(self.vars), 2):
            last_layer = (i == len(self.vars)-2)
            W = self.vars[i]
            b = self.vars[i+1]
            x = np.matmul(x, W) + b
            if not last_layer:
                x = x * (x > 0)  # ReLU
        return x

    def get_topk_from_smi(self, smi='', k=100):
        if not smi:
            return []
        mol = Chem.MolFromSmiles(smi)
        if not mol:
            return []
        return self.get_topk_from_mol(mol, k=k)

    def get_topk_from_mol(self, mol, k=100):
        fp = self.mol_to_fp(mol).astype(np.float32)
        cur_scores = self.apply(fp)
        indices = list(cur_scores.argsort()[-k:][::-1])
        cur_scores.sort()
        probs = softmax(cur_scores)
        return probs[-k:][::-1], indices

    def sigmoid(x):
        return 1 / (1 + math.exp(-x))

def softmax(x):
    e_x = np.exp(x - np.max(x))
    return e_x / e_x.sum()

if __name__ == '__main__':
    import sys 
    sys.path.insert(0, os.path.abspath('../'))
    model = RelevanceTemplatePrioritizer()
    model.load_model()
    smis = ['CCCOCCC', 'CCCNc1ccccc1']
    for smi in smis:
        lst = model.get_topk_from_smi(smi)
        print('{} -> {}'.format(smi, lst))
