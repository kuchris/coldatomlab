"""Lundh, Pethick & Smith (1998), Eqs. 36–39, radial + axial-Gaussian model.

Oscillator units, radial norm 2*pi*integral(r*|f|^2 dr)=1; g=4*pi*N*a/a0.
The r-independent real term in Eq. 39 is omitted by a global-phase gauge.
This is the paper's separable approximation, not the full 3D GPE.
"""

import math

import numpy as np
from scipy.linalg import solve_banded
from scipy.optimize import brentq


class PaperVortex:
    def __init__(self, coupling=20, cells=256, radius=24, dt=0.002, prepare_dt=0.002):
        if coupling < 0 or cells < 32 or radius <= 0 or not 0 < dt <= 0.01:
            raise ValueError("Invalid paper reference parameters.")
        self.coupling, self.g, self.dt = coupling, 4 * math.pi * coupling, dt
        self.dr = radius / cells
        self.r = (np.arange(cells) + 0.5) * self.dr
        self.weight = 2 * math.pi * self.r * self.dr
        # Finite-volume radial Laplacian with centrifugal term q=1. Transform
        # to sqrt(weight)*f for a symmetric tridiagonal operator and unit norm.
        left = np.arange(cells) * self.dr
        right = left + self.dr
        self.diagonal = (left + right) / (2 * self.r * self.dr**2) + 0.5 / self.r**2
        self.diagonal[-1] += right[-1] / (2 * self.r[-1] * self.dr**2)  # Dirichlet outer face
        self.off = -right[:-1] / (2 * self.dr**2 * np.sqrt(self.r[:-1] * self.r[1:]))
        self.u = self.r * np.exp(-(self.r**2) / 2) * np.sqrt(self.weight)
        self.u /= np.linalg.norm(self.u)
        self.z, self.v, self.steps = 1.0, 0.0, 0
        self.prepare(prepare_dt)
        self.initial = self.u.copy()
        self.initial_z = self.z

    def apply_kinetic(self, u):
        result = self.diagonal * u
        result[:-1] += self.off * u[1:]
        result[1:] += self.off * u[:-1]
        return result

    def kinetic_step(self, u, h):
        # Cayley/Crank–Nicolson: h=i*dt for real time, real tau for preparation.
        band = np.zeros((3, len(u)), dtype=np.result_type(u, h))
        band[0, 1:] = h * 0.5 * self.off
        band[2, :-1] = h * 0.5 * self.off
        band[1] = 1 + h * 0.5 * self.diagonal
        return solve_banded((1, 1), band, u - h * 0.5 * self.apply_kinetic(u))

    def quartic(self):
        return float(np.sum(abs(self.u) ** 4 / self.weight))

    def prepare(self, tau):
        old = self.u.copy()
        change = math.inf
        mu_shift = 2.0
        for it in range(1, 20001):
            interaction = self.g / (math.sqrt(2 * math.pi) * self.z)
            potential = 0.5 * self.r**2 - mu_shift
            ex = np.exp(-tau * potential)
            ratio = np.full_like(potential, tau)
            np.divide(
                -np.expm1(-tau * potential), potential, out=ratio, where=abs(potential) > 1e-12
            )
            self.u *= np.sqrt(ex / (1 + interaction * abs(self.u) ** 2 / self.weight * ratio))
            self.u = self.kinetic_step(self.u, tau)
            self.u *= np.sqrt(ex / (1 + interaction * abs(self.u) ** 2 / self.weight * ratio))
            norm = np.linalg.norm(self.u)
            self.u /= norm
            mu_shift -= math.log(norm) / tau
            coefficient = self.g * self.quartic() / math.sqrt(2 * math.pi)
            self.z = brentq(lambda z: z**4 - coefficient * z - 1, 1, max(2, coefficient + 2))
            if it % 50 == 0:
                change = float(np.linalg.norm(self.u - old))
                if change < 1e-9:
                    break
                old = self.u.copy()
        else:
            raise ValueError("Paper reference preparation did not converge.")
        h = (
            self.apply_kinetic(self.u)
            + (0.5 * self.r**2 + interaction * abs(self.u) ** 2 / self.weight) * self.u
        )
        mu = float(np.vdot(self.u, h).real)
        error = float(np.linalg.norm(h - mu * self.u) / mu)
        if error > 2e-4:
            raise ValueError("Paper reference stationary residual too large.")
        self.preparation = dict(
            iterations=it, dt=tau, radial_residual=error, radial_mu=mu, iterate_change=change
        )
        self.u = self.u.astype(complex)

    def acceleration(self):
        return 1 / self.z**3 + self.g * self.quartic() / (math.sqrt(2 * math.pi) * self.z**2)

    def advance(self, count):
        for _ in range(count):
            self.v += 0.5 * self.dt * self.acceleration()
            middle = self.z + 0.5 * self.dt * self.v
            interaction = self.g / (math.sqrt(2 * math.pi) * middle)
            self.u *= np.exp(-0.5j * self.dt * interaction * abs(self.u) ** 2 / self.weight)
            self.u = self.kinetic_step(self.u, 1j * self.dt)
            self.u *= np.exp(-0.5j * self.dt * interaction * abs(self.u) ** 2 / self.weight)
            self.z += self.dt * self.v
            self.v += 0.5 * self.dt * self.acceleration()
            self.steps += 1

    def diagnostics(self):
        density = abs(self.u) ** 2 / self.weight
        peak = int(np.argmax(density))
        threshold = density[peak] / math.e
        # The regular q=1 origin has f(0)=0; interpolate the first 1/e crossing.
        radius = np.r_[0, self.r[: peak + 1]]
        profile = np.r_[0, density[: peak + 1]]
        upper = int(np.flatnonzero(profile >= threshold)[0])
        inner = float(
            np.interp(threshold, profile[upper - 1 : upper + 1], radius[upper - 1 : upper + 1])
        )
        norm = float(np.vdot(self.u, self.u).real)
        rms = math.sqrt(float(np.sum(abs(self.u) ** 2 * self.r**2)) / norm)
        energy = (
            float(np.vdot(self.u, self.apply_kinetic(self.u)).real)
            + 0.25 * (self.v**2 + 1 / self.z**2)
            + self.g * self.quartic() / (2 * math.sqrt(2 * math.pi) * self.z)
        )
        return dict(
            time=self.steps * self.dt,
            norm=norm,
            core_radius=inner,
            radial_rms=rms,
            core_ratio=inner / rms,
            axial_rms=self.z / math.sqrt(2),
            energy=energy,
            edge_probability=float(np.sum(abs(self.u[self.r > 0.875 * self.r[-1]]) ** 2)),
        )
