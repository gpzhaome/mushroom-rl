import numpy as np
from sklearn.ensemble import ExtraTreesRegressor

from PyPi.algorithms.batch_td import FQI
from PyPi.approximators import Regressor, ActionRegressor
from PyPi.core.core import Core
from PyPi.environments import *
from PyPi.policy import EpsGreedy
from PyPi.utils.dataset import compute_J
from PyPi.utils.parameters import Parameter


def experiment(fit_action):
    np.random.seed(20)

    # MDP
    mdp = CarOnHill()

    # Policy
    epsilon = Parameter(value=1)
    pi = EpsGreedy(epsilon=epsilon, observation_space=mdp.observation_space,
                   action_space=mdp.action_space)

    # Approximator
    approximator_params = dict()
    if fit_action:
        approximator = Regressor(ExtraTreesRegressor, **approximator_params)
    else:
        approximator = ActionRegressor(ExtraTreesRegressor,
                                       action_space=mdp.action_space,
                                       **approximator_params)

    # Agent
    algorithm_params = dict()
    fit_params = dict()
    agent_params = {'algorithm_params': algorithm_params,
                    'fit_params': fit_params}
    agent = FQI(approximator, pi, **agent_params)

    # Algorithm
    core = Core(agent, mdp)

    # Train
    core.learn(n_iterations=1, how_many=1000, n_fit_steps=20,
               iterate_over='episodes', quiet=True)
    core.reset()

    # Test
    test_epsilon = Parameter(0)
    agent.policy.set_epsilon(test_epsilon)

    initial_states = np.zeros((289, 2))
    cont = 0
    for i in range(-8, 9):
        for j in range(-8, 9):
            initial_states[cont, :] = [0.125 * i, 0.375 * j]
            cont += 1

    dataset = core.evaluate(initial_states=initial_states, quiet=True)

    return np.mean(compute_J(dataset, mdp.gamma))


if __name__ == '__main__':
    print('Executing car_on_hill test...')

    n_experiment = 1

    res = experiment(fit_action=True)
    assert np.round(res, 4) == .1601
    res = experiment(fit_action=False)
    assert np.round(res, 4) == .2346