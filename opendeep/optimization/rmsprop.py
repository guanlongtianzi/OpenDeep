'''
.. module:: rmsprop

Generic implementation of RMSProp training algorithm.
'''

__authors__ = "Markus Beissinger"
__copyright__ = "Copyright 2015, Vitruvian Science"
__credits__ = ["Pylearn2", "Markus Beissinger"]
__license__ = "Apache"
__maintainer__ = "OpenDeep"
__email__ = "opendeep-dev@googlegroups.com"

# standard libraries
import logging
# third party libraries
import theano.tensor as T
from theano.compat.python2x import OrderedDict  # use this compatibility OrderedDict
# internal references
from opendeep import sharedX
from opendeep.optimization.optimizer import Optimizer

log = logging.getLogger(__name__)

# All RMSProp needs to do is implement the get_updates() method for stochastic gradient descent
class RMSProp(Optimizer):
    """
    From Pylearn2 (https://github.com/lisa-lab/pylearn2/blob/master/pylearn2/training_algorithms/learning_rule.py)

    The RMSProp learning rule is described by Hinton in `lecture 6
    <http://www.cs.toronto.edu/~tijmen/csc321/slides/lecture_slides_lec6.pdf>`
    of the Coursera Neural Networks for Machine Learning course.
    In short, Hinton suggests "[the] magnitude of the gradient can be very
    different for different weights and can change during learning. This
    makes it hard to choose a global learning rate." RMSProp solves this
    problem by "[dividing] the learning rate for a weight by a running
    average of the magnitudes of recent gradients for that weight."
    Parameters
    ----------
    decay : float, optional
    Decay constant similar to that used in AdaDelta and Momentum methods.
    max_scaling: float, optional
    Restrict the RMSProp gradient scaling coefficient to values
    below `max_scaling`.
    """
    # Default values to use for some training parameters
    _defaults = {'decay': 0.95,
                 'max_scaling': 1e5}

    def __init__(self, model, dataset,
                 config=None, defaults=_defaults,
                 n_epoch=None, batch_size=None, minimum_batch_size=None,
                 save_frequency=None, early_stop_threshold=None, early_stop_length=None,
                 learning_rate=None, lr_decay=None, lr_factor=None,
                 decay=None, max_scaling=None):
        # need to call the Optimizer constructor
        super(RMSProp, self).__init__(model, dataset, config=config, defaults=defaults,
                                      n_epoch=n_epoch, batch_size=batch_size, minimum_batch_size=minimum_batch_size,
                                      save_frequency=save_frequency, early_stop_length=early_stop_length,
                                      early_stop_threshold=early_stop_threshold, learning_rate=learning_rate,
                                      lr_decay=lr_decay, lr_factor=lr_factor, decay=decay, max_scaling=max_scaling)

        assert self.max_scaling > 0., "Max_scaling needs to be > 0."
        self.epsilon = 1. / self.max_scaling

        self.mean_square_grads = OrderedDict()

    def get_updates(self, grads):
        """
        Provides the symbolic (theano) description of the updates needed to
        perform this learning rule. See Notes for side-effects.

        Parameters
        ----------
        grads : dict
            A dictionary mapping from the model's parameters to their
            gradients.

        Returns
        -------
        updates : OrderdDict
            A dictionary mapping from the old model parameters, to their new
            values after a single iteration of the learning rule.

        Notes
        -----
        This method has the side effect of storing the moving average
        of the square gradient in `self.mean_square_grads`. This is
        necessary in order for the monitoring channels to be able
        to track the value of these moving averages.
        Therefore, this method should only get called once for each
        instance of RMSProp.
        """
        log.debug('Setting up RMSProp for optimizer...')
        updates = OrderedDict()
        for param in grads:

            # mean_squared_grad := E[g^2]_{t-1}
            mean_square_grad = sharedX(param.get_value() * 0.)

            if param.name is None:
                raise ValueError("Model parameters must be named.")
            mean_square_grad.name = 'mean_square_grad_' + param.name

            if param.name in self.mean_square_grads:
                log.warning("Calling get_updates more than once on the "
                              "gradients of `%s` may make monitored values "
                              "incorrect." % param.name)
            # Store variable in self.mean_square_grads for monitoring.
            self.mean_square_grads[param.name] = mean_square_grad

            # Accumulate gradient
            new_mean_squared_grad = (self.decay * mean_square_grad +
                                     (1 - self.decay) * T.sqr(grads[param]))

            # Compute update
            scaled_lr = self.lr_scalers.get(param, 1.) * self.learning_rate
            rms_grad_t = T.sqrt(new_mean_squared_grad)
            rms_grad_t = T.maximum(rms_grad_t, self.epsilon)
            delta_x_t = - scaled_lr * grads[param] / rms_grad_t

            # Apply update
            updates[mean_square_grad] = new_mean_squared_grad
            updates[param] = param + delta_x_t

        return updates

