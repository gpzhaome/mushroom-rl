import numpy as np
from gym.envs.mujoco.half_cheetah_v3 import HalfCheetahEnv


class HalfCheetahEnvPOMPD(HalfCheetahEnv):

    def __init__(self, obs_to_hide=("velocities",), random_force_com=False, max_force_strength=5.0, **kwargs):

        self._hidable_obs = ("positions", "velocities")
        if type(obs_to_hide) == str:
            obs_to_hide = (obs_to_hide,)
        assert not all(x in obs_to_hide for x in self._hidable_obs), "You are not allowed to hide all observations!"
        assert all(x in self._hidable_obs for x in obs_to_hide), "Some of the observations you want to hide are not" \
                                                                 "supported. Valid observations to hide are %s."\
                                                                 % (self._hidable_obs,)
        self._obs_to_hide = obs_to_hide
        self._random_force_com = random_force_com
        self._max_force_strength = max_force_strength
        self._force_strength = 0.0
        super().__init__(**kwargs)

    def reset_model(self):
        if self._random_force_com:
            self._force_strength = np.random.choice([-self._max_force_strength, self._max_force_strength])
            sign = -1.0 if self._force_strength < 0 else 1.0
            self._forward_reward_weight = np.abs(self._forward_reward_weight) * sign
        return super().reset_model()

    def step(self, action):
        torso_index = self.model.body_names.index('torso')
        self.data.xfrc_applied[torso_index, 0] = self._force_strength
        return super().step(action)

    def _get_obs(self):
        observations = []
        if "positions" not in self._obs_to_hide:
            position = self.sim.data.qpos.flat.copy()
            if self._exclude_current_positions_from_observation:
                position = position[1:]
            observations += [position]

        if "velocities" not in self._obs_to_hide:
            velocity = self.sim.data.qvel.flat.copy()
            observations += [velocity]

        return np.concatenate(observations).ravel()
