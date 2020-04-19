#    Copyright (C) 2020 David J. Wooten
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

from scipy.optimize import curve_fit
from scipy.stats import linregress, norm
import numpy as np
from .. import utils

class Hill:
    """The four-parameter Hill equation

                            d^h
    E = E0 + (Emax-E0) * ---------
                         C^h + d^h

    The Hill equation is a standard model for single-drug dose-response curves.
    This is the base model for Hill_2P and Hill_CI.

    """
    def __init__(self, E0=None, Emax=None, h=None, C=None, E0_bounds=(-np.inf, np.inf), Emax_bounds=(-np.inf, np.inf), h_bounds=(0,np.inf), C_bounds=(0,np.inf)):
        """
        Parameters
        ----------
        E0 : float, optional
            Effect at 0 dose. Set this if you are creating a synthetic Hill
            model, rather than fitting from data
        
        Emax : float, optional
            Effect at 0 dose. Set this if you are creating a synthetic Hill
            model, rather than fitting from data
        
        h : float, optional
            The Hill-slope. Set this if you are creating a synthetic Hill
            model, rather than fitting from data
        
        C : float, optional
            EC50, the dose for which E = (E0+Emax)/2. Set this if you are
            creating a synthetic Hill model, rather than fitting from data
        
        E0_bounds: tuple, default=(-np.inf, np.inf)
            Bounds to use for E0 when fitting this model to data
        
        Emax_bounds: tuple, default=(-np.inf, np.inf)
            Bounds to use for Emax when fitting this model to data
        
        h_bounds: tuple, default=(0, np.inf)
            Bounds to use for h when fitting this model to data
        
        C_bounds: tuple, default=(0, np.inf)
            Bounds to use for C when fitting this model to data
        """
        self.E0 = E0
        self.Emax = Emax
        self.h = h
        self.C = C
        
        self.E0_bounds=E0_bounds
        self.Emax_bounds=Emax_bounds
        self.h_bounds=h_bounds
        self.C_bounds=C_bounds
        with np.errstate(divide='ignore'):
            self.logh_bounds = (np.log(h_bounds[0]), np.log(h_bounds[1]))
            self.logC_bounds = (np.log(C_bounds[0]), np.log(C_bounds[1]))

        self.converged = False

        self.sum_of_squares_residuals = None
        self.r_squared = None
        self.aic = None
        self.bic = None
        self.bootstrap_parameters = None

        self.fit_func = lambda d, E0, E1, logh, logC: self._model(d, E0, E1, np.exp(logh), np.exp(logC))

        self.bounds = tuple(zip(self.E0_bounds, self.Emax_bounds, self.logh_bounds, self.logC_bounds))


    
    def _internal_fit(self, d, E, use_jacobian, **kwargs):
        try:
            if use_jacobian:
                popt1, pcov = curve_fit(self.fit_func, d, E, bounds=self.bounds, jac=self._model_jacobian, **kwargs)
            else: 
                popt1, pcov = curve_fit(self.fit_func, d, E, bounds=self.bounds, **kwargs)
            return popt1
        except:
            return None

    def fit(self, d, E, use_jacobian=True, bootstrap_iterations=10, **kwargs):
        """Fit the Hill equation to data. Fitting algorithm searches for h and C in a log-scale, but all bounds and guesses should be provided in a linear scale.

        Parameters
        ----------
        d : array_like
            Array of doses measured
        
        E : array_like
            Array of effects measured at doses d
        
        use_jacobian : bool, default=True
            If True, will use the Jacobian to help guide fit. When the number
            of data points is less than a few hundred, this makes the fitting
            slower. However, it also improves the reliability with which a fit
            can be found.
        
        kwargs
            kwargs to pass to scipy.optimize.curve_fit()
        """
        d = utils.remove_zeros(d)
        
        if 'p0' in kwargs:
            p0 = list(kwargs.get('p0'))
            p0[2] = np.log(p0[2])
            p0[3] = np.log(p0[3])
            utils.sanitize_initial_guess(p0, self.bounds)
            kwargs['p0'] = p0
        else:
            p0 = [max(E), min(E), 0, np.log(np.median(d))]
            utils.sanitize_initial_guess(p0, self.bounds)
            kwargs['p0'] = p0

        with np.errstate(divide='ignore', invalid='ignore'):
            popt = self._internal_fit(d, E, use_jacobian, **kwargs)

        if popt is None:
            E0 = np.max(E)
            E1 = np.min(E)
            logh = 0
            logC = np.log(np.median(d))
            self.converged = False
        else:
            E0, E1, logh, logC = popt
            self.converged = True

        self.E0 = E0
        self.Emax = E1
        self.h = np.exp(logh)
        self.C = np.exp(logC)

        if self.converged:
            self._score(d, E)
            kwargs['p0'] = [E0, E1, logh, logC]
            return self._bootstrap_resample(d, E, use_jacobian, bootstrap_iterations, **kwargs)

    def E(self, d):
        """Evaluate this model at dose d. If the model is not parameterized, returns 0.

        Parameters
        ----------
        d : array_like
            Doses to calculate effect at
        
        Returns
        ----------
        effect : array_like
            Evaluate's the model at dose in d
        """
        if not self._is_parameterized():
            return 0
        return self._model(d, self.E0, self.Emax, self.h, self.C)

    def E_inv(self, E):
        """Inverse of the Hill equation

        Parameters
        ----------
        E : array_like
            Effects to get the doses for
        
        Returns
        ----------
        doses : array_like
            Doses which achieve effects E using this model. Effects that are
            outside the range [E0, Emax] will return np.nan for the dose
        """
        if not self._is_parameterized():
            return 0
        return self._model_inv(E, self.E0, self.Emax, self.h, self.C)

    def get_parameters(self):
        """
        Returns
        ----------
        parameters : tuple
            (E0, Emax, h, C)
        """
        return (self.E0, self.Emax, self.h, self.C)
        
    def _model(self, d, E0, Emax, h, C):
        dh = d**h
        return E0 + (Emax-E0)*dh/(C**h+dh)

    def _model_inv(self, E, E0, Emax, h, C):
        d = np.float_power((E0-Emax)/(E-Emax)-1.,1./h)*C
        return d

    def _model_jacobian(self, d, E0, Emax, logh, logC):
        """
        Returns
        ----------
        jacobian : array_like
            Derivatives of the Hill equation with respect to E0, Emax, logh,
            and logC
        """
        
        dh = d**(np.exp(logh))
        Ch = (np.exp(logC))**(np.exp(logh))
        logd = np.log(d)

        jE0 = 1 - dh/(Ch+dh)
        jEmax = 1-jE0

        jC = (E0-Emax)*dh*np.exp(logh+logC)*(np.exp(logC))**(np.exp(logh)-1) / ((Ch+dh)*(Ch+dh))

        jh = (Emax-E0)*dh*np.exp(logh) * ((Ch+dh)*logd - (logC*Ch + logd*dh)) / ((Ch+dh)*(Ch+dh))
        
        return np.hstack((jE0.reshape(-1,1), jEmax.reshape(-1,1), jh.reshape(-1,1), jC.reshape(-1,1)))

    def _is_parameterized(self):
        return not (None in self.get_parameters() or True in np.isnan(np.asarray(self.get_parameters())))

    def create_fit(d, E, E0_bounds=(-np.inf, np.inf), Emax_bounds=(-np.inf, np.inf), h_bounds=(0,np.inf), C_bounds=(0,np.inf), **kwargs):
        """Courtesy function to build a Hill model directly from data.
        Initializes a model using the provided bounds, then fits.
        """
        drug = Hill(E0_bounds=E0_bounds, Emax_bounds=Emax_bounds, h_bounds=h_bounds, C_bounds=C_bounds)
        drug.fit(d, E, **kwargs)
        return drug

    def __repr__(self):
        if not self._is_parameterized(): return "Hill()"
        
        return "Hill(E0=%0.2f, Emax=%0.2f, h=%0.2f, C=%0.2e)"%(self.E0, self.Emax, self.h, self.C)

    def _score(self, d, E):
        """Calculate goodness of fit and model quality scores, including sum-of-squares residuals, R^2, Akaike Information Criterion (AIC), and Bayesian Information Criterion (BIC).

        If model is not yet paramterized, does nothing

        Called automatically during model.fit(d1, d2, E)

        Parameters
        ----------
        d : array_like
            Doses
        
        E : array_like
            Measured dose-response at doses d
        """
        if (self._is_parameterized()):

            n_parameters = len(self.get_parameters())

            self.sum_of_squares_residuals = utils.residual_ss_1d(d, E, self.E)
            self.r_squared = utils.r_squared(E, self.sum_of_squares_residuals)
            self.aic = utils.AIC(self.sum_of_squares_residuals, n_parameters, len(E))
            self.bic = utils.BIC(self.sum_of_squares_residuals, n_parameters, len(E))

    def _bootstrap_resample(self, d, E, use_jacobian, bootstrap_iterations, confidence_interval=95, **kwargs):

        if not self._is_parameterized(): return
        
        p0 = kwargs.get('p0')
        

        n_data_points = len(E)
        n_parameters = len(p0)
        
        sigma_residuals = np.sqrt(self.sum_of_squares_residuals / (n_data_points - n_parameters))

        E_model = self.E(d)
        bootstrap_parameters = []
        for iteration in range(bootstrap_iterations):
            residuals_step = norm.rvs(loc=0, scale=sigma_residuals, size=n_data_points)

            # Add random noise to model prediction
            E_iteration = E_model + residuals_step

            # Fit noisy data
            with np.errstate(divide='ignore', invalid='ignore'):
                popt1 = self._internal_fit(d, E_iteration, use_jacobian=use_jacobian, **kwargs)
            
            if popt1 is not None:
                E0, E1, logh, logC = popt1
                h = np.exp(logh)
                C = np.exp(logC)
                bootstrap_parameters.append((E0, E1, h, C))
            
        
        self.bootstrap_parameters = np.vstack(bootstrap_parameters)
        lower_bounds = (100-confidence_interval)/2.
        upper_bounds = 100-lower_bounds
        return np.percentile(self.bootstrap_parameters, [lower_bounds, upper_bounds], axis=0)




class Hill_2P(Hill):
    """The two-parameter Hill equation

                            d^h
    E = E0 + (Emax-E0) * ---------
                         C^h + d^h

    Mathematically equivalent to the four-parameter Hill equation, but E0 and Emax are held constant (not fit to data).
    
    """
    def __init__(self, h=None, C=None, h_bounds=(0,np.inf), C_bounds=(0,np.inf), E0=1, Emax=0):
        super().__init__(h=h, C=C, E0=E0, Emax=Emax, h_bounds=h_bounds, C_bounds=C_bounds)

    def fit(self, d, E, use_jacobian=True, **kwargs):
        if self.E0 is None: self.E0 = 1.
        if self.Emax is None: self.Emax = 0.

        f = lambda d, logh, logC: self._model(d, self.E0, self.Emax, np.exp(logh), np.exp(logC))

        d = utils.remove_zeros(d)

        bounds = tuple(zip(self.logh_bounds, self.logC_bounds))

        if 'p0' in kwargs:
            p0 = list(kwargs.get('p0'))
            p0[0] = np.log(p0[0])
            p0[1] = np.log(p0[1])
            kwargs['p0'] = p0
            utils.sanitize_initial_guess(p0, bounds)
        else:
            p0 = [0, np.log(np.median(d))]
            utils.sanitize_initial_guess(p0, bounds)
            kwargs['p0'] = p0

        with np.errstate(divide='ignore', invalid='ignore'):
            try:
                if use_jacobian:
                    popt1, pcov = curve_fit(f, d, E, bounds=bounds, jac=self._model_jacobian, **kwargs)
                else: 
                    popt1, pcov = curve_fit(f, d, E, bounds=bounds, **kwargs)
                logh, logC = popt1
                self.converged = True
            except RuntimeError:
                #print("\n\n*********\nFailed to fit single drug\n*********\n\n")
                logh = 0
                logC = np.log(np.median(d))
                self.converged = False

        self.h = np.exp(logh)
        self.C = np.exp(logC)

    def _model_jacobian(self, d, logh, logC):
        dh = d**(np.exp(logh))
        Ch = (np.exp(logC))**(np.exp(logh))
        logd = np.log(d)
        E0 = self.E0
        Emax = self.Emax

        jC = (E0-Emax)*dh*np.exp(logh+logC)*(np.exp(logC))**(np.exp(logh)-1) / ((Ch+dh)*(Ch+dh))

        jh = (Emax-E0)*dh*np.exp(logh) * ((Ch+dh)*logd - (logC*Ch + logd*dh)) / ((Ch+dh)*(Ch+dh))
        
        return np.hstack((jh.reshape(-1,1), jC.reshape(-1,1)))

    def create_fit(d, E, E0=1, Emax=0, h_bounds=(0,np.inf), C_bounds=(0,np.inf), **kwargs):
        drug = Hill_2P(E0=E0, Emax=Emax, h_bounds=h_bounds, C_bounds=C_bounds)
        drug.fit(d, E, **kwargs)
        return drug

    def get_parameters(self):
        """Gets the model's fitted parameters
        
        Returns
        ----------
        parameters : tuple
            (h, C)
        """
        return (self.h, self.C)

    def __repr__(self):
        if not self._is_parameterized(): return "Hill()"
        
        return "Hill2P(E0=%0.2f, Emax=%0.2f, h=%0.2f, C=%0.2e, converged=%r)"%(self.E0, self.Emax, self.h, self.C)
    
    
class Hill_CI(Hill_2P):
    """Mathematically equivalent two-parameter Hill equation with E0=1 and Emax=0. However, Hill_CI.fit() uses the log-linearization approach to dose-response fitting used by the Combination Index.
    """
    def __init__(self, h=None, C=None):
        super().__init__(h=h, C=C, E0=1., Emax=0.)

    def fit(self, d, E):
        mask = np.where((E < 1) & (E > 0) & (d > 0))
        E = E[mask]
        d = d[mask]
        fU = E
        fA = 1-E

        median_effect_line = linregress(np.log(d),np.log(fA/fU))
        self.h = median_effect_line.slope
        self.C = np.exp(-median_effect_line.intercept / self.h)

    def create_fit(d, E):
        drug = Hill_CI()
        drug.fit(d, E)
        return drug

    def __repr__(self):
        if not self._is_parameterized(): return "Hill_CI()"
        
        return "Hill_CI(h=%0.2f, C=%0.2e)"%(self.h, self.C)
    
    