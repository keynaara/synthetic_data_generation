"""Base classes for all synthesizers"""

import numpy as np
import pandas as pd
import dill

from abc import ABC, abstractmethod
from copy import copy
from numbers import Real
from scipy.spatial.distance import jensenshannon

class BaseDPSynthesizer(ABC):
    """Abstract base class for all differentially private synthesizers"""

    def __init__(self, epsilon=1.0, verbose=True):
        """Base class for differentially private synthesizers.

        Parameters
        ----------
        epsilon : float or int
            Privacy parameter epsilon in differential privacy. Must be in range [0, float(np.inf)].
        verbose : bool
            Enable verbose output
        """
        self.epsilon = epsilon
        self.verbose = verbose

    @abstractmethod
    def fit(self, data):
        """Fit synthesizer to input data.

         Parameters
        ----------
        data: pandas.DataFrame
            Input dataset to fit the synthesizer to.

        Returns
        -------
        self : class
            Returns the fitted synthesizer that can be sampled from.
        """
        pass

    @abstractmethod
    def sample(self, n_records=None):
        """Sample records from fitted synthesizer.

        Parameters
        ----------
        n_records: int or float
            Number of records to be sampled.

        Returns
        -------
        pandas.DataFrame
            Returns synthetic dataset that mimics the input data seen in fit.
        """
        pass

    def score(self, original_data, synthetic_data, score_dict=False):
        """Calculate jensen_shannon distance between original and synthetic data.
        Look for more elaborate evaluation techniques in synthesis.evaluation.

        Parameters
        ----------
        original_data: pandas.DataFrame
            Original data that was seen in fit
        synthetic_data: pandas.DataFrame
            Synthetic data that was generated based original_data
        score_dict: bool
            If true, will return jensen_shannon scores of each column individually
        Returns
        -------
        average jensen_shannon distance: float
            Average jensen_shannon distance over all columns
        per-column jensen_shannon distance (if score_dict): dict
            Per-column jensen_shannon distance
        """
        column_distances = {}
        for i, c in enumerate(original_data.columns):
            # compute value_counts for both original and synthetic - align indexes as certain column
            # values in the original data may not have been sampled in the synthetic data
            counts_original, counts_synthetic = \
                original_data[c].value_counts(dropna=False).align(
                    synthetic_data[c].value_counts(dropna=False), join='outer', axis=0, fill_value=0
                )

            js_distance = jensenshannon(counts_original, counts_synthetic)
            column_distances[c] = js_distance
        average_column_distance = sum(column_distances.values()) / len(original_data.columns)
        if score_dict:
            return average_column_distance, column_distances
        return average_column_distance


    def copy(self):
        """Produces a copy of the class.
        Returns
        -------
        self : class
            Returns the copy.
        """
        return copy(self)

    def save(self, path):
        """
        Save this synthesizer instance to the given path using pickle.

        Parameters
        ----------
        path: str
            Path where the synthesizer instance is saved.
        """
        with open(path, 'wb') as output:
            dill.dump(self, output)

    @classmethod
    def load(cls, path):
        """Load a synthesizer instance from specified path.
        Parameters
        ----------
        path: str
            Path where the synthesizer instance is saved.

        Returns
        -------
        synthesizer : class
            Returns synthesizer instance.
        """
        with open(path, 'rb') as f:
            return dill.load(f)

    def _check_init_args(self):
        """Check arguments provided at object instantiation"""
        self._check_epsilon()

    def _check_input_data(self, data):
        """Check input dataset - save column names and number of records"""
        # converts to dataframe in case of numpy input and make all columns categorical.
        data = pd.DataFrame(data).astype(str, copy=False)

        # prevent integer column indexing issues
        data.columns = data.columns.astype(str)

        # store general information about input data to ensure synthetic data maintains the same structure
        self.columns_ = list(data.columns)
        self.n_records_fit_ = data.shape[0]
        return data

    def _check_epsilon(self):
        """Check whether epsilon is in range [0, float(np.inf)]"""
        if not isinstance(self.epsilon, Real):
            raise TypeError("Epsilon must be numeric")

        if self.epsilon < 0:
            raise ValueError("Epsilon must be non-negative")

        if self.epsilon == 0:
            raise ValueError("Epsilon cannot be zero")
        float(self.epsilon)

    def _check_is_fitted(self):
        if not hasattr(self, 'model_'):
            msg = ("This %(name)s instance is not fitted yet. Call 'fit' with "
                   "appropriate arguments before using this synthesizer.")
            raise NotFittedError(msg % {'name': type(self).__name__})


class FixedSamplingMixin:
    """Mixin for fixing data when sampling from a synthesizer. Must be instantiated with a :class:'.BaseDPSynthesizer'."""

    # def __init__(self):
    #     if not isinstance(self, BaseDPSynthesizer):
    #         raise TypeError("FixedSamplingMixin must be implemented alongside a :class:`.BaseDPSynthesizer`")

    def sample_remaining_columns(self, fixed_data):
        """Sample columns that were seen in fit but not part of fixed data

        Parameters
        ----------
        fixed_data: pandas.DataFrame
            Input dataset that contains the same column names as seen in fit, but misses at least one column.

        Returns
        -------
        complete_data: pandas.DataFrame
            Combined dataset containing the input fixed_data and the remaining sampled column(s).
        """
        raise NotImplementedError

    def _check_fixed_data(self, fixed_data):
        """Checks whether the columns in fixed data where also seen in fit"""
        if isinstance(fixed_data, pd.Series):
            if fixed_data.name not in self.columns_:
                raise ValueError("Columns in fixed data not seen in fit.")
        if isinstance(fixed_data, pd.DataFrame):
            if not np.all([c in self.columns_ for c in fixed_data.columns]):
                raise ValueError('Columns in fixed data not seen in fit.')
            if set(fixed_data.columns) == set(self.columns_):
                raise ValueError('Fixed data already contains all the columns that were seen in fit.')

            for c in fixed_data.columns:
                assert set(np.unique(self.model_.index.get_level_values(c))) == \
                    set(np.unique(fixed_data[c])), 'conditioning variable has different categories for column: {}'.format(c)

            if self.verbose:
                sample_columns = [c for c in self.columns_ if c not in fixed_data.columns]
                print('Columns sampled and added to fixed data: {}'.format(sample_columns))

class NotFittedError(Exception):
    """Exception to indicate that the synthesizer is not fitted yet"""
