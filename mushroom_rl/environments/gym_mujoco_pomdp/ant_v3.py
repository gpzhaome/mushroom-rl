import numpy as np
from gym.envs.mujoco.ant_v3 import AntEnv


class AntEnvPOMPD(AntEnv):

    def __init__(self, obs_to_hide=("velocities",), **kwargs):

        self._hidable_obs = ("positions", "velocities", "contact_forces")
        if type(obs_to_hide) == str:
            obs_to_hide = (obs_to_hide,)
        assert not all(x in obs_to_hide for x in self._hidable_obs), "You are not allowed to hide all observations!"
        assert all(x in self._hidable_obs for x in obs_to_hide), "Some of the observations you want to hide are not" \
                                                                 "supported. Valid observations to hide are %s."\
                                                                 % (self._hidable_obs,)
        self._obs_to_hide = obs_to_hide
        super().__init__(**kwargs)

    def _get_obs(self):
        observations = []
        if "positions" not in self._obs_to_hide:
            position = self.sim.data.qpos.flat.copy()
            if self._exclude_current_positions_from_observation:
                position = position[2:]
            observations += [position]

        if "velocities" not in self._obs_to_hide:
            velocity = self.sim.data.qvel.flat.copy()
            observations += [velocity]

        if "contact_forces" not in self._obs_to_hide:
            contact_force = self.contact_forces.flat.copy()
            observations += [contact_force]

        return np.concatenate(observations).ravel()

