### imports
import numpy as np
import matplotlib.pyplot as plt
from tqdm import tqdm
plt.style.use("ggplot")

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.autograd import grad

from stein.utils import *

### langevin-stein operator
def langevin_stein(p, phi, x):
    """
    implementation of the Langevin-Stein operator, which is an operator
    variational objective useful for SVGD.
    """
    def logp(y):
        return torch.log(p(y))
    nabla_logp = grad(logp(x), x, create_graph=True)[0]
    phi_x = phi(x).view(-1)
    return torch.dot(phi_x, nabla_logp) + grad(phi_x, x, create_graph=True)[0]

### Kernelized Stein discrepancy
class KSD:
    """
    Kernelized Stein discrepancy for a kernel in a
    given RKHS.
    """
    def __init__(self, kernel, p):
        self.kernel = kernel
        self.p = p
        
    def optimal_fn(self, samples):
        # python lacks true currying, so this is
        # going to be sorta awkward
        def kern_curry(y):
            def k(x):
                return self.kernel.eval(x,y).view(-1)
            return k
        
        def phi_star(x):
            num_samples = samples.shape[0]
            phi_vals = torch.zeros(samples.shape)
            for i in range(num_samples):
                sp = samples[i].clone().detach().requires_grad_()
                phi_vals[i] = langevin_stein(self.p, kern_curry(sp), x.view(-1))
            return torch.mean(phi_vals)
    
        return phi_star
            
    def eval(self, q, num_samples=100):
        """
        Monte carlo estimate of KSD.
        """
        samples = q.sample((num_samples,))
        phi_star = self.optimal_fn(samples)
        # get new samples for second expectation
        new_samples = q.sample((num_samples,))
        ksd_vals = torch.zeros(samples.shape)
        for i in tqdm(range(num_samples)):
            sp = samples[i].clone().detach().requires_grad_()
            ksd_vals[i] = langevin_stein(self.p, phi_star, sp.view(-1))
        return torch.mean(ksd_vals)