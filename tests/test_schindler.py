import numpy as np
from synergy.single.hill import Hill
from synergy.combination.musyc import MuSyC
from synergy.combination.schindler import Schindler

from matplotlib import pyplot as plt

E0, E1, E2, E3 = 1, 0.5, 0.2, 0.1
h1, h2 = 1., 1.
C1, C2 = 1e-2, 1e-1
alpha12, alpha21 = 0., 0.

model = MuSyC(E0=E0, E1=E1, E2=E2, E3=E3, h1=h1, h2=h2, C1=C1, C2=C2, alpha12=alpha12, alpha21=alpha21)

model2 = MuSyC(E0=E0, E1=E1, E2=E2, E3=E3, h1=h1, h2=h2, C1=C1, C2=C2, alpha12=alpha12, alpha21=1.)

drug1 = Hill(E0=E0, Emax=E1, h=h1, C=C1)
drug2 = Hill(E0=E0, Emax=E2, h=h2, C=C2)

npoints = 12

d1 = np.logspace(-3,0,num=npoints)
d2 = np.logspace(-2,1,num=npoints)
D1, D2 = np.meshgrid(d1,d2)
D1 = D1.flatten()
D2 = D2.flatten()

E = model.E(D1, D2)
E_2 = model2.E(D1, D2)

schindler = Schindler()
synergy = schindler.fit(D1, D2, E, drug1_model=drug1, drug2_model=drug2)
synergy_2 = schindler.fit(D1, D2, E_2, drug1_model=drug1, drug2_model=drug2)

fig = plt.figure(figsize=(5,6))

ax = fig.add_subplot(2,2,1)
ax.pcolormesh(E.reshape(npoints,npoints), vmin=E3, vmax=E0)
ax.set_aspect('equal')
ax.set_title("Dose Surface")

ax = fig.add_subplot(2,2,2)
ax.pcolormesh(synergy.reshape(npoints,npoints), vmin=-0.01, vmax=0.01)
ax.set_aspect('equal')
ax.set_yticks([])
ax.set_title("Schindler Synergy")

ax = fig.add_subplot(2,2,3)
ax.pcolormesh(E_2.reshape(npoints,npoints), vmin=E3, vmax=E0)
ax.set_aspect('equal')
ax.set_title("Dose Surface")

V = max(abs(min(synergy_2)), abs(max(synergy_2)))
ax = fig.add_subplot(2,2,4)
ax.pcolormesh(synergy_2.reshape(npoints,npoints), vmin=-V, vmax=V)
ax.set_aspect('equal')
ax.set_yticks([])
ax.set_title("Schindler Synergy")

plt.tight_layout()
plt.show()