import kerch
import numpy as np
from matplotlib import pyplot as plt

x = np.sin(np.arange(50) / np.pi)

k_rbf = kerch.kernel.RBF(sample=x, sigma=1)
k_rff = kerch.kernel.RFF(sample=x, num_weights=50, sigma=1)

fig, axs = plt.subplots(1, 2)

axs[0].imshow(k_rbf.K)
axs[0].set_title("RBF")

im = axs[1].imshow(k_rff.K)
axs[1].set_title("RFF")

fig.colorbar(im, ax=axs.ravel().tolist(), orientation='horizontal')