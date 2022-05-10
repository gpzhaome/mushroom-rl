from .reward import NoGoalReward, NoGoalRewardRandInit, MaxVelocityReward, \
    VelocityProfileReward, CompleteTrajectoryReward, ChangingVelocityTargetReward

from .trajectory import HumanoidTrajectory

from .velocity_profile import VelocityProfile, PeriodicVelocityProfile,\
    SinVelocityProfile, ConstantVelocityProfile, RandomConstantVelocityProfile,\
    SquareWaveVelocityProfile,  VelocityProfile3D