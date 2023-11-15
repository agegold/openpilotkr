import numpy as np
from cereal import log
from openpilot.common.conversions import Conversions as CV
from openpilot.common.realtime import DT_MDL

from openpilot.common.numpy_fast import interp
from openpilot.common.params import Params
from decimal import Decimal

LaneChangeState = log.LateralPlan.LaneChangeState
LaneChangeDirection = log.LateralPlan.LaneChangeDirection

if int(Params().get("OpkrLaneChangeSpeed", encoding="utf8")) < 1:
  LANE_CHANGE_SPEED_MIN = -1
elif Params().get_bool("IsMetric"):
  LANE_CHANGE_SPEED_MIN = float(int(Params().get("OpkrLaneChangeSpeed", encoding="utf8")) * CV.KPH_TO_MS)
else:
  LANE_CHANGE_SPEED_MIN = float(int(Params().get("OpkrLaneChangeSpeed", encoding="utf8")) * CV.MPH_TO_MS)
LANE_CHANGE_TIME_MAX = 10.

DESIRES = {
  LaneChangeDirection.none: {
    LaneChangeState.off: log.LateralPlan.Desire.none,
    LaneChangeState.preLaneChange: log.LateralPlan.Desire.none,
    LaneChangeState.laneChangeStarting: log.LateralPlan.Desire.none,
    LaneChangeState.laneChangeFinishing: log.LateralPlan.Desire.none,
  },
  LaneChangeDirection.left: {
    LaneChangeState.off: log.LateralPlan.Desire.none,
    LaneChangeState.preLaneChange: log.LateralPlan.Desire.none,
    LaneChangeState.laneChangeStarting: log.LateralPlan.Desire.laneChangeLeft,
    LaneChangeState.laneChangeFinishing: log.LateralPlan.Desire.laneChangeLeft,
  },
  LaneChangeDirection.right: {
    LaneChangeState.off: log.LateralPlan.Desire.none,
    LaneChangeState.preLaneChange: log.LateralPlan.Desire.none,
    LaneChangeState.laneChangeStarting: log.LateralPlan.Desire.laneChangeRight,
    LaneChangeState.laneChangeFinishing: log.LateralPlan.Desire.laneChangeRight,
  },
}


class DesireHelper:
  def __init__(self, CP):
    self.lane_change_state = LaneChangeState.off
    self.lane_change_direction = LaneChangeDirection.none
    self.lane_change_timer = 0.0
    self.lane_change_ll_prob = 1.0
    self.keep_pulse_timer = 0.0
    self.prev_one_blinker = False
    self.desire = log.LateralPlan.Desire.none

    self.lane_change_delay = int(Params().get("OpkrAutoLaneChangeDelay", encoding="utf8"))
    self.lane_change_auto_delay = 0.0 if self.lane_change_delay == 0 else 0.2 if self.lane_change_delay == 1 else 0.5 if self.lane_change_delay == 2 \
     else 1.0 if self.lane_change_delay == 3 else 1.5 if self.lane_change_delay == 4 else 2.0

    self.lane_change_wait_timer = 0.0

    self.lane_change_adjust = [float(Decimal(Params().get("LCTimingFactor30", encoding="utf8")) * Decimal('0.01')), float(Decimal(Params().get("LCTimingFactor60", encoding="utf8")) * Decimal('0.01')),
     float(Decimal(Params().get("LCTimingFactor80", encoding="utf8")) * Decimal('0.01')), float(Decimal(Params().get("LCTimingFactor110", encoding="utf8")) * Decimal('0.01'))]
    self.lane_change_adjust_vel = [30*CV.KPH_TO_MS, 60*CV.KPH_TO_MS, 80*CV.KPH_TO_MS, 110*CV.KPH_TO_MS]
    self.lane_change_adjust_new = 2
    self.lane_change_adjust_enable = Params().get_bool("LCTimingFactorEnable")

    self.output_scale = 0.0
    self.ready_to_change = False

  def update(self, CP, carstate, controlstate, lateral_active, lane_change_prob, md):
    try:
      if CP.lateralTuning.which() == 'pid':
        self.output_scale = controlstate.lateralControlState.pidState.output
      elif CP.lateralTuning.which() == 'indi':
        self.output_scale = controlstate.lateralControlState.indiState.output
      elif CP.lateralTuning.which() == 'lqr':
        self.output_scale = controlstate.lateralControlState.lqrState.output
      elif CP.lateralTuning.which() == 'torque':
        self.output_scale = controlstate.lateralControlState.torqueState.output
      elif CP.lateralTuning.which() == 'atom':
        self.output_scale = controlstate.lateralControlState.atomState.output
    except:
      pass
    v_ego = carstate.vEgo
    one_blinker = carstate.leftBlinker != carstate.rightBlinker
    below_lane_change_speed = (v_ego < LANE_CHANGE_SPEED_MIN) or (LANE_CHANGE_SPEED_MIN == -1)

    left_edge_prob = np.clip(1.0 - md.roadEdgeStds[0], 0.0, 1.0)
    left_nearside_prob = md.laneLineProbs[0]
    left_close_prob = md.laneLineProbs[1]
    right_close_prob = md.laneLineProbs[2]
    right_nearside_prob = md.laneLineProbs[3]
    right_edge_prob = np.clip(1.0 - md.roadEdgeStds[1], 0.0, 1.0)

    if right_edge_prob > 0.35 and right_nearside_prob < 0.2 and left_nearside_prob >= right_nearside_prob:
      road_edge_stat = 1
    elif left_edge_prob > 0.35 and left_nearside_prob < 0.2 and right_nearside_prob >= left_nearside_prob:
      road_edge_stat = -1
    else:
      road_edge_stat = 0

    if carstate.leftBlinker:
      self.lane_change_direction = LaneChangeDirection.left
      lane_direction = -1
    elif carstate.rightBlinker:
      self.lane_change_direction = LaneChangeDirection.right
      lane_direction = 1
    else:
      lane_direction = 2

    if self.lane_change_state == LaneChangeState.off and road_edge_stat == lane_direction:
      self.lane_change_direction = LaneChangeDirection.none
    elif not lateral_active or (self.lane_change_timer > LANE_CHANGE_TIME_MAX) or (abs(self.output_scale) >= 0.8 and self.lane_change_timer > 0.5):
      self.lane_change_state = LaneChangeState.off
      self.lane_change_direction = LaneChangeDirection.none
    else:
      torque_applied = carstate.steeringPressed and \
                       ((carstate.steeringTorque > 0 and self.lane_change_direction == LaneChangeDirection.left) or
                        (carstate.steeringTorque < 0 and self.lane_change_direction == LaneChangeDirection.right))

      blindspot_detected = ((carstate.leftBlindspot and self.lane_change_direction == LaneChangeDirection.left) or
                            (carstate.rightBlindspot and self.lane_change_direction == LaneChangeDirection.right))

      # LaneChangeState.off
      if self.lane_change_state == LaneChangeState.off and one_blinker and not self.prev_one_blinker and not below_lane_change_speed:
        self.lane_change_state = LaneChangeState.preLaneChange
        self.lane_change_ll_prob = 1.0
        self.lane_change_wait_timer = 0 if not self.ready_to_change else self.lane_change_auto_delay
        if self.lane_change_adjust_enable:
          if controlstate.curvature > 0.0005 and self.lane_change_direction == LaneChangeDirection.left: # left curve
            self.lane_change_adjust_new = min(2.0, interp(v_ego, self.lane_change_adjust_vel, self.lane_change_adjust)*1.5)
          elif controlstate.curvature < -0.0005 and self.lane_change_direction == LaneChangeDirection.right: # right curve
            self.lane_change_adjust_new = min(2.0, interp(v_ego, self.lane_change_adjust_vel, self.lane_change_adjust)*1.5)
          else:
            self.lane_change_adjust_new = interp(v_ego, self.lane_change_adjust_vel, self.lane_change_adjust)
      # LaneChangeState.preLaneChange
      elif self.lane_change_state == LaneChangeState.preLaneChange:
        self.lane_change_wait_timer += DT_MDL
        if not one_blinker or below_lane_change_speed:
          self.lane_change_state = LaneChangeState.off
        elif not blindspot_detected and (torque_applied or (self.lane_change_auto_delay and self.lane_change_wait_timer > self.lane_change_auto_delay)):
          self.lane_change_state = LaneChangeState.laneChangeStarting

      # LaneChangeState.laneChangeStarting
      elif self.lane_change_state == LaneChangeState.laneChangeStarting:
        # fade out over .5s
        self.lane_change_ll_prob = max(self.lane_change_ll_prob - self.lane_change_adjust_new*DT_MDL, 0.0)

        # 98% certainty
        if lane_change_prob < 0.02 and self.lane_change_ll_prob < 0.01:
          self.lane_change_state = LaneChangeState.laneChangeFinishing

      # LaneChangeState.laneChangeFinishing
      elif self.lane_change_state == LaneChangeState.laneChangeFinishing:
        # fade in laneline over 1s
        self.lane_change_ll_prob = min(self.lane_change_ll_prob + DT_MDL, 1.0)
        if one_blinker and self.lane_change_ll_prob > 0.99:
          self.lane_change_state = LaneChangeState.preLaneChange
        elif self.lane_change_ll_prob > 0.99:
          self.lane_change_state = LaneChangeState.off

    if self.lane_change_state in (LaneChangeState.off, LaneChangeState.preLaneChange):
      self.lane_change_timer = 0.0
    else:
      self.lane_change_timer += DT_MDL

    self.prev_one_blinker = one_blinker
    self.ready_to_change = False
    if self.lane_change_state == LaneChangeState.off and road_edge_stat == lane_direction and one_blinker:
      self.prev_one_blinker = False
      self.ready_to_change = True

    self.desire = DESIRES[self.lane_change_direction][self.lane_change_state]

    # Send keep pulse once per second during LaneChangeStart.preLaneChange
    if self.lane_change_state in (LaneChangeState.off, LaneChangeState.laneChangeStarting):
      self.keep_pulse_timer = 0.0
    elif self.lane_change_state == LaneChangeState.preLaneChange:
      self.keep_pulse_timer += DT_MDL
      if self.keep_pulse_timer > 1.0:
        self.keep_pulse_timer = 0.0
      elif self.desire in (log.LateralPlan.Desire.keepLeft, log.LateralPlan.Desire.keepRight):
        self.desire = log.LateralPlan.Desire.none
