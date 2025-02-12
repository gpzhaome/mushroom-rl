import time
from copy import deepcopy
from time import perf_counter
from contextlib import contextmanager

from mushroom_rl.utils.angles import euler_to_quat, quat_to_euler
from mushroom_rl.environments.mujoco import ObservationType

import matplotlib.pyplot as plt

import numpy as np
from scipy import signal, interpolate

# Todo: do we want to include foot position in future?
# FOOT_KEYS = ["rel_feet_xpos_r", "rel_feet_ypos_r", "rel_feet_zpos_r",
#              "rel_feet_xpos_l", "rel_feet_ypos_l", "rel_feet_zpos_l",
#              "feet_q1_r", "feet_q2_r", "feet_q3_r", "feet_q4_r",
#              "feet_q1_l", "feet_q2_l", "feet_q3_l", "feet_q4_l",
#              "feet_xvelp_r", "feet_yvelp_r", "feet_zvelp_r",
#              "feet_xvelp_l", "feet_yvelp_l", "feet_zvelp_l",
#              "feet_xvelr_r", "feet_yvelr_r", "feet_zvelr_r",
#              "feet_xvelr_l", "feet_yvelr_l", "feet_zvelr_l"]


class Trajectory(object):
    """
    Builds a general trajectory from a numpy bin file(.npy), and automatically
    synchronizes the trajectory timestep to the desired control timestep while
    also allowing to change it's speed by the desired amount. When using
    periodic trajectories it is also possible to pass split points which signal
    the points where the trajectory repeats, and provides an utility to select
    the desired cycle.

    """
    def __init__(self, keys, traj_path, traj_dt=0.002, control_dt=0.01, ignore_keys=[]):
        """
        Constructor.

        Args:
            model: mujoco model.
            data: mujoco data structure.
            keys (list): list of keys to extract data from the trajectories.
            traj_path (string): path with the trajectory for the
                model to follow. Should be a numpy zipped file (.npz)
                with a 'trajectory_data' array and possibly a
                'split_points' array inside. The 'trajectory_data'
                should be in the shape (joints x observations);
            traj_dt (float, 0.01): time step of the trajectory file;
            control_dt (float, 0.01): model control frequency (used to
                synchronize trajectory with the control step);

        """
        self._trajectory_files = np.load(traj_path, allow_pickle=True)

        if "goal" in self._trajectory_files.keys():
            keys += ["goal"]

        # needed for deep mimic
        if "rel_feet_xpos_r" in self._trajectory_files.keys():
            keys += FOOT_KEYS

        # remove unwanted keys
        for ik in ignore_keys:
            keys.remove(ik)

        self.trajectory = np.array([self._trajectory_files[key] for key in keys])
        self.keys = keys

        if "split_points" in self._trajectory_files.keys():
            self.split_points = self._trajectory_files["split_points"]
        else:
            self.split_points = np.array([0, self.trajectory.shape[1]])

        self.n_repeating_steps = len(self.split_points) - 1

        self.traj_dt = traj_dt
        self.control_dt = control_dt
        self.traj_speed_multiplier = 1.0    # todo: delete the trajecotry speed multiplier stuff

        if self.traj_dt != control_dt or traj_speed_mult != 1.0:
            new_traj_sampling_factor = (1 / self.traj_speed_multiplier) * (
                    self.traj_dt / control_dt)

            self.trajectory = self._interpolate_trajectory(
                self.trajectory, factor=new_traj_sampling_factor
            )

            self.split_points = np.round(
                self.split_points * new_traj_sampling_factor).astype(np.int32)

        self.subtraj_step_no = 0
        self.x_dist = 0
        self.subtraj = self.trajectory.copy()

    @property
    def traj_length(self):
        return self.subtraj.shape[1]

    def create_dataset(self, ignore_keys=[], normalizer=None):

        # create a dict and extract all elements except the ones specified in ignore_keys.
        all_data = dict(zip(self.keys, deepcopy(list(self.trajectory))))
        for ikey in ignore_keys:
            del all_data[ikey]
        traj = list(all_data.values())
        states = np.transpose(deepcopy(np.array(traj)))

        # normalize if needed
        if normalizer:
            normalizer.set_state(dict(mean=np.mean(states, axis=0),
                                      var=1 * (np.std(states, axis=0) ** 2),
                                      count=1))
            states = np.array([normalizer(st) for st in states])

        # convert to dict with states and next_states
        new_states = states[:-1]
        new_next_states = states[1:]
        absorbing = np.zeros(len(new_states))

        return dict(states=new_states, next_states=new_next_states, absorbing=absorbing)

    def create_datase_with_triplet_states(self, normalizer=None):

        # get relevant data
        states = np.transpose(deepcopy(self.trajectory))

        # normalize if needed
        if normalizer:
            normalizer.set_state(dict(mean=np.mean(states, axis=0),
                                      var=1 * (np.std(states, axis=0) ** 2),
                                      count=1))
            norm_states = np.array([normalizer(st) for st in states])

        # convert to dict with states and next_states
        states = norm_states[:-2]
        next_states = norm_states[1:-1]
        next_next_states = norm_states[2:]

        return dict(states=states, next_states=next_states, next_next_states=next_next_states)


    def _interpolate_trajectory(self, traj, factor):
        x = np.arange(traj.shape[1])
        x_new = np.linspace(0, traj.shape[1] - 1, round(traj.shape[1] * factor),
                            endpoint=True)
        new_traj = interpolate.interp1d(x, traj, kind="cubic", axis=1)(x_new)
        return new_traj

    def get_next_sub_trajectory(self):
        """
        Get the next trajectory once the current one reaches it's end.

        """
        self.x_dist += self.subtraj[0][-1]
        self.reset_trajectory()

    def _get_traj_gait_sub_steps(self, initial_walking_step,
                                 number_of_walking_steps=1):
        start_sim_step = self.split_points[initial_walking_step]
        end_sim_step = self.split_points[
            initial_walking_step + number_of_walking_steps
        ]

        sub_traj = self.trajectory[:, start_sim_step:end_sim_step].copy()
        initial_x_pos = self.trajectory[0][start_sim_step]
        sub_traj[0, :] -= initial_x_pos
        return sub_traj

    def reset_trajectory(self, len_q_pos, len_qvel, substep_no=None):
        """
        Resets the trajectory and the model. The trajectory can be forced
        to start on the 'substep_no' if desired, else it starts at
        a random one.

        Args:
            substep_no (int, None): starting point of the trajectory.
                If None, the trajectory starts from a random point.
        """
        self.x_dist = 0
        if substep_no is None:
            self.subtraj_step_no = int(np.random.rand() * (
                    self.traj_length * 0.45))
        else:
            self.subtraj_step_no = substep_no

        self.subtraj = self.trajectory.copy()

        # reset x and y to middle position
        self.subtraj[0, :] -= self.subtraj[0, self.subtraj_step_no]
        self.subtraj[1, :] -= self.subtraj[1, self.subtraj_step_no]

        qpos = self.subtraj[0:len_q_pos, self.subtraj_step_no]
        qvel = self.subtraj[len_q_pos:len_q_pos + len_qvel, self.subtraj_step_no]

        return qpos, qvel

    def get_next_sample(self):
        if self.subtraj_step_no >= self.traj_length:
            self.get_next_sub_trajectory()
        sample = deepcopy(self.subtraj[:, self.subtraj_step_no])
        self.subtraj_step_no += 1
        return sample


